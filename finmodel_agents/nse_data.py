"""Official NSE public archives. No authenticated feeds, proxies or access-control bypasses."""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from io import BytesIO, StringIO
from pathlib import Path
from zipfile import ZipFile
import logging
import numpy as np
import pandas as pd
import requests
from lxml import html
from .utils import finite, safe_div

LISTING_URL = "https://nsearchives.nseindia.com/content/equities/EQUITY_L.csv"
FILING_REGISTRY = {
    "TCS": "https://nsearchives.nseindia.com/corporate/ixbrl/INTEGRATED_FILING_INDAS_150312_09042026234218_iXBRL_WEB.html",
}
# Stable issuer identity, not financial numbers. Currency confirmed by the linked filing.
ISSUERS = {"TCS": {"longName": "Tata Consultancy Services Limited", "sector": "Technology",
                   "industry": "Information Technology Services", "financialCurrency": "INR"}}


def number(text):
    value = str(text).strip().replace(",", "")
    if value.startswith("(") and value.endswith(")"):
        value = "-" + value[1:-1]
    try:
        value = float(value)
        return value if finite(value) else np.nan
    except (TypeError, ValueError):
        return np.nan


def parse_indas_filing(content, symbol):
    """Validate issuer, consolidated basis, units and full-year duration before mapping."""
    root = html.fromstring(content)
    tables = []
    for table in root.xpath("//table"):
        rows = [[" ".join(cell.text_content().split()) for cell in row.xpath("./td|./th")]
                for row in table.xpath("./thead/tr|./tbody/tr|./tr")]
        tables.append([row for row in rows if row])
    meta = dict(row for rows in tables[:1] for row in rows if len(row) == 2)
    if meta.get("NSE Symbol", "").upper() != symbol.upper():
        raise ValueError("NSE filing issuer does not match the requested ticker.")
    if meta.get("Nature of report standalone or consolidated") != "Consolidated":
        raise ValueError("Only consolidated NSE filings are supported by this model.")
    currency = meta.get("Description of presentation currency")
    scales = {"lakhs": 1e5, "lakh": 1e5, "crores": 1e7, "crore": 1e7, "millions": 1e6, "rupees": 1}
    scale = scales.get(meta.get("Level of rounding used in financial results", "").lower())
    if currency != "INR" or scale is None:
        raise ValueError("NSE filing currency or unit is unsupported; no scaling has been guessed.")

    def find_table(label):
        for rows in tables[1:]:
            if any(label in row for row in rows):
                return rows
        raise ValueError(f"NSE filing lacks {label}.")

    incrows = find_table("Revenue from operations")
    bsrows = find_table("Total assets")
    cfrows = find_table("Net cash flows from (used in) operating activities")

    def row_value(rows, label):
        for row in rows:
            if label in row:
                return row[-1]
        return ""

    period = pd.to_datetime(row_value(incrows, "Date of end of reporting period"), format="%d-%m-%Y")
    start = pd.to_datetime(row_value(incrows, "Date of start of reporting period"), format="%d-%m-%Y")
    if not 330 <= (period-start).days <= 375:
        raise ValueError("NSE year-to-date column is not a full financial year.")
    for rows in (bsrows, cfrows):
        if row_value(rows, "Date of end of reporting period") != period.strftime("%d-%m-%Y"):
            raise ValueError("NSE statements have inconsistent reporting periods.")

    cf_start = pd.to_datetime(row_value(cfrows,"Date of start of reporting period"),format="%d-%m-%Y")
    if not 330 <= (period-cf_start).days <= 375:
        raise ValueError("NSE cash flow does not cover a full year.")

    def get(rows, label, per_share=False):
        return number(row_value(rows, label)) * (1 if per_share else scale)

    income_map = {"Total Revenue": "Revenue from operations", "Pretax Income": "Total profit before tax",
        "Tax Provision": "Total tax expenses", "Net Income": "Profit or loss, attributable to owners of parent",
        "Interest Expense": "Finance costs", "Reconciled Depreciation": "Depreciation, depletion and amortisation expense"}
    inc = {k: get(incrows,v) for k,v in income_map.items()}
    inc["Diluted EPS"] = get(incrows, "Diluted earnings (loss) per share from continuing and discontinued operations", True)
    # Excludes other income and exceptional items; does not invent a service-company COGS split.
    inc["Operating Income"] = get(incrows,"Total profit before exceptional items and tax") + inc["Interest Expense"] - get(incrows,"Other income")
    inc["EBITDA"] = inc["Operating Income"] + inc["Reconciled Depreciation"]
    bs_map = {"Cash And Cash Equivalents": "Cash and cash equivalents", "Accounts Receivable": "Trade receivables, current",
        "Inventory": "Inventories", "Current Assets": "Total current assets", "Net PPE": "Property, plant and equipment",
        "Total Assets": "Total assets", "Current Liabilities": "Total current liabilities",
        "Total Liabilities Net Minority Interest": "Total liabilities", "Total Equity Gross Minority Interest": "Total equity",
        "Stockholders Equity": "Total equity attributable to owners of parent", "Minority Interest": "Non controlling interest"}
    bs = {k:get(bsrows,v) for k,v in bs_map.items()}
    bs["Cash Cash Equivalents And Short Term Investments"] = bs["Cash And Cash Equivalents"] + get(bsrows,"Current investments")
    def section_values(label):
        return [number(row[-1])*scale for row in bsrows if label in row and finite(number(row[-1]))]
    payable = section_values("Total Trade payable")
    bs["Accounts Payable"] = payable[-1] if payable else np.nan
    leases = section_values("Lease liabilities")
    bs["Current Debt"] = get(bsrows,"Borrowings, current") + (leases[-1] if len(leases)==2 else 0)
    bs["Long Term Debt"] = get(bsrows,"Borrowings, non-current") + (leases[0] if len(leases)==2 else 0)
    bs["Total Debt"] = bs["Current Debt"] + bs["Long Term Debt"]
    cf = {"Operating Cash Flow":get(cfrows,"Net cash flows from (used in) operating activities"),
          "Capital Expenditure":-get(cfrows,"Purchase of property, plant and equipment")-get(cfrows,"Purchase of intangible assets"),
          "Depreciation And Amortization":get(cfrows,"Adjustments for depreciation and amortisation expense"),
          "Cash Dividends Paid":-get(cfrows,"Dividends paid"),
          "Net Issuance Payments Of Debt":get(cfrows,"Proceeds from borrowings")-get(cfrows,"Repayments of borrowings")-get(cfrows,"Payments of lease liabilities")}
    cf["Free Cash Flow"] = cf["Operating Cash Flow"] + cf["Capital Expenditure"]
    shares = safe_div(get(incrows,"Paid-up equity share capital"),get(incrows,"Face value of equity share capital",True))
    profile = {"longName":meta["Name of company"],"financialCurrency":currency,"currency":"INR","exchange":"NSE",
               "sharesOutstanding":shares,"sharesAsOf":period.strftime("%Y-%m-%d"),
               "sharesBasis":"Period-end shares estimated from rounded reported paid-up capital / face value"}
    return profile, pd.DataFrame({period:inc}), pd.DataFrame({period:bs}), pd.DataFrame({period:cf})


