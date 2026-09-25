import numpy as np
import pandas as pd
from .utils import get_row

class NormalizationAgent:
    name = "Normalization Agent"

    def run(self, data):
        years = sorted([c for c in data.income.columns if isinstance(c, int)])
        if not years:
            raise ValueError("Could not identify annual statement years.")
        years = years[-5:]
        inc = data.income.reindex(columns=years)
        bs = data.balance.reindex(columns=years)
        cf = data.cashflow.reindex(columns=years)

        revenue = get_row(inc, ["Total Revenue", "Operating Revenue"])
        gross_profit = get_row(inc, ["Gross Profit"])
        ebit = get_row(inc, ["EBIT", "Operating Income"])
        ebitda = get_row(inc, ["EBITDA", "Normalized EBITDA"])
        net_income = get_row(inc, ["Net Income", "Net Income Common Stockholders"])
        pretax = get_row(inc, ["Pretax Income"])
        tax = get_row(inc, ["Tax Provision"])
        interest = get_row(inc, ["Interest Expense", "Interest Expense Non Operating"])

        cash = get_row(bs, ["Cash Cash Equivalents And Short Term Investments", "Cash And Cash Equivalents"])
        ar = get_row(bs, ["Accounts Receivable", "Receivables"])
        inventory = get_row(bs, ["Inventory"])
        ap = get_row(bs, ["Accounts Payable", "Payables And Accrued Expenses"])
        current_assets = get_row(bs, ["Current Assets", "Total Current Assets"])
        current_liab = get_row(bs, ["Current Liabilities", "Total Current Liabilities"])
        ppe = get_row(bs, ["Net PPE", "Property Plant Equipment Net"])
        total_assets = get_row(bs, ["Total Assets"])
        total_debt = get_row(bs, ["Total Debt"])
        equity = get_row(bs, ["Stockholders Equity", "Total Equity Gross Minority Interest"])

        cfo = get_row(cf, ["Operating Cash Flow", "Total Cash From Operating Activities"])
        capex = -get_row(cf, ["Capital Expenditure", "Capital Expenditures"]).abs()
        da = get_row(cf, ["Depreciation And Amortization", "Depreciation"])
        dividends = -get_row(cf, ["Cash Dividends Paid", "Common Stock Dividend Paid"]).abs()

        rows = {
            "Revenue": revenue, "Gross Profit": gross_profit, "EBITDA": ebitda,
            "EBIT": ebit, "Pretax Income": pretax, "Tax": tax, "Net Income": net_income,
            "Interest Expense": interest, "Cash": cash, "Accounts Receivable": ar,
            "Inventory": inventory, "Accounts Payable": ap, "Current Assets": current_assets,
            "Current Liabilities": current_liab, "Net PPE": ppe, "Total Assets": total_assets,
            "Total Debt": total_debt, "Equity": equity, "CFO": cfo, "Capex": capex,
            "D&A": da, "Dividends": dividends,
        }
        model = pd.DataFrame(rows).T.reindex(columns=years).fillna(0.0)
        model.columns = [str(y) + "A" for y in years]
        return model
