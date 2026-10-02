from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
import json
import logging
import pandas as pd
import yfinance as yf
from .utils import finite

ROOT = Path(__file__).resolve().parents[1]
yf.set_tz_cache_location(str(ROOT / "data" / "cache" / "yfinance"))


@dataclass
class MarketData:
    ticker: str
    info: dict
    income: pd.DataFrame
    balance: pd.DataFrame
    cashflow: pd.DataFrame
    estimates: dict = field(default_factory=dict)
    retrieved_at: str = ""
    warnings: list = field(default_factory=list)
    source: str = "Yahoo Finance via yfinance"
    cached: bool = False

    @property
    def currency(self):
        return self.info.get("financialCurrency") or self.info.get("currency") or "Unknown"

    @property
    def name(self):
        return self.info.get("longName") or self.info.get("shortName") or self.ticker


class MarketDataAgent:
    def fetch(self, ticker, use_cache=True):
        obj = yf.Ticker(ticker)
        warnings = []

        def read(label, fn, default):
            try:
                result = fn()
                return result if result is not None else default
            except Exception:
                logging.getLogger(__name__).exception("Data fetch failed for %s: %s", ticker, label)
                warnings.append(f"{label} is unavailable from the public source.")
                return default

        info = read("Company profile", lambda: obj.info, {})
        income = read("Income statement", lambda: obj.income_stmt, pd.DataFrame())
        balance = read("Balance sheet", lambda: obj.balance_sheet, pd.DataFrame())
        cashflow = read("Cash flow", lambda: obj.cashflow, pd.DataFrame())
        estimates = {}
        if not income.empty:
            for label, prop in (("Revenue estimates", "revenue_estimate"), ("EPS estimates", "earnings_estimate")):
                frame = read(label, lambda p=prop: getattr(obj, p), pd.DataFrame())
                if isinstance(frame, pd.DataFrame) and not frame.empty:
                    estimates[label] = frame
        if income.empty and use_cache:
            cached = self._load(ticker)
            if cached:
                cached.cached = True
                cached.warnings.append("Live annual data was unavailable. Showing the last successful local snapshot; check its retrieval date.")
                return cached
        if income.empty:
            warnings.append("Annual financial statements are unavailable. Retry later or use another ticker; no financial values have been invented.")
        if not info.get("financialCurrency") and info.get("currency"):
            warnings.append("Reporting currency was not supplied; quote currency is used as a labelled fallback.")
        if not finite(info.get("currentPrice")) and finite(info.get("regularMarketPrice")):
            info["currentPrice"] = info["regularMarketPrice"]
        data = MarketData(ticker, info, income, balance, cashflow, estimates,
                          datetime.now(timezone.utc).isoformat(timespec="seconds"), warnings)
        if not income.empty:
            self._save(data)
        return data

    def _save(self, data):
        try:
            directory = ROOT / "data" / "cache" / data.ticker
            directory.mkdir(parents=True, exist_ok=True)
            meta = {"ticker": data.ticker, "info": data.info, "retrieved_at": data.retrieved_at,
                    "warnings": data.warnings, "source": data.source}
            (directory / "metadata.json").write_text(json.dumps(meta, default=str))
            for name in ("income", "balance", "cashflow"):
                getattr(data, name).to_csv(directory / f"{name}.csv")
        except OSError:
            logging.getLogger(__name__).warning("Local snapshot could not be saved")

    def _load(self, ticker):
        directory = ROOT / "data" / "cache" / ticker
        try:
            meta = json.loads((directory / "metadata.json").read_text())
            frames = {}
            for name in ("income", "balance", "cashflow"):
                frames[name] = pd.read_csv(directory / f"{name}.csv", index_col=0)
                frames[name].columns = pd.to_datetime(frames[name].columns)
            return MarketData(**meta, **frames)
        except (OSError, ValueError, KeyError, pd.errors.EmptyDataError):
            return None
