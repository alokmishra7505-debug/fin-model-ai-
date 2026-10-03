from dataclasses import dataclass, field
import numpy as np
import pandas as pd
from scipy.optimize import brentq
from .utils import finite, safe_div
from .three_statement import build_forecast
from .forecasting import scenario_assumptions
from dataclasses import replace


@dataclass
class Valuation:
    values: dict = field(default_factory=dict)
    cashflows: pd.DataFrame = field(default_factory=pd.DataFrame)
    sensitivity: pd.DataFrame = field(default_factory=pd.DataFrame)
    message: str = ""


def wacc(a, market_cap, debt):
    if not finite(market_cap) or market_cap <= 0 or not finite(debt) or debt < 0:
        return np.nan
    ke = a.risk_free+a.beta*a.equity_premium
    return ke*market_cap/(market_cap+debt)+a.cost_debt*(1-a.tax_rate)*debt/(market_cap+debt)


def dcf_value(cashflows, discount_rate, terminal_growth, net_debt=0, shares=np.nan):
    flows = np.asarray(cashflows, dtype=float)
    if not len(flows) or not np.all(np.isfinite(flows)) or not finite(discount_rate) or discount_rate <= terminal_growth or discount_rate <= 0:
        raise ValueError("DCF requires finite cash flows and a positive WACC above terminal growth.")
    factors = (1+discount_rate)**np.arange(1, len(flows)+1)
    pv_flows = float(np.sum(flows/factors))
    terminal = float(flows[-1]*(1+terminal_growth)/(discount_rate-terminal_growth))
    pv_terminal = terminal/factors[-1]
    ev = pv_flows+pv_terminal
    equity = ev-net_debt
    return {"PV Forecast FCF": pv_flows, "Terminal Value": terminal, "PV Terminal Value": pv_terminal,
            "Enterprise Value": ev, "Net Debt": net_debt, "Equity Value": equity,
            "Implied Price": safe_div(equity, shares) if shares > 0 else np.nan,
            "WACC": discount_rate, "Terminal Growth": terminal_growth,
            "Terminal Value Weight": safe_div(pv_terminal, ev)}


def value_company(model, data):
    info, a = data.info, model.assumptions
    if data.currency != info.get("currency", data.currency):
        return Valuation(message="Quote and financial reporting currencies differ. DCF is unavailable until a consistent currency basis is supplied.")
    if not data.currency or data.currency == "Unknown":
        return Valuation(message="Reporting currency is unavailable; valuation has been paused.")
    if info.get("sector") == "Financial Services":
        return Valuation(message="Industrial-company FCFF valuation is disabled for financial institutions. Banks and insurers need regulatory capital, deposit and equity-based models.")
    rate = wacc(a, info.get("marketCap"), model.opening["Debt"])
    flows = model.cashflow.loc["UFCF"].values
    if not finite(rate):
        return Valuation(message="Market capitalization or debt is unavailable; market-value WACC cannot be calculated.")
    if flows[-1] <= 0:
        return Valuation(message="Terminal-year UFCF is non-positive. A perpetuity DCF is not economically meaningful; revise the operating assumptions.")
    # Book debt is a disclosed proxy for market-value debt; excess cash uses latest annual balances.
    net_debt = model.opening["Debt"]-model.opening["Cash"]
    minority = 0.0
    if "Minority Interest" in data.balance.index:
        series = data.balance.loc["Minority Interest"].dropna()
        if len(series):
            minority = max(0, float(series.iloc[0]))
    preferred = 0.0
    if "Preferred Stock" in data.balance.index:
        series = data.balance.loc["Preferred Stock"].dropna()
        if len(series):
            preferred = max(0, float(series.iloc[0]))
    try:
        result = dcf_value(flows, rate, a.terminal_growth, net_debt+minority+preferred, model.opening["Shares"])
    except ValueError as e:
        return Valuation(message=str(e))
    result.update({"Net Debt": net_debt, "Minority Interest": minority, "Preferred Equity": preferred,
                   "Current Price": info.get("currentPrice", np.nan), "Cost of Equity": a.risk_free+a.beta*a.equity_premium,
                   "After-tax Cost of Debt": a.cost_debt*(1-a.tax_rate),
                   "Debt Weight": model.opening["Debt"]/(info["marketCap"]+model.opening["Debt"])})
    result["Upside"] = safe_div(result["Implied Price"], result["Current Price"])-1
    cashflows = pd.DataFrame({"UFCF": flows, "Discount Factor": 1/(1+rate)**np.arange(1,len(flows)+1),
                             "PV UFCF": flows/(1+rate)**np.arange(1,len(flows)+1)}, index=model.income.columns).T
    rates = rate+np.linspace(-.02, .02, 5)
    growths = a.terminal_growth+np.linspace(-.01, .01, 5)
    sensitivity = pd.DataFrame(index=rates, columns=growths, dtype=float)
    for r in rates:
        for g in growths:
            sensitivity.at[r,g] = dcf_value(flows, r, g, net_debt+minority+preferred, model.opening["Shares"])["Implied Price"] if r>g and r>0 else np.nan
    return Valuation(result, cashflows, sensitivity)


