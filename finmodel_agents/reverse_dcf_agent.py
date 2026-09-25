import numpy as np


class ReverseDCFAgent:
    name = "Reverse DCF Agent"

    def run(self, valuation_agent, info, hist, forecast, target_price=None, terminal_growth=0.025):
        try:
            target = float(target_price if target_price is not None else info.get("currentPrice") or info.get("regularMarketPrice"))
            shares = float(info.get("sharesOutstanding"))
        except Exception:
            return {"Target Price": np.nan, "Implied UFCF Scale": np.nan}
        if not np.isfinite(target) or not np.isfinite(shares) or shares <= 0:
            return {"Target Price": np.nan, "Implied UFCF Scale": np.nan}

        base = valuation_agent.dcf(info, hist, forecast, terminal_growth=terminal_growth)
        u = base["UFCF"]
        w = base["WACC"]
        g = min(terminal_growth, w-0.01)
        debt = abs(float(hist.loc["Total Debt"].iloc[-1])); cash = float(hist.loc["Cash"].iloc[-1])
        target_ev = target*shares + debt - cash
        unit_pv = sum(float(v)/((1+w)**i) for i,v in enumerate(u.values,1))
        unit_tv = float(u.iloc[-1])*(1+g)/(w-g)/((1+w)**len(u))
        denom = unit_pv + unit_tv
        scale = target_ev/denom if denom else np.nan
        return {"Target Price": target, "Implied UFCF Scale": scale, "Interpretation": "~1.0 means market price is close to the base-case DCF cash-flow path."}
