from dataclasses import dataclass, field
import numpy as np
import pandas as pd
from .utils import safe_div, finite

IS_ROWS = ["Revenue", "COGS", "Gross Profit", "Operating Expenses", "EBITDA", "D&A", "EBIT", "Interest Expense", "Pretax Income", "Taxes", "Net Income", "EPS"]
BS_ROWS = ["Cash", "Accounts Receivable", "Inventory", "Other Current Assets", "Current Assets", "Net PPE", "Other Assets", "Total Assets", "Accounts Payable", "Other Current Liabilities", "Current Debt", "Current Liabilities", "Long Term Debt", "Debt", "Other Liabilities", "Total Liabilities", "Equity", "Total Liabilities + Equity", "Balance Check"]
CF_ROWS = ["CFO", "Capex", "FCF", "Net Debt Issuance", "Dividends"]


@dataclass
class HistoricalModel:
    income: pd.DataFrame
    balance: pd.DataFrame
    cashflow: pd.DataFrame
    notes: list = field(default_factory=list)

    @property
    def years(self):
        return list(self.income.columns)


def normalize(data):
    notes = []
    dates = sorted(set(data.income.columns) | set(data.balance.columns) | set(data.cashflow.columns))
    # Yahoo sometimes includes an otherwise empty extra period. Require reported revenue.
    dates = [d for d in dates if d in data.income.columns and any(
        key in data.income.index and finite(data.income.at[key, d]) for key in ("Total Revenue", "Operating Revenue"))]
    income, balance, cashflow = {}, {}, {}
    for date in dates:
        label = pd.Timestamp(date).strftime("%Y-%m-%d")

        def get(frame, *keys):
            for key in keys:
                if key in frame.index and date in frame.columns and finite(frame.at[key, date]):
                    return float(frame.at[key, date])
            return np.nan

        def derived(value, fallback, item):
            if finite(value):
                return value
            if finite(fallback):
                notes.append(f"{label}: {item} derived from reported components.")
            return fallback

        inc, bs, cf = data.income, data.balance, data.cashflow
        rev = get(inc, "Total Revenue", "Operating Revenue")
        cogs = abs(get(inc, "Cost Of Revenue"))
        gross = derived(get(inc, "Gross Profit"), rev - cogs, "Gross profit")
        ebit = get(inc, "Operating Income", "EBIT")
        da = abs(get(cf, "Depreciation And Amortization", "Depreciation Amortization Depletion", "Depreciation"))
        da = derived(da, abs(get(inc, "Reconciled Depreciation", "Depreciation And Amortization In Income Statement")), "D&A")
        ebitda = derived(get(inc, "EBITDA", "Normalized EBITDA"), ebit + da, "EBITDA")
        da = derived(da, ebitda - ebit, "D&A")
        ni = get(inc, "Net Income", "Net Income Common Stockholders")
        income[label] = dict(zip(IS_ROWS, [rev, cogs, gross, derived(get(inc, "Operating Expense"), gross - ebit, "Operating expenses"), ebitda, da, ebit,
              abs(get(inc, "Interest Expense", "Interest Expense Non Operating")), get(inc, "Pretax Income"), get(inc, "Tax Provision"), ni,
              derived(get(inc, "Diluted EPS", "Basic EPS"), safe_div(ni, get(inc, "Diluted Average Shares", "Basic Average Shares")), "EPS")]))
        cash = get(bs, "Cash Cash Equivalents And Short Term Investments", "Cash And Cash Equivalents")
        ar = get(bs, "Accounts Receivable", "Receivables")
        inv = get(bs, "Inventory")
        ca = get(bs, "Current Assets")
        ppe = get(bs, "Net PPE")
        assets = get(bs, "Total Assets")
        ap = get(bs, "Accounts Payable", "Payables")
        cl = get(bs, "Current Liabilities")
        cd = get(bs, "Current Debt And Capital Lease Obligation", "Current Debt")
        ld = get(bs, "Long Term Debt And Capital Lease Obligation", "Long Term Debt")
        debt = derived(get(bs, "Total Debt"), cd + ld, "Total debt")
        ld = derived(ld, debt - cd, "Long-term debt")
        liab = get(bs, "Total Liabilities Net Minority Interest", "Total Liabilities")
        equity = get(bs, "Total Equity Gross Minority Interest", "Stockholders Equity", "Common Stock Equity")
        oca = derived(get(bs, "Other Current Assets"), ca - cash - ar - inv, "Other current assets")
        # Residual categories include ALL omitted items, not only Yahoo's narrow 'other' field.
        oca = ca - cash - ar - inv if all(finite(v) for v in (ca, cash, ar, inv)) else oca
        otherassets = assets - ca - ppe
        ocl = cl - ap - cd
        otherliab = liab - ap - ocl - debt
        balance[label] = dict(zip(BS_ROWS, [cash, ar, inv, oca, ca, ppe, otherassets, assets, ap, ocl, cd, cl, ld, debt, otherliab, liab, equity, liab + equity, assets - liab - equity]))
        cfo = get(cf, "Operating Cash Flow", "Cash Flow From Continuing Operating Activities")
        capex = abs(get(cf, "Capital Expenditure", "Capital Expenditure Reported"))
        netdebt = get(cf, "Net Issuance Payments Of Debt")
        dividends = abs(get(cf, "Cash Dividends Paid", "Common Stock Dividend Paid"))
        cashflow[label] = dict(zip(CF_ROWS, [cfo, capex, derived(get(cf, "Free Cash Flow"), cfo - capex, "FCF"), netdebt, dividends]))
    notes.append("Historical residual asset and liability categories reconcile reported totals. Missing source values remain N/A; expenses and capex are displayed as positive uses of funds.")
    return HistoricalModel(pd.DataFrame(income).reindex(IS_ROWS), pd.DataFrame(balance).reindex(BS_ROWS), pd.DataFrame(cashflow).reindex(CF_ROWS), notes)