class NSEArchiveAgent:
    def __init__(self, cache_dir):
        self.cache_dir = Path(cache_dir)
        self.session = requests.Session()
        self.session.headers.update({"User-Agent":"FinModelAI/1.0 public financial research", "Accept":"*/*"})

    def download(self,url,cache_name,ttl_hours=24):
        path = self.cache_dir/cache_name
        if path.exists() and datetime.now().timestamp()-path.stat().st_mtime < ttl_hours*3600:
            return path.read_bytes()
        response = self.session.get(url,timeout=(4,8))
        response.raise_for_status()
        content = response.content
        self.cache_dir.mkdir(parents=True,exist_ok=True)
        path.write_bytes(content)
        return content

    def profile(self,symbol):
        content = self.download(LISTING_URL,"equity-list.csv")
        frame = pd.read_csv(BytesIO(content))
        frame.columns = frame.columns.str.strip()
        matches = frame[frame["SYMBOL"].str.strip().eq(symbol)]
        if matches.empty:
            return {}
        row = matches.iloc[0]
        return {"longName":row["NAME OF COMPANY"],"exchange":"NSE","currency":"INR","isin":row["ISIN NUMBER"]}

    def annual_filing(self,symbol):
        url = FILING_REGISTRY.get(symbol)
        if not url:
            return None
        parsed = parse_indas_filing(self.download(url,f"{symbol}-annual.html"),symbol)
        return (*parsed,url)

    def closing_quote(self,symbol,today=None):
        today = today or datetime.now(ZoneInfo("Asia/Kolkata")).date()
        # At most seven calendar dates; skip weekends and stop on access/network failures.
        for offset in range(1,8):
            day = today-timedelta(days=offset)
            if day.weekday()>=5:
                continue
            name = f"BhavCopy_NSE_CM_0_0_0_{day:%Y%m%d}_F_0000.csv.zip"
            url = f"https://nsearchives.nseindia.com/content/cm/{name}"
            try:
                raw = self.download(url,name,ttl_hours=24)
                with ZipFile(BytesIO(raw)) as z:
                    names = [n for n in z.namelist() if n.endswith(".csv")]
                    if len(names)!=1 or z.getinfo(names[0]).file_size>30_000_000:
                        raise ValueError("Unexpected NSE archive contents")
                    frame = pd.read_csv(z.open(names[0]))
                match = frame[frame.TckrSymb.eq(symbol)&frame.SctySrs.eq("EQ")]
                if len(match):
                    row = match.iloc[0]
                    observed = pd.Timestamp(row["TradDt"]).date()
                    if observed!=day or not finite(row["ClsPric"]) or row["ClsPric"]<=0:
                        continue
                    return {"currentPrice":float(row["ClsPric"]),"currency":"INR","priceAsOf":str(day),
                            "priceBasis":"NSE official daily closing price (not live)","priceSourceUrl":url}
            except requests.HTTPError as exc:
                if exc.response.status_code==404:
                    continue
                raise  # Do not try to evade NSE access restrictions.
        return {}
