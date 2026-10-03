from dataclasses import dataclass, field
import pandas as pd
from .normalizer import normalize
from .forecasting import default_assumptions, scenario_assumptions, SCENARIOS
from .three_statement import build_forecast
from .valuation import Valuation, value_company, reverse_dcf, monte_carlo
from .kpis import calculate_kpis
from .risk import risk_flags
from .audit import audit_model


@dataclass
class ModelBundle:
    data: object
    historical: object
    assumptions: object
    forecasts: dict = field(default_factory=dict)
    valuations: dict = field(default_factory=dict)
    kpis: pd.DataFrame = field(default_factory=pd.DataFrame)
    risks: pd.DataFrame = field(default_factory=pd.DataFrame)
    checks: pd.DataFrame = field(default_factory=pd.DataFrame)
    notices: list = field(default_factory=list)


def run_model(data, assumptions=None, years=5, yearly=None):
    hist = normalize(data)
    a = assumptions or default_assumptions(hist,data.info)
    bundle = ModelBundle(data,hist,a)
    if data.info.get("sector") == "Financial Services":
        bundle.notices.append("Financial institutions require specialist forecasting. Historical statements and KPIs are available; generic industrial forecasts and DCF are disabled.")
    else:
        for name in SCENARIOS:
            try:
                annual = tuple(scenario_assumptions(item,name) for item in yearly) if yearly is not None else None
                f = build_forecast(hist,data.info,scenario_assumptions(a,name),years,annual)
                bundle.forecasts[name] = f
                bundle.valuations[name] = value_company(f,data)
            except ValueError as exc:
                bundle.notices.append(f"{name}: {exc}")
    base = bundle.forecasts.get("Base")
    val = bundle.valuations.get("Base",Valuation(message="Valuation requires a usable non-financial-company forecast."))
    frames = [pd.concat([getattr(hist,key),getattr(base,key)],axis=1) if base else getattr(hist,key) for key in ("income","balance","cashflow")]
    bundle.kpis = calculate_kpis(*frames)
    bundle.risks = risk_flags(bundle.kpis,hist,base,val)
    bundle.checks = audit_model(hist,base,val)
    return bundle
