import numpy as np
import pandas as pd
from .utils import safe_div, finite

PERCENT_KPIS = {"Revenue growth", "Gross margin", "EBITDA margin", "EBIT margin", "Net margin", "FCF margin", "ROE", "ROA", "ROIC", "FCF conversion", "DuPont ROE"}
DAY_KPIS = {"Receivable days", "Inventory days", "Payable days", "Cash conversion cycle"}


def calculate_kpis(income, balance, cashflow):
    columns = {}
    for n,col in enumerate(income.columns):
        i,b,c = income[col],balance[col],cashflow[col]
        prev = balance.iloc[:,n-1] if n else b
        avg_assets = (b["Total Assets"]+prev["Total Assets"])/2
        avg_equity = (b["Equity"]+prev["Equity"])/2
        rev = i["Revenue"]
        invested = (b["Equity"]+b["Debt"]-b["Cash"]+prev["Equity"]+prev["Debt"]-prev["Cash"])/2
        tax = safe_div(i["Taxes"],i["Pretax Income"])
        tax = np.clip(tax,0,.6) if finite(tax) else np.nan
        dso = safe_div(b["Accounts Receivable"],rev)*365
        dio = safe_div(b["Inventory"],i["COGS"])*365
        dpo = safe_div(b["Accounts Payable"],i["COGS"])*365
        margin = safe_div(i["Net Income"],rev)
        turnover = safe_div(rev,avg_assets)
        multiplier = safe_div(avg_assets,avg_equity) if avg_equity>0 else np.nan
        columns[col] = {
            "Revenue growth": safe_div(rev,income.iloc[:,n-1]["Revenue"])-1 if n else np.nan,
            "Gross margin": safe_div(i["Gross Profit"],rev), "EBITDA margin": safe_div(i["EBITDA"],rev),
            "EBIT margin": safe_div(i["EBIT"],rev), "Net margin": margin,"FCF margin": safe_div(c["FCF"],rev),
            "ROE": safe_div(i["Net Income"],avg_equity) if avg_equity>0 else np.nan,
            "ROA": safe_div(i["Net Income"],avg_assets),
            "ROIC": safe_div(i["EBIT"]*(1-tax),invested) if invested>0 else np.nan,
            "Current ratio": safe_div(b["Current Assets"],b["Current Liabilities"]),
            "Quick ratio": safe_div(b["Cash"]+b["Accounts Receivable"],b["Current Liabilities"]),
            "Debt / EBITDA": safe_div(b["Debt"],i["EBITDA"]) if i["EBITDA"]>0 else np.nan,
            "Net Debt / EBITDA": safe_div(b["Debt"]-b["Cash"],i["EBITDA"]) if i["EBITDA"]>0 else np.nan,
            "Interest coverage": safe_div(i["EBIT"],i["Interest Expense"]) if i["Interest Expense"]>0 else np.nan,
            "Asset turnover": turnover, "Receivable days": dso,"Inventory days": dio,"Payable days": dpo,
            "Cash conversion cycle": dso+dio-dpo,"FCF conversion": safe_div(c["FCF"],i["Net Income"]) if i["Net Income"]>0 else np.nan,
            "Equity multiplier": multiplier,"DuPont ROE": margin*turnover*multiplier,
        }
    return pd.DataFrame(columns)
