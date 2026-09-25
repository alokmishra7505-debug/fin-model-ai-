import numpy as np
import pandas as pd
from .utils import bounded, safe_float


class ScheduleAgent:
    name = "Operating Schedules Agent"

    def derive(self, hist: pd.DataFrame, info: dict):
        rev = hist.loc["Revenue"].replace(0, np.nan)
        cogs = (hist.loc["Revenue"] - hist.loc["Gross Profit"]).replace(0, np.nan)
        ar = hist.loc["Accounts Receivable"]
        inv = hist.loc["Inventory"]
        ap = hist.loc["Accounts Payable"]

        def med(series, fallback):
            s = pd.to_numeric(series, errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
            return float(s.tail(3).median()) if len(s) else fallback

        growth = rev.pct_change()
        gross_margin = hist.loc["Gross Profit"] / rev
        ebitda_margin = hist.loc["EBITDA"] / rev
        da_pct = hist.loc["D&A"].abs() / rev
        capex_pct = hist.loc["Capex"].abs() / rev
        tax_rate = hist.loc["Tax"] / hist.loc["Pretax Income"].replace(0, np.nan)
        dso = ar / rev * 365
        dio = inv / cogs * 365
        dpo = ap / cogs * 365
        interest_rate = hist.loc["Interest Expense"].abs() / hist.loc["Total Debt"].replace(0, np.nan)

        return {
            "revenue_growth": bounded(med(growth, 0.06), -0.15, 0.25, 0.06),
            "gross_margin": bounded(med(gross_margin, 0.40), 0.02, 0.95, 0.40),
            "ebitda_margin": bounded(med(ebitda_margin, 0.20), -0.20, 0.75, 0.20),
            "da_pct_revenue": bounded(med(da_pct, 0.03), 0.0, 0.20, 0.03),
            "capex_pct_revenue": bounded(med(capex_pct, 0.04), 0.0, 0.30, 0.04),
            "tax_rate": bounded(med(tax_rate, 0.24), 0.0, 0.45, 0.24),
            "dso": bounded(med(dso, 45), 0, 180, 45),
            "dio": bounded(med(dio, 50), 0, 240, 50),
            "dpo": bounded(med(dpo, 45), 0, 240, 45),
            "interest_rate": bounded(med(interest_rate, 0.05), 0.0, 0.20, 0.05),
            "debt_repayment_pct": 0.05,
            "dividend_payout": bounded(abs(med(hist.loc["Dividends"] / hist.loc["Net Income"].replace(0, np.nan), 0.0)), 0.0, 0.90, 0.0),
            "terminal_growth": 0.025,
            "risk_free_rate": 0.043,
            "equity_risk_premium": 0.055,
            "shares_outstanding": safe_float(info.get("sharesOutstanding"), np.nan),
        }

    def scenario(self, assumptions: dict, scenario: str):
        a = dict(assumptions)
        if scenario == "Bull":
            a["revenue_growth"] += 0.03
            a["ebitda_margin"] += 0.02
            a["gross_margin"] += 0.01
        elif scenario == "Bear":
            a["revenue_growth"] -= 0.03
            a["ebitda_margin"] -= 0.02
            a["gross_margin"] -= 0.01
        a["revenue_growth"] = bounded(a["revenue_growth"], -0.30, 0.40, 0.05)
        a["ebitda_margin"] = bounded(a["ebitda_margin"], -0.30, 0.80, 0.20)
        a["gross_margin"] = bounded(a["gross_margin"], 0.01, 0.95, 0.40)
        return a
