from dataclasses import dataclass, replace, asdict
import numpy as np
from .utils import finite, safe_div


@dataclass(frozen=True)
class Assumptions:
    growth: float = .06
    gross_margin: float = .40
    ebitda_margin: float = .25
    tax_rate: float = .25
    dso: float = 45
    dio: float = 30
    dpo: float = 45
    capex_pct: float = .05
    da_pct: float = .04
    debt_change_pct: float = 0
    interest_rate: float = .05
    terminal_growth: float = .025
    risk_free: float = .04
    equity_premium: float = .055
    beta: float = 1
    cost_debt: float = .05
    dividend_payout: float = .20
    min_cash_pct: float = .02

    def validate(self):
        if not all(finite(v) for v in asdict(self).values()):
            raise ValueError("All assumptions must be finite numbers.")
        if not -.5 <= self.growth <= 1 or not 0 <= self.ebitda_margin <= self.gross_margin <= 1:
            raise ValueError("Use growth between -50% and 100%, and gross margin at least as high as EBITDA margin.")
        if not 0 <= self.tax_rate <= .6 or not 0 <= self.dividend_payout <= 1:
            raise ValueError("Tax rate or dividend payout is outside the supported range.")
        if min(self.dso, self.dio, self.dpo, self.capex_pct, self.da_pct, self.interest_rate, self.min_cash_pct, self.cost_debt, self.risk_free, self.equity_premium, self.beta) < 0:
            raise ValueError("Days, spending rates, interest rates, beta and capital costs cannot be negative.")
        if not -.05 <= self.terminal_growth <= .10 or not -1 <= self.debt_change_pct <= 1:
            raise ValueError("Terminal growth or annual debt change is outside the supported range.")


LABELS = {
    "growth": "Revenue growth", "gross_margin": "Gross margin", "ebitda_margin": "EBITDA margin", "tax_rate": "Tax rate",
    "dso": "Receivable days (DSO)", "dio": "Inventory days (DIO)", "dpo": "Payable days (DPO)",
    "capex_pct": "Capex / revenue", "da_pct": "D&A / revenue", "debt_change_pct": "Annual debt change / opening debt",
    "interest_rate": "Interest rate on opening debt", "terminal_growth": "Terminal growth", "risk_free": "Risk-free rate",
    "equity_premium": "Equity risk premium", "beta": "Beta", "cost_debt": "Cost of debt",
    "dividend_payout": "Dividend payout / net income", "min_cash_pct": "Minimum cash / revenue",
}
SCENARIOS = ("Bear", "Base", "Bull")
VALUATION_KEYS = ("terminal_growth","risk_free","equity_premium","beta","cost_debt")
OPERATING_KEYS = tuple(key for key in LABELS if key not in VALUATION_KEYS)


def annual_assumptions(base, years, overrides=None):
    if overrides is not None and len(overrides)!=years:
        raise ValueError("Provide one complete assumption set for each forecast year.")
    result = tuple(overrides) if overrides is not None else (base,)*years
    for item in result:
        item.validate()
    return result


def default_assumptions(hist, info):
    if hist.income.empty:
        return Assumptions()
    i, b, c = hist.income.iloc[:, -1], hist.balance.iloc[:, -1], hist.cashflow.iloc[:, -1]
    rev = i["Revenue"]

    def clip(value, low, high, fallback):
        return float(np.clip(value, low, high)) if finite(value) else fallback

    growth = hist.income.loc["Revenue"].pct_change(fill_method=None).dropna().median()
    gm = clip(safe_div(i["Gross Profit"], rev), .05, .95, .4)
    return Assumptions(growth=clip(growth, -.1, .2, .06), gross_margin=gm,
        ebitda_margin=clip(safe_div(i["EBITDA"], rev), .02, gm, min(.25, gm)),
        tax_rate=clip(safe_div(i["Taxes"], i["Pretax Income"]), .10, .40, .25),
        dso=clip(safe_div(b["Accounts Receivable"], rev)*365, 0, 180, 45),
        dio=clip(safe_div(b["Inventory"], i["COGS"])*365, 0, 365, 30),
        dpo=clip(safe_div(b["Accounts Payable"], i["COGS"])*365, 0, 365, 45),
        capex_pct=clip(safe_div(c["Capex"], rev), 0, .30, .05),
        da_pct=clip(safe_div(i["D&A"], rev), 0, .25, .04),
        beta=clip(info.get("beta"), .2, 3, 1),
        dividend_payout=clip(safe_div(c["Dividends"], i["Net Income"]), 0, 1, .2),
        risk_free=.065 if info.get("financialCurrency", info.get("currency")) == "INR" else .04)


def scenario_assumptions(base, name):
    shift = {"Bear": -1, "Base": 0, "Bull": 1}[name]
    gm = float(np.clip(base.gross_margin + .02*shift, .01, .99))
    return replace(base, growth=float(np.clip(base.growth + .03*shift, -.5, 1)), gross_margin=gm,
        ebitda_margin=float(np.clip(base.ebitda_margin + .02*shift, 0, gm)),
        dso=max(0, base.dso - 5*shift))
