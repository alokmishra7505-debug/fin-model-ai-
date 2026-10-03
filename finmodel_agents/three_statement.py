from dataclasses import dataclass, field
import numpy as np
import pandas as pd
from .normalizer import IS_ROWS, BS_ROWS
from .schedules import operating_schedules
from .utils import finite, safe_div
from .forecasting import annual_assumptions

FORECAST_CF_ROWS = ["Net Income", "D&A", "Change in Working Capital", "CFO", "Capex", "FCF", "Planned Debt Change", "Funding Draw", "Dividends", "Financing Cash Flow", "Net Cash Change", "Opening Cash", "Closing Cash", "Cash Reconciliation", "UFCF"]


@dataclass
class ForecastModel:
    income: pd.DataFrame
    balance: pd.DataFrame
    cashflow: pd.DataFrame
    schedules: dict
    assumptions: object
    opening: dict
    notes: list = field(default_factory=list)
    yearly_assumptions: tuple = ()


def opening_balance(hist, info):
    if hist.income.empty:
        raise ValueError("A reported annual revenue period is required to build a forecast.")
    i, b = hist.income.iloc[:, -1], hist.balance.iloc[:, -1]
    required = ["Total Assets", "Total Liabilities", "Equity", "Cash"]
    if any(not finite(b[k]) for k in required):
        raise ValueError("The latest annual period lacks complete balance-sheet anchors. Historical data is available; forecasting is paused.")
    if abs(b["Balance Check"]) > max(1, abs(b["Total Assets"])*1e-5):
        raise ValueError("The reported opening balance sheet does not balance. Forecasting is paused rather than silently inserting a plug.")
    o = {k: float(v) for k, v in b.items()}
    notes = []
    for key in ("Accounts Receivable", "Inventory", "Net PPE", "Accounts Payable", "Current Debt", "Debt"):
        if not finite(o[key]):
            o[key] = 0.0
            notes.append(f"Opening {key.lower()} was unavailable: explicitly assumed zero; valuation reliability is reduced.")
    if not finite(o["Current Assets"]):
        o["Current Assets"] = o["Cash"]+o["Accounts Receivable"]+o["Inventory"]
        notes.append("Opening current assets use known current components; remaining assets are held in other assets.")
    if not finite(o["Current Liabilities"]):
        o["Current Liabilities"] = o["Accounts Payable"]+o["Current Debt"]
        notes.append("Opening current liabilities use known current components; remaining liabilities are held in other liabilities.")
    o["Other Current Assets"] = o["Current Assets"]-o["Cash"]-o["Accounts Receivable"]-o["Inventory"]
    o["Other Assets"] = o["Total Assets"]-o["Current Assets"]-o["Net PPE"]
    o["Other Current Liabilities"] = o["Current Liabilities"]-o["Accounts Payable"]-o["Current Debt"]
    o["Other Liabilities"] = o["Total Liabilities"]-o["Accounts Payable"]-o["Other Current Liabilities"]-o["Debt"]
    o["Revenue"] = float(i["Revenue"])
    o["Shares"] = float(info["sharesOutstanding"]) if finite(info.get("sharesOutstanding")) and info["sharesOutstanding"] > 0 else np.nan
    o["EPS"] = i["EPS"]
    o["Net Working Capital"] = o["Accounts Receivable"]+o["Inventory"]+o["Other Current Assets"]-o["Accounts Payable"]-o["Other Current Liabilities"]
    if not finite(o["Shares"]):
        notes.append("Shares outstanding are unavailable; per-share forecasts and valuation are unavailable.")
    return o, notes