def reverse_dcf(hist, data, a, years, target_price, yearly=None):
    if not finite(target_price) or target_price <= 0:
        return np.nan, "Current market price is unavailable."
    def objective(growth):
        annual = tuple(replace(item,growth=growth) for item in yearly) if yearly else None
        model = build_forecast(hist, data.info, replace(a, growth=growth), years,annual)
        v = value_company(model, data)
        return v.values.get("Implied Price", np.nan)-target_price
    # Search only a bracket containing valid perpetuity valuations.
    grid = np.linspace(-.5, 1, 61)
    previous = None
    for g in grid:
        value = objective(g)
        if finite(value):
            if value == 0:
                return g, "Constant annual revenue growth, holding other drivers and WACC fixed."
            if previous and previous[1]*value < 0:
                root = brentq(objective, previous[0], g, xtol=1e-9)
                return root, "Constant annual revenue growth, holding margins, working-capital days, capital intensity and WACC fixed."
            previous = (g,value)
        else:
            previous = None
    return np.nan, "No valid implied-growth solution exists within the supported -50% to +100% annual growth range."


def monte_carlo(model, data, count=1000, seed=42):
    """Vectorized operating-driver simulation; same operating/FCFF equations as base model."""
    base = value_company(model,data)
    if not base.values:
        return np.array([]), pd.Series(dtype=float)
    rng = np.random.default_rng(seed)
    a, o = model.assumptions, model.opening
    growth_shock = rng.normal(0,.03,count)
    gm_shock = rng.normal(0,.02,count)
    margin_shock = rng.normal(0,.02,count)
    rates = rng.normal(base.values["WACC"],.01,count)
    terminal = rng.normal(a.terminal_growth,.005,count)
    revenue = np.full(count,o["Revenue"])
    ppe = np.full(count,o["Net PPE"])
    nwc = np.full(count,o["Net Working Capital"])
    pv = np.zeros(count)
    for n in range(1,len(model.income.columns)+1):
        a = model.yearly_assumptions[n-1] if model.yearly_assumptions else model.assumptions
        growth = np.clip(a.growth+growth_shock,-.5,1)
        gm = np.clip(a.gross_margin+gm_shock,.01,.99)
        margin = np.clip(a.ebitda_margin+margin_shock,0,gm)
        revenue = revenue*(1+growth)
        capex = revenue*a.capex_pct
        da = np.minimum(revenue*a.da_pct,np.maximum(0,ppe+capex))
        ebit = revenue*margin-da
        next_nwc = revenue*a.dso/365+revenue*(1-gm)*(a.dio-a.dpo)/365+o["Other Current Assets"]-o["Other Current Liabilities"]
        flows = ebit-np.maximum(0,ebit)*a.tax_rate+da-capex-(next_nwc-nwc)
        pv += flows/(1+rates)**n
        nwc, ppe = next_nwc, ppe+capex-da
    valid = (rates>terminal+.005)&(rates>0)&(flows>0)
    bridge = base.values["Net Debt"]+base.values["Minority Interest"]+base.values["Preferred Equity"]
    with np.errstate(divide="ignore",invalid="ignore"):
        prices = (pv+flows*(1+terminal)/(rates-terminal)/(1+rates)**n-bridge)/o["Shares"]
    prices = prices[valid & np.isfinite(prices)]
    if not len(prices):
        return prices,pd.Series(dtype=float)
    summary = pd.Series(dict(zip(["P10","P25","Median / P50","P75","P90"],np.percentile(prices,[10,25,50,75,90]))))
    summary["Mean"] = np.mean(prices)
    return prices,summary.reindex(["P10","P25","Median / P50","Mean","P75","P90"])
