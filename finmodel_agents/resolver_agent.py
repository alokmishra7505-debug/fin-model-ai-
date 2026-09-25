import re
import yfinance as yf


class CompanyResolverAgent:
    name = "Company Resolver Agent"

    def resolve(self, query: str) -> dict:
        q = (query or "").strip()
        if not q:
            raise ValueError("Enter a company name or ticker.")

        # Obvious ticker inputs should not be unnecessarily searched.
        if re.fullmatch(r"[A-Za-z0-9.\-^=]{1,20}", q) and " " not in q and (q == q.upper() or "." in q or "-" in q or "^" in q):
            return {"query": q, "ticker": q.upper(), "name": q.upper(), "exchange": None, "source": "direct ticker"}

        try:
            search = yf.Search(q, max_results=10, news_count=0)
            quotes = getattr(search, "quotes", None) or []
            equities = [x for x in quotes if str(x.get("quoteType", "")).upper() in {"EQUITY", "ETF"}]
            candidates = equities or quotes
            if candidates:
                x = candidates[0]
                symbol = x.get("symbol")
                if symbol:
                    return {
                        "query": q,
                        "ticker": symbol.upper(),
                        "name": x.get("longname") or x.get("shortname") or symbol,
                        "exchange": x.get("exchange"),
                        "source": "Yahoo Finance search",
                    }
        except Exception:
            pass
        raise ValueError(f"Could not resolve '{q}' to a listed ticker. Try a ticker such as AAPL or RELIANCE.NS.")
