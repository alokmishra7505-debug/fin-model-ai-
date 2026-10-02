from dataclasses import dataclass
import math
import numpy as np
import pandas as pd


def finite(value):
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError, OverflowError):
        return False


def safe_div(a, b):
    return float(a) / float(b) if finite(a) and finite(b) and b != 0 else np.nan


@dataclass(frozen=True)
class Units:
    currency: str = "USD"
    selection: str = "Auto"

    @property
    def name(self):
        return ("Crore" if self.currency == "INR" else "Million") if self.selection == "Auto" else self.selection

    @property
    def scale(self):
        return {"Crore": 1e7, "Million": 1e6, "Billion": 1e9}[self.name]

    @property
    def symbol(self):
        return {"INR": "₹", "USD": "$", "EUR": "€", "GBP": "£", "JPY": "¥"}.get(self.currency, self.currency + " ")

    @property
    def suffix(self):
        return {"Crore": " Cr", "Million": "m", "Billion": "bn"}[self.name]

    @property
    def label(self):
        return f"{self.currency} · {self.name.lower()}s"

    def money(self, value, per_share=False):
        if not finite(value):
            return "N/A"
        if value == 0:
            return "–"
        amount = abs(value) if per_share else abs(value) / self.scale
        result = f"{self.symbol}{amount:,.2f}" if per_share else f"{self.symbol}{amount:,.1f}{self.suffix}"
        return f"({result})" if value < 0 else result


def pct(value):
    return f"{value:.1%}" if finite(value) else "N/A"


def multiple(value):
    return f"{value:,.2f}x" if finite(value) else "N/A"


def statement_display(frame, units):
    result = frame.copy().astype(object)
    for row in result.index:
        for col in result.columns:
            v = frame.at[row, col]
            if row in ("EPS", "EPS change"):
                result.at[row, col] = units.money(v, per_share=True)
            elif row in ("Shares",):
                result.at[row, col] = f"{v / 1e6:,.1f}m" if finite(v) else "N/A"
            elif "margin" in row.lower() or row in ("Revenue growth", "Tax rate", "Interest rate"):
                result.at[row, col] = pct(v)
            elif row.endswith("days"):
                result.at[row, col] = f"{v:,.1f}" if finite(v) else "N/A"
            else:
                result.at[row, col] = units.money(v)
    return result


def as_float(value, default=np.nan):
    return float(value) if finite(value) else default