def build_forecast(hist, info, assumptions, years=5, yearly=None):
    assumptions.validate()
    if years not in (3, 4, 5):
        raise ValueError("Select a forecast horizon of three to five years.")
    o, notes = opening_balance(hist, info)
    annual = annual_assumptions(assumptions,years,yearly)
    prev = o.copy()
    records = {}
    start = pd.Timestamp(hist.years[-1])
    current_debt_share = np.clip(safe_div(o["Current Debt"], o["Debt"]), 0, 1) if o["Debt"] > 0 else 0
    for n in range(1, years+1):
        a = annual[n-1]
        r = {}
        r["Revenue"] = prev["Revenue"] * (1+a.growth)
        r["Revenue growth"] = a.growth
        r["COGS"] = r["Revenue"] * (1-a.gross_margin)
        r["Gross Profit"] = r["Revenue"]-r["COGS"]
        r["EBITDA"] = r["Revenue"]*a.ebitda_margin
        r["Capex"] = r["Revenue"]*a.capex_pct
        r["Opening Net PPE"] = prev["Net PPE"]
        r["D&A"] = min(r["Revenue"]*a.da_pct, max(0, prev["Net PPE"]+r["Capex"]))
        r["EBIT"] = r["EBITDA"]-r["D&A"]
        r["Operating Expenses"] = r["Gross Profit"]-r["EBIT"]
        r["Opening Debt"] = prev["Debt"]
        r["Interest Expense"] = prev["Debt"]*a.interest_rate
        r["Pretax Income"] = r["EBIT"]-r["Interest Expense"]
        r["Taxes"] = max(0, r["Pretax Income"])*a.tax_rate
        r["Net Income"] = r["Pretax Income"]-r["Taxes"]
        r["Accounts Receivable"] = r["Revenue"]*a.dso/365
        r["Inventory"] = r["COGS"]*a.dio/365
        r["Accounts Payable"] = r["COGS"]*a.dpo/365
        for key in ("Other Current Assets", "Other Assets", "Other Current Liabilities", "Other Liabilities", "Shares"):
            r[key] = o[key]
        r["Net Working Capital"] = r["Accounts Receivable"]+r["Inventory"]+r["Other Current Assets"]-r["Accounts Payable"]-r["Other Current Liabilities"]
        r["Change in Working Capital"] = r["Net Working Capital"]-prev["Net Working Capital"]
        r["CFO"] = r["Net Income"]+r["D&A"]-r["Change in Working Capital"]
        r["FCF"] = r["CFO"]-r["Capex"]
        r["Planned Debt Change"] = max(-prev["Debt"], prev["Debt"]*a.debt_change_pct)
        r["Dividends"] = max(0, r["Net Income"])*a.dividend_payout
        cash_before = prev["Cash"]+r["FCF"]+r["Planned Debt Change"]-r["Dividends"]
        r["Funding Draw"] = max(0, r["Revenue"]*a.min_cash_pct-cash_before)
        r["Debt"] = prev["Debt"]+r["Planned Debt Change"]+r["Funding Draw"]
        r["Current Debt"] = r["Debt"]*current_debt_share
        r["Long Term Debt"] = r["Debt"]-r["Current Debt"]
        r["Financing Cash Flow"] = r["Planned Debt Change"]+r["Funding Draw"]-r["Dividends"]
        r["Net Cash Change"] = r["FCF"]+r["Financing Cash Flow"]
        r["Opening Cash"] = prev["Cash"]
        r["Cash"] = r["Closing Cash"] = prev["Cash"]+r["Net Cash Change"]
        r["Cash Reconciliation"] = r["Cash"]-r["Opening Cash"]-r["Net Cash Change"]
        r["Net PPE"] = prev["Net PPE"]+r["Capex"]-r["D&A"]
        r["Current Assets"] = r["Cash"]+r["Accounts Receivable"]+r["Inventory"]+r["Other Current Assets"]
        r["Total Assets"] = r["Current Assets"]+r["Net PPE"]+r["Other Assets"]
        r["Current Liabilities"] = r["Accounts Payable"]+r["Other Current Liabilities"]+r["Current Debt"]
        r["Total Liabilities"] = r["Current Liabilities"]+r["Long Term Debt"]+r["Other Liabilities"]
        r["Equity"] = prev["Equity"]+r["Net Income"]-r["Dividends"]
        r["Total Liabilities + Equity"] = r["Total Liabilities"]+r["Equity"]
        r["Balance Check"] = r["Total Assets"]-r["Total Liabilities + Equity"]
        r["UFCF"] = r["EBIT"]-max(0, r["EBIT"])*a.tax_rate+r["D&A"]-r["Capex"]-r["Change in Working Capital"]
        r["EPS"] = safe_div(r["Net Income"], r["Shares"])
        r["EPS change"] = r["EPS"]-prev["EPS"]
        r.update({"Gross margin": a.gross_margin, "EBITDA margin": a.ebitda_margin, "Tax rate": a.tax_rate,
                  "Receivable days": a.dso, "Inventory days": a.dio, "Payable days": a.dpo, "Interest rate": a.interest_rate})
        records[(start+pd.DateOffset(years=n)).strftime("%Y-%m-%d")] = r
        prev = r
    frame = pd.DataFrame(records)
    notes.extend([
        "Forecasts use the displayed year-specific assumptions, a 365-day convention, and the latest reported fiscal period. Fiscal year-end dates are approximated for 52/53-week reporters.",
        "Other assets and liabilities remain fixed in nominal terms. No acquisitions, disposals, FX movements, buybacks or stock compensation are modelled. Total equity includes minority interests when available; allocation between parent and minorities is not forecast.",
        "Cash includes short-term investments where provided. Minimum cash shortfalls produce a visible Funding Draw. Interest is charged on opening debt to avoid circularity; funding draws bear interest from the next year.",
        "Debt retains the opening current/long-term proportion. Shares stay constant at current outstanding shares; EPS uses this count rather than historical weighted-average diluted shares.",
        "Taxes have no loss carryforwards or deferred-tax movements. Depreciation cannot exceed available net PPE plus capex. Dividends apply only to positive net income.",
    ])
    return ForecastModel(frame.loc[IS_ROWS], frame.loc[BS_ROWS], frame.loc[FORECAST_CF_ROWS], operating_schedules(records), assumptions, o, notes, annual)
