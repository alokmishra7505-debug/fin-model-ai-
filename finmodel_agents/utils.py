import math
import numpy as np
import pandas as pd


def safe_float(x, default=np.nan):
    try:
        if x is None:
            return default
        v = float(x)
        return v if math.isfinite(v) else default
    except Exception:
        return default


def latest_value(series_or_row, default=np.nan):
    try:
        s = pd.Series(series_or_row).dropna()
        return safe_float(s.iloc[0] if len(s) else default, default)
    except Exception:
        return default


def get_row(df: pd.DataFrame, candidates, default=0.0):
    if df is None or df.empty:
        return pd.Series(dtype=float)
    for name in candidates:
        if name in df.index:
            s = pd.to_numeric(df.loc[name], errors="coerce")
            return s
    return pd.Series([default] * len(df.columns), index=df.columns, dtype=float)


def annualize_columns(df: pd.DataFrame):
    if df is None or df.empty:
        return df
    out = df.copy()
    cols = []
    for c in out.columns:
        try:
            cols.append(pd.Timestamp(c).year)
        except Exception:
            cols.append(str(c))
    out.columns = cols
    out = out.loc[:, ~pd.Index(out.columns).duplicated()]
    return out


def bounded(value, lo, hi, fallback=0.0):
    try:
        value = float(value)
        if not np.isfinite(value):
            return fallback
        return max(lo, min(hi, value))
    except Exception:
        return fallback


def median_ratio(num: pd.Series, den: pd.Series, lo=-10, hi=10, fallback=0.0):
    x = (pd.to_numeric(num, errors='coerce') / pd.to_numeric(den, errors='coerce')).replace([np.inf, -np.inf], np.nan).dropna()
    if x.empty:
        return fallback
    return bounded(x.median(), lo, hi, fallback)
