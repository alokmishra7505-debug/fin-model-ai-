import pandas as pd


def operating_schedules(records):
    frame = pd.DataFrame(records)
    groups = {
        "Revenue Build": ["Revenue", "Revenue growth", "COGS", "Gross Profit", "Gross margin", "EBITDA", "EBITDA margin"],
        "Working Capital": ["Accounts Receivable", "Inventory", "Accounts Payable", "Net Working Capital", "Change in Working Capital", "Receivable days", "Inventory days", "Payable days"],
        "Capex & Depreciation": ["Opening Net PPE", "Capex", "D&A", "Net PPE"],
        "Debt Schedule": ["Opening Debt", "Planned Debt Change", "Funding Draw", "Debt", "Interest rate", "Interest Expense"],
        "Taxes & EPS": ["Pretax Income", "Tax rate", "Taxes", "Net Income", "Dividends", "Shares", "EPS", "EPS change"],
    }
    return {name: frame.loc[rows] for name, rows in groups.items()}
