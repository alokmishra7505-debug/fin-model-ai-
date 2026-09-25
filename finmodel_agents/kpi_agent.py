import numpy as np
import pandas as pd

class KPIAgent:
    name = "KPI & Risk Agent"

    def run(self, model: pd.DataFrame):
        rev=model.loc["Revenue"].replace(0,np.nan)
        metrics=pd.DataFrame(index=model.columns)
        metrics["Revenue Growth"] = rev.pct_change().values
        metrics["Gross Margin"] = (model.loc["Gross Profit"]/rev).values
        metrics["EBITDA Margin"] = (model.loc["EBITDA"]/rev).values
        metrics["EBIT Margin"] = (model.loc["EBIT"]/rev).values
        metrics["Net Margin"] = (model.loc["Net Income"]/rev).values
        metrics["FCF"] = (model.loc["CFO"]+model.loc["Capex"]).values
        metrics["FCF Margin"] = (metrics["FCF"].values/rev.values)
        metrics["Debt / EBITDA"] = (model.loc["Total Debt"]/model.loc["EBITDA"].replace(0,np.nan)).values
        metrics["Current Ratio"] = (model.loc["Current Assets"]/model.loc["Current Liabilities"].replace(0,np.nan)).values
        metrics["ROE"] = (model.loc["Net Income"]/model.loc["Equity"].replace(0,np.nan)).values
        metrics["ROA"] = (model.loc["Net Income"]/model.loc["Total Assets"].replace(0,np.nan)).values
        return metrics.replace([np.inf,-np.inf],np.nan)

    def flags(self, kpis: pd.DataFrame):
        flags=[]
        last=kpis.iloc[-1]
        if last.get("Debt / EBITDA",0) > 4: flags.append("High leverage: Debt/EBITDA above 4x")
        if last.get("Current Ratio",99) < 1: flags.append("Liquidity risk: current ratio below 1x")
        if last.get("FCF Margin",0) < 0: flags.append("Negative free cash flow margin")
        if last.get("Net Margin",0) < 0: flags.append("Negative net margin")
        if not flags: flags.append("No major rule-based red flags triggered")
        return flags
