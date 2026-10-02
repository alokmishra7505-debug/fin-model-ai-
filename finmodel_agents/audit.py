import numpy as np
import pandas as pd
from .utils import finite


def audit_model(hist, forecast, valuation):
    rows = []
    def record(name,status,detail):
        rows.append({"Check":name,"Status":status,"Detail":detail})
    checks = hist.balance.loc["Balance Check"].dropna()
    record("Historical balance sheet", "PASS" if len(checks) and checks.abs().max()<=1 else "REVIEW", "Reported assets less liabilities and total equity; missing periods require review.")
    missing = int(hist.income.isna().sum().sum()+hist.balance.isna().sum().sum()+hist.cashflow.isna().sum().sum())
    record("Source completeness","PASS" if missing==0 else "REVIEW",f"{missing} unavailable historical cells; see historical disclosures.")
    if forecast:
        for name,frame,row in (("Forecast balance sheet",forecast.balance,"Balance Check"),("Cash flow reconciliation",forecast.cashflow,"Cash Reconciliation")):
            error = frame.loc[row].abs().max()
            record(name,"PASS" if finite(error) and error<=1 else "FAIL",f"Maximum absolute difference: {error:,.4f} reporting-currency units.")
        expected = [pd.Timestamp(hist.years[-1])+pd.DateOffset(years=n) for n in range(1,len(forecast.income.columns)+1)]
        record("Forecast period continuity","PASS" if list(pd.to_datetime(forecast.income.columns))==expected else "FAIL","Annual forecast periods follow the latest actual fiscal period.")
        cash_delta = forecast.cashflow.loc["Closing Cash"].diff().iloc[1:] - forecast.cashflow.loc["Net Cash Change"].iloc[1:]
        record("Cash roll-forward","PASS" if cash_delta.abs().max()<=1 else "FAIL","Consecutive closing cash balances reconcile to net cash movement.")
        valid = all(not np.isinf(frame.to_numpy(dtype=float)).any() for frame in (forecast.income,forecast.balance,forecast.cashflow))
        record("No infinite calculations","PASS" if valid else "FAIL","Undefined ratios and per-share values are N/A, never infinity.")
    else:
        record("Forecast availability","REVIEW","A forecast could not be built from the available inputs.")
    if valuation.values:
        v = valuation.values
        record("Terminal growth below WACC","PASS" if v["WACC"]>v["Terminal Growth"] else "FAIL","Gordon growth requires a positive discount-rate spread.")
        record("DCF sanity","PASS" if v["Equity Value"]>0 and finite(v["Implied Price"]) and v["Implied Price"]>0 else "REVIEW","Positive equity and per-share value are required for an interpretable DCF.")
    else:
        record("DCF availability","REVIEW",valuation.message)
    return pd.DataFrame(rows)
