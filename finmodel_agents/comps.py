import numpy as np
import pandas as pd
from .utils import finite, safe_div, as_float
from .market_data import MarketDataAgent
from .resolver import resolve


def trading_comps(tickers):
    rows,notes = [],[]
    for ticker in dict.fromkeys(tickers):
        try:
            symbol = resolve(ticker)
            data = MarketDataAgent().fetch(symbol)
            i = data.info
            if not i:
                notes.append(f"{symbol}: market data unavailable.")
                continue
            rev,ebitda,ni = (as_float(i.get(key)) for key in ("totalRevenue","ebitda","netIncomeToCommon"))
            ev,mc = (as_float(i.get(key)) for key in ("enterpriseValue","marketCap"))
            same_currency = data.currency == i.get("currency",data.currency)
            rows.append({"Ticker": symbol,"Company": data.name,"Currency":data.currency,"Quote Currency":i.get("currency","Unknown"),
                "Market Cap":mc,"EV":ev,"Revenue":rev,"EBITDA":ebitda,"Net Income":ni,
                "Revenue Growth":i.get("revenueGrowth",np.nan),"EBITDA Margin":safe_div(ebitda,rev),
                "EV / Revenue":safe_div(ev,rev) if same_currency and rev>0 else np.nan,
                "EV / EBITDA":safe_div(ev,ebitda) if same_currency and ebitda>0 else np.nan,
                "P/E":safe_div(mc,ni) if same_currency and ni>0 else np.nan,"Retrieved":data.retrieved_at})
            if not same_currency:
                notes.append(f"{symbol}: valuation multiples suppressed because reporting and quote currencies differ.")
        except Exception:
            notes.append(f"{ticker}: comparable data unavailable.")
    return pd.DataFrame(rows),notes
