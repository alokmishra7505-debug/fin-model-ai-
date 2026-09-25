import numpy as np
import pandas as pd
from .utils import safe_float, bounded

class ValuationAgent:
    name = "Valuation Agent"

    def compute_wacc(self, info: dict, hist: pd.DataFrame, risk_free=0.043, erp=0.055):
        beta = safe_float(info.get("beta"), 1.0)
        mcap = safe_float(info.get("marketCap"), np.nan)
        debt = abs(float(hist.loc["Total Debt"].iloc[-1]))
        interest = abs(float(hist.loc["Interest Expense"].iloc[-1]))
        tax = 0.24
        pretax = float(hist.loc["Pretax Income"].iloc[-1])
        tax_exp = float(hist.loc["Tax"].iloc[-1])
        if pretax > 0:
            tax = bounded(tax_exp/pretax, 0, .45, .24)
        cost_equity = risk_free + beta * erp
        cost_debt = bounded(interest/debt if debt > 0 else 0.05, 0.01, 0.15, 0.05)
        if not np.isfinite(mcap) or mcap <= 0:
            mcap = max(1.0, abs(float(hist.loc["Equity"].iloc[-1])))
        total = mcap + debt
        wacc = (mcap/total)*cost_equity + (debt/total)*cost_debt*(1-tax)
        return bounded(wacc, 0.05, 0.20, 0.10)

    def dcf(self, info, hist, forecast, terminal_growth=0.025, risk_free=0.043, erp=0.055):
        wacc = self.compute_wacc(info, hist, risk_free, erp)
        rev = forecast.loc["Revenue"]
        ebit = forecast.loc["EBIT"]
        tax_rate = 0.24
        pretax = forecast.loc["Pretax Income"].replace(0, np.nan)
        tr = (forecast.loc["Tax"] / pretax).replace([np.inf,-np.inf],np.nan).dropna()
        if len(tr): tax_rate = bounded(tr.median(), 0, .45, .24)
        da = forecast.loc["D&A"]
        capex = forecast.loc["Capex"]
        nwc = forecast.loc["Accounts Receivable"] + forecast.loc["Inventory"] - forecast.loc["Accounts Payable"]
        hist_nwc = float(hist.loc["Accounts Receivable"].iloc[-1] + hist.loc["Inventory"].iloc[-1] - hist.loc["Accounts Payable"].iloc[-1])
        deltas = nwc.diff()
        deltas.iloc[0] = nwc.iloc[0] - hist_nwc
        ufcf = ebit*(1-tax_rate) + da + capex - deltas
        pv = 0.0
        for i,v in enumerate(ufcf.values, start=1):
            pv += float(v)/((1+wacc)**i)
        tg = min(terminal_growth, wacc-0.01)
        tv = float(ufcf.iloc[-1])*(1+tg)/(wacc-tg)
        pv_tv = tv/((1+wacc)**len(ufcf))
        debt = abs(float(hist.loc["Total Debt"].iloc[-1]))
        cash = float(hist.loc["Cash"].iloc[-1])
        ev = pv + pv_tv
        eq = ev - debt + cash
        shares = safe_float(info.get("sharesOutstanding"), np.nan)
        price = eq/shares if np.isfinite(shares) and shares > 0 else np.nan
        return {"WACC":wacc,"Terminal Growth":tg,"PV Forecast FCF":pv,"PV Terminal Value":pv_tv,"Enterprise Value":ev,"Equity Value":eq,"Implied Price":price,"UFCF":ufcf}

    def sensitivity(self, info, hist, forecast):
        rows=[]
        for w in np.arange(0.07,0.131,0.01):
            for g in np.arange(0.01,0.041,0.005):
                base=self.dcf(info,hist,forecast,terminal_growth=float(g))
                # recompute quickly using selected WACC
                u=base["UFCF"]; tg=min(g,w-0.01)
                pv=sum(float(v)/((1+w)**i) for i,v in enumerate(u.values,1))
                tv=float(u.iloc[-1])*(1+tg)/(w-tg)
                ev=pv+tv/((1+w)**len(u))
                eq=ev-abs(float(hist.loc["Total Debt"].iloc[-1]))+float(hist.loc["Cash"].iloc[-1])
                shares=safe_float(info.get("sharesOutstanding"),np.nan)
                price=eq/shares if np.isfinite(shares) and shares>0 else np.nan
                rows.append({"WACC":w,"Terminal Growth":g,"Implied Price":price})
        return pd.DataFrame(rows)
