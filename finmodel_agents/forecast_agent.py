import numpy as np
import pandas as pd
from .utils import bounded

class ForecastAgent:
    name = "Forecast Agent"

    def derive_assumptions(self, hist: pd.DataFrame):
        rev = hist.loc["Revenue"].replace(0, np.nan)
        growth = rev.pct_change().replace([np.inf, -np.inf], np.nan).dropna()
        revenue_growth = bounded(growth.tail(3).median() if not growth.empty else 0.05, -0.15, 0.25, 0.05)

        def margin(row, fallback=0):
            s = (hist.loc[row] / rev).replace([np.inf, -np.inf], np.nan).dropna()
            return bounded(s.tail(3).median() if not s.empty else fallback, -1, 1, fallback)

        tax_base = (hist.loc["Tax"] / hist.loc["Pretax Income"].replace(0, np.nan)).replace([np.inf,-np.inf],np.nan).dropna()
        return {
            "revenue_growth": revenue_growth,
            "gross_margin": margin("Gross Profit", 0.4),
            "ebitda_margin": margin("EBITDA", 0.2),
            "ebit_margin": margin("EBIT", 0.15),
            "net_margin": margin("Net Income", 0.10),
            "tax_rate": bounded(tax_base.tail(3).median() if not tax_base.empty else 0.24, 0, 0.45, 0.24),
            "da_pct_revenue": abs(margin("D&A", 0.03)),
            "capex_pct_revenue": abs(margin("Capex", -0.04)),
            "ar_pct_revenue": abs(margin("Accounts Receivable", 0.12)),
            "inventory_pct_revenue": abs(margin("Inventory", 0.08)),
            "ap_pct_revenue": abs(margin("Accounts Payable", 0.08)),
            "current_assets_pct_revenue": abs(margin("Current Assets", 0.35)),
            "current_liab_pct_revenue": abs(margin("Current Liabilities", 0.20)),
        }

    def run(self, hist: pd.DataFrame, assumptions: dict, years=5, scenario="Base"):
        last_col = hist.columns[-1]
        start_year = int(str(last_col)[:4]) + 1
        cols = [f"{start_year+i}E" for i in range(years)]
        fc = pd.DataFrame(0.0, index=hist.index, columns=cols)

        g = assumptions["revenue_growth"]
        if scenario == "Bull": g += 0.03
        elif scenario == "Bear": g -= 0.03
        g = bounded(g, -0.25, 0.35, 0.05)

        prev_rev = float(hist.loc["Revenue", last_col])
        prev_nwc = float(hist.loc["Accounts Receivable", last_col] + hist.loc["Inventory", last_col] - hist.loc["Accounts Payable", last_col])
        prev_ppe = float(hist.loc["Net PPE", last_col])
        debt = float(hist.loc["Total Debt", last_col])
        cash = float(hist.loc["Cash", last_col])
        equity = float(hist.loc["Equity", last_col])
        assets_other = float(hist.loc["Total Assets", last_col] - hist.loc["Cash", last_col] - hist.loc["Accounts Receivable", last_col] - hist.loc["Inventory", last_col] - hist.loc["Net PPE", last_col])

        for c in cols:
            rev = prev_rev * (1 + g)
            gm = assumptions["gross_margin"]
            em = assumptions["ebit_margin"]
            ebitdam = max(assumptions["ebitda_margin"], em)
            da = rev * assumptions["da_pct_revenue"]
            capex = -rev * assumptions["capex_pct_revenue"]
            ebit = rev * em
            ebitda = rev * ebitdam
            pretax = ebit - max(0.0, debt * 0.04)
            tax = max(0.0, pretax * assumptions["tax_rate"])
            ni = pretax - tax
            ar = rev * assumptions["ar_pct_revenue"]
            inv = rev * assumptions["inventory_pct_revenue"]
            ap = rev * assumptions["ap_pct_revenue"]
            nwc = ar + inv - ap
            delta_nwc = nwc - prev_nwc
            cfo = ni + da - delta_nwc
            fcf = cfo + capex
            ppe = max(0.0, prev_ppe - da - capex)  # capex is negative
            cash = max(0.0, cash + fcf)
            equity = equity + ni
            current_assets = rev * assumptions["current_assets_pct_revenue"]
            current_liab = rev * assumptions["current_liab_pct_revenue"]
            total_assets = cash + ar + inv + ppe + assets_other

            vals = {
                "Revenue": rev, "Gross Profit": rev*gm, "EBITDA": ebitda, "EBIT": ebit,
                "Pretax Income": pretax, "Tax": tax, "Net Income": ni, "Interest Expense": max(0.0, debt*0.04),
                "Cash": cash, "Accounts Receivable": ar, "Inventory": inv, "Accounts Payable": ap,
                "Current Assets": current_assets, "Current Liabilities": current_liab,
                "Net PPE": ppe, "Total Assets": total_assets, "Total Debt": debt, "Equity": equity,
                "CFO": cfo, "Capex": capex, "D&A": da, "Dividends": 0.0,
            }
            for r,v in vals.items(): fc.loc[r,c] = v
            prev_rev, prev_nwc, prev_ppe = rev, nwc, ppe
        return fc
