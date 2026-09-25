import pandas as pd


class ConsensusAgent:
    name = "Consensus Estimates Agent"

    def run(self, ticker_obj):
        out = {}
        for label, attr in [
            ("Revenue Estimate", "revenue_estimate"),
            ("Earnings Estimate", "earnings_estimate"),
            ("Growth Estimates", "growth_estimates"),
            ("EPS Trend", "eps_trend"),
        ]:
            try:
                value = getattr(ticker_obj, attr)
                if isinstance(value, pd.DataFrame) and not value.empty:
                    out[label] = value.copy()
            except Exception:
                continue
        return out
