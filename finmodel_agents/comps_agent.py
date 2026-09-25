import numpy as np
import pandas as pd
import yfinance as yf


class CompsAgent:
    name = "Trading Comps Agent"

    def run(self, peer_tickers):
        peers = [p.strip().upper() for p in (peer_tickers or []) if p and p.strip()]
        rows = []
        for ticker in peers:
            try:
                info = yf.Ticker(ticker).info or {}
                rows.append({
                    "Ticker": ticker,
                    "Company": info.get("shortName") or info.get("longName") or ticker,
                    "Market Cap": info.get("marketCap"),
                    "Enterprise Value": info.get("enterpriseValue"),
                    "Trailing P/E": info.get("trailingPE"),
                    "Forward P/E": info.get("forwardPE"),
                    "EV/Revenue": info.get("enterpriseToRevenue"),
                    "EV/EBITDA": info.get("enterpriseToEbitda"),
                    "Price/Book": info.get("priceToBook"),
                })
            except Exception:
                continue
        return pd.DataFrame(rows)

    def summary(self, comps: pd.DataFrame):
        if comps is None or comps.empty:
            return {}
        numeric = ["Trailing P/E", "Forward P/E", "EV/Revenue", "EV/EBITDA", "Price/Book"]
        out = {}
        for c in numeric:
            s = pd.to_numeric(comps[c], errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
            if len(s): out[c] = {"Median": float(s.median()), "25th": float(s.quantile(.25)), "75th": float(s.quantile(.75))}
        return out
