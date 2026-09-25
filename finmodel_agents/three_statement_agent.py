import numpy as np
import pandas as pd


class ThreeStatementAgent:
    name = "Integrated 3-Statement Agent"

    def run(self, hist: pd.DataFrame, assumptions: dict, years: int = 5):
        last = hist.columns[-1]
        try:
            start_year = int(str(last)[:4]) + 1
        except Exception:
            start_year = pd.Timestamp.utcnow().year + 1
        cols = [f"{start_year+i}E" for i in range(years)]

        rows = [
            "Revenue", "COGS", "Gross Profit", "EBITDA", "D&A", "EBIT", "Interest Expense", "Pretax Income", "Tax", "Net Income",
            "Cash", "Accounts Receivable", "Inventory", "Accounts Payable", "Current Assets", "Current Liabilities", "Net PPE", "Other Assets", "Total Assets", "Total Debt", "Other Liabilities", "Equity", "Total Liabilities & Equity", "Balance Check",
            "CFO", "Capex", "Debt Issuance/(Repayment)", "Dividends", "Net Change in Cash", "Cash Flow Check", "FCF",
        ]
        fc = pd.DataFrame(0.0, index=rows, columns=cols)

        prev_rev = float(hist.loc["Revenue", last])
        prev_cash = float(hist.loc["Cash", last])
        prev_ar = float(hist.loc["Accounts Receivable", last])
        prev_inv = float(hist.loc["Inventory", last])
        prev_ap = float(hist.loc["Accounts Payable", last])
        prev_ppe = float(hist.loc["Net PPE", last])
        prev_debt = max(0.0, float(hist.loc["Total Debt", last]))
        prev_equity = float(hist.loc["Equity", last])
        prev_assets = float(hist.loc["Total Assets", last])
        prev_other_assets = max(0.0, prev_assets - prev_cash - prev_ar - prev_inv - prev_ppe)
        prev_other_liab = prev_assets - prev_debt - prev_ap - prev_equity

        for c in cols:
            rev = prev_rev * (1 + assumptions["revenue_growth"])
            gp = rev * assumptions["gross_margin"]
            cogs = max(0.0, rev - gp)
            ebitda = rev * assumptions["ebitda_margin"]
            da = rev * assumptions["da_pct_revenue"]
            ebit = ebitda - da

            scheduled_repayment = min(prev_debt, prev_debt * assumptions["debt_repayment_pct"])
            avg_debt = max(0.0, prev_debt - scheduled_repayment / 2)
            interest = avg_debt * assumptions["interest_rate"]
            pretax = ebit - interest
            tax = max(0.0, pretax * assumptions["tax_rate"])
            ni = pretax - tax

            ar = rev * assumptions["dso"] / 365
            inv = cogs * assumptions["dio"] / 365
            ap = cogs * assumptions["dpo"] / 365
            delta_nwc = (ar + inv - ap) - (prev_ar + prev_inv - prev_ap)
            capex = -(rev * assumptions["capex_pct_revenue"])
            cfo = ni + da - delta_nwc
            dividends = -max(0.0, ni * assumptions["dividend_payout"])
            debt_change = -scheduled_repayment
            net_change_cash = cfo + capex + debt_change + dividends
            cash = prev_cash + net_change_cash

            # If cash would fall below zero, draw enough debt to keep the model solvent.
            if cash < 0:
                emergency_draw = -cash
                debt_change += emergency_draw
                cash = 0.0
                net_change_cash += emergency_draw

            debt = max(0.0, prev_debt + debt_change)
            ppe = max(0.0, prev_ppe - da - capex)  # capex is negative
            other_assets = prev_other_assets
            equity = prev_equity + ni + dividends
            current_assets = cash + ar + inv
            current_liabilities = ap + min(debt, max(0.0, debt * 0.20))
            total_assets = cash + ar + inv + ppe + other_assets

            # Other liabilities carry the historical base and act only as the balancing residual.
            other_liab = total_assets - debt - ap - equity
            total_le = debt + ap + other_liab + equity
            balance_check = total_assets - total_le
            cash_flow_check = cash - prev_cash - net_change_cash
            fcf = cfo + capex

            values = {
                "Revenue": rev, "COGS": cogs, "Gross Profit": gp, "EBITDA": ebitda, "D&A": da, "EBIT": ebit,
                "Interest Expense": interest, "Pretax Income": pretax, "Tax": tax, "Net Income": ni,
                "Cash": cash, "Accounts Receivable": ar, "Inventory": inv, "Accounts Payable": ap,
                "Current Assets": current_assets, "Current Liabilities": current_liabilities, "Net PPE": ppe, "Other Assets": other_assets, "Total Assets": total_assets, "Total Debt": debt,
                "Other Liabilities": other_liab, "Equity": equity, "Total Liabilities & Equity": total_le,
                "Balance Check": balance_check, "CFO": cfo, "Capex": capex, "Debt Issuance/(Repayment)": debt_change,
                "Dividends": dividends, "Net Change in Cash": net_change_cash, "Cash Flow Check": cash_flow_check, "FCF": fcf,
            }
            for row, value in values.items():
                fc.loc[row, c] = value

            prev_rev, prev_cash, prev_ar, prev_inv, prev_ap = rev, cash, ar, inv, ap
            prev_ppe, prev_debt, prev_equity = ppe, debt, equity
            prev_other_assets, prev_other_liab = other_assets, other_liab

        return fc
