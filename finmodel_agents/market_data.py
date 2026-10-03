from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
import json
import logging
import pandas as pd
import yfinance as yf
from .utils import finite
from .nse_data import NSEArchiveAgent, ISSUERS, FILING_REGISTRY, LISTING_URL

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
    provenance: list = field(default_factory=list)

    @property
    def currency(self):
        return self.info.get("financialCurrency") or self.info.get("currency") or ("INR" if self.ticker.endswith((".NS",".BO")) else "")

    @property
    def name(self):
        return self.info.get("longName") or self.info.get("shortName") or self.ticker


class MarketDataAgent:
    def fetch(self, ticker, use_cache=True):
        obj = yf.Ticker(ticker)
        warnings = []
        provenance = []

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
        profile_missing = not info.get("longName") or not info.get("financialCurrency")
        if ticker.endswith(".NS"):
            symbol = ticker[:-3]
            nse = NSEArchiveAgent(ROOT/"data"/"cache"/"nse")
            if profile_missing:
                identity = read("NSE issuer listing",lambda:nse.profile(symbol),{})
                for key,value in identity.items():
                    if not info.get(key):
                        info[key] = value
                if identity:
                    provenance.append({"Field":"Issuer name / exchange / quote currency","Source":"NSE equity listing","As of":"Retrieved with model","URL":LISTING_URL})
                for key,value in ISSUERS.get(symbol,{}).items():
                    if not info.get(key):
                        info[key] = value
                if symbol in ISSUERS:
                    provenance.append({"Field":"Issuer reporting currency / identity","Source":"NSE filed annual results","As of":"2026-03-31","URL":FILING_REGISTRY[symbol]})
            if income.empty or balance.empty or cashflow.empty or not finite(info.get("sharesOutstanding")):
                filing = read("NSE annual filing",lambda:nse.annual_filing(symbol),None)
                if filing:
                    profile,official_is,official_bs,official_cf,url = filing
                    for key,value in profile.items():
                        if not info.get(key) or (key=="sharesOutstanding" and not finite(info.get(key))):
                            info[key]=value
                    # Use a consistent whole-period filing when Yahoo statements are missing.
                    if income.empty or balance.empty or cashflow.empty:
                        income,balance,cashflow = official_is,official_bs,official_cf
                        warnings.append("Historical statements use the available full-year consolidated NSE filing. A separate service-company COGS / gross-profit split is not supplied by this filing.")
                    provenance.append({"Field":"Annual financials / shares fallback","Source":"NSE consolidated IndAS filing","As of":str(official_is.columns[0].date()),"URL":url})
            if not finite(info.get("currentPrice")) and not finite(info.get("regularMarketPrice")):
                quote = read("NSE closing-price archive",lambda:nse.closing_quote(symbol),{})
                info.update(quote)
                if quote:
                    provenance.append({"Field":"Market price","Source":"NSE daily closing-price archive","As of":quote["priceAsOf"],"URL":quote["priceSourceUrl"]})
            if not info.get("financialCurrency"):
                info["financialCurrency"]="INR"
                warnings.append("Reporting currency defaults to INR for this NSE-listed company. Verify it against its financial filing before external use.")
            info.setdefault("exchange","NSE")
            info.setdefault("currency","INR")
        # A genuine period-end share count is preferable to an invented current value.
        if (not finite(info.get("sharesOutstanding")) or info.get("sharesBasis")) and "Ordinary Shares Number" in balance.index:
            shares = balance.loc["Ordinary Shares Number"].dropna().sort_index()
            if len(shares) and shares.iloc[-1]>0:
                info["sharesOutstanding"] = float(shares.iloc[-1])
                info["sharesAsOf"] = str(pd.Timestamp(shares.index[-1]).date())
                info["sharesBasis"] = "Latest reported period-end ordinary shares; held constant in the model"
        if not finite(info.get("currentPrice")) and finite(info.get("regularMarketPrice")):
            info["currentPrice"]=info["regularMarketPrice"]
        if not finite(info.get("marketCap")) and finite(info.get("currentPrice")) and finite(info.get("sharesOutstanding")):
            info["marketCap"] = info["currentPrice"]*info["sharesOutstanding"]
            warnings.append("Market capitalization is calculated from the sourced price and share count; see their dates and bases in Sources.")
        if not info.get("longName"):
            warnings.append("Company profile was not returned. The exchange ticker identifies this model; no company metadata has been invented.")
        if not finite(info.get("currentPrice")):
            warnings.append("A market quote is unavailable from the accessible sources. Forecast statements still work; enter a sourced quote in Market inputs if valuation is needed.")
        if info.get("sharesBasis"):
            warnings.append(info["sharesBasis"]+" ("+info.get("sharesAsOf", "date unavailable")+").")
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
                          datetime.now(timezone.utc).isoformat(timespec="seconds"), warnings,
                          source="Yahoo Finance"+(" + official NSE archives" if provenance else " via yfinance"),provenance=provenance)
        if not income.empty:
            self._save(data)
        return data

    def _save(self, data):
        try:
            directory = ROOT / "data" / "cache" / data.ticker
            directory.mkdir(parents=True, exist_ok=True)
            meta = {"ticker": data.ticker, "info": data.info, "retrieved_at": data.retrieved_at,
                    "warnings": data.warnings, "source": data.source,"provenance":data.provenance}
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
