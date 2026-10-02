import pandas as pd
from .utils import finite


def risk_flags(kpis, hist, forecast, valuation):
    flags = []
    def add(condition, level, title, detail):
        if condition:
            flags.append({"Severity":level,"Flag":title,"Observation":detail})
    if not kpis.empty:
        last = kpis[hist.years[-1]]
        add(last["Revenue growth"]<0,"Watch","Declining revenue","Latest annual revenue is below the prior period.")
        if len(hist.years)>1:
            prior = kpis[hist.years[-2]]
            add(last["EBITDA margin"]<prior["EBITDA margin"],"Watch","Margin contraction","Latest EBITDA margin is below the prior period.")
            add(last["Cash conversion cycle"]-prior["Cash conversion cycle"]>15,"Watch","Working capital deterioration","Cash conversion cycle increased by more than 15 days.")
        add(last["FCF margin"]<.05,"Watch","Weak free cash flow","Latest annual FCF margin is below 5%.")
        add(last["Debt / EBITDA"]>3,"High","High leverage","Latest debt / EBITDA exceeds 3.0x.")
        add(last["Interest coverage"]<2,"High","Low interest coverage","Latest EBIT / interest expense is below 2.0x.")
        add(hist.cashflow.iloc[:,-1]["FCF"]<0,"High","Negative free cash flow","Latest annual free cash flow is negative.")
    if forecast:
        a = forecast.assumptions
        add(a.growth>.15 or a.ebitda_margin>.5 or a.terminal_growth>.04,"Watch","Aggressive assumptions","Growth, EBITDA margin or terminal growth exceeds a conservative screening threshold.")
        add(forecast.cashflow.loc["Funding Draw"].sum()>1,"Watch","Additional financing required","The forecast includes explicit debt funding draws to maintain minimum cash.")
        add((forecast.cashflow.loc["FCF"]<0).any(),"High","Negative forecast FCF","At least one forecast year generates negative free cash flow.")
        add(forecast.balance.loc["Balance Check"].abs().max()>1,"High","Forecast balance imbalance","Forecast assets do not equal liabilities plus equity.")
    if valuation.values:
        add(valuation.values["Terminal Value Weight"]>.75,"Watch","Terminal-value dependence","More than 75% of enterprise value comes from the terminal value.")
        add(valuation.values["Equity Value"]<=0,"High","Non-positive equity value","DCF enterprise value does not cover the net debt and other claims bridge.")
    else:
        add(True,"Review","Valuation unavailable",valuation.message or "Insufficient valuation inputs.")
    if hist.balance.loc["Balance Check"].abs().max()>1:
        add(True,"High","Historical balance imbalance","At least one reported annual balance sheet has a non-zero reconciliation.")
    if not flags:
        flags.append({"Severity":"Clear","Flag":"No screening thresholds triggered","Observation":"This is a limited rule-based screen, not an assessment of every investment risk."})
    return pd.DataFrame(flags)
