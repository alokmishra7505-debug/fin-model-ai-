from dataclasses import dataclass
from datetime import datetime, timezone
import pandas as pd
import yfinance as yf
from .utils import annualize_columns

@dataclass
class CompanyData:
    ticker: str
    info: dict
    income: pd.DataFrame
    balance: pd.DataFrame
    cashflow: pd.DataFrame
    price_history: pd.DataFrame
    timestamp_utc: str

class MarketDataAgent:
    name = "Market Data Agent"

    def fetch(self, ticker: str) -> CompanyData:
        t = yf.Ticker(ticker.strip())
        info = t.info or {}
        income = annualize_columns(t.financials)
        balance = annualize_columns(t.balance_sheet)
        cashflow = annualize_columns(t.cashflow)
        hist = t.history(period="5y", auto_adjust=False)
        if income is None or income.empty:
            raise ValueError(f"No annual financial statements found for {ticker}.")
        return CompanyData(
            ticker=ticker.upper().strip(), info=info,
            income=income, balance=balance, cashflow=cashflow,
            price_history=hist,
            timestamp_utc=datetime.now(timezone.utc).isoformat()
        )
