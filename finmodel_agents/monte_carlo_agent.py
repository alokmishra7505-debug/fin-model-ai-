import numpy as np


class MonteCarloAgent:
    name = "Monte Carlo Valuation Agent"

    def run(self, valuation_agent, info, hist, base_forecast, assumptions, simulations=500, seed=42):
        rng = np.random.default_rng(seed)
        prices = []
        base_wacc = valuation_agent.compute_wacc(info, hist, assumptions.get("risk_free_rate", .043), assumptions.get("equity_risk_premium", .055))
        base_g = assumptions.get("terminal_growth", .025)
        ufcf = valuation_agent.dcf(info, hist, base_forecast, terminal_growth=base_g,
                                   risk_free=assumptions.get("risk_free_rate", .043),
                                   erp=assumptions.get("equity_risk_premium", .055))["UFCF"]
        debt = abs(float(hist.loc["Total Debt"].iloc[-1])); cash = float(hist.loc["Cash"].iloc[-1])
        shares = info.get("sharesOutstanding")
        try: shares = float(shares)
        except Exception: shares = np.nan
        if not np.isfinite(shares) or shares <= 0:
            return {"count": 0, "p10": np.nan, "p50": np.nan, "p90": np.nan, "mean": np.nan}

        for _ in range(int(simulations)):
            w = float(np.clip(rng.normal(base_wacc, 0.0125), 0.04, 0.25))
            g = float(np.clip(rng.normal(base_g, 0.0075), -0.01, min(0.06, w - 0.01)))
            cf_scale = float(np.clip(rng.normal(1.0, 0.10), 0.65, 1.35))
            u = ufcf * cf_scale
            pv = sum(float(v)/((1+w)**i) for i,v in enumerate(u.values,1))
            tv = float(u.iloc[-1])*(1+g)/(w-g)
            eq = pv + tv/((1+w)**len(u)) - debt + cash
            prices.append(eq/shares)
        arr = np.array(prices)
        return {"count": len(arr), "p10": float(np.nanpercentile(arr,10)), "p50": float(np.nanpercentile(arr,50)), "p90": float(np.nanpercentile(arr,90)), "mean": float(np.nanmean(arr))}
