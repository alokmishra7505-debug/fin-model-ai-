import re
import yfinance as yf

ALIASES = {
    "APPLE": "AAPL", "APPLE INC": "AAPL", "MICROSOFT": "MSFT", "NVIDIA": "NVDA",
    "RELIANCE": "RELIANCE.NS", "RELIANCE INDUSTRIES": "RELIANCE.NS",
    "TCS": "TCS.NS", "TATA CONSULTANCY SERVICES": "TCS.NS",
    "ASIAN PAINTS": "ASIANPAINT.NS", "HDFC BANK": "HDFCBANK.NS",
}


def resolve(query):
    value = query.strip().upper()
    if not value:
        raise ValueError("Enter a company name or exchange ticker.")
    if value in ALIASES:
        return ALIASES[value]
    if re.fullmatch(r"[A-Z0-9^][A-Z0-9.^=\-]{0,24}", value):
        return value
    try:
        quotes = yf.Search(query, max_results=5, news_count=0).quotes
        matches = [q for q in quotes if q.get("quoteType") == "EQUITY"]
        if matches:
            return matches[0]["symbol"]
    except Exception:
        pass
    raise ValueError("No listed company match found. Try the exact exchange ticker, such as RELIANCE.NS.")
