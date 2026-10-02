"""FinModel AI — unified Streamlit dashboard."""
from dataclasses import asdict
import html
import logging
import re
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from finmodel_agents.market_data import MarketDataAgent
from finmodel_agents.resolver import resolve
from finmodel_agents.normalizer import normalize
from finmodel_agents.forecasting import Assumptions, LABELS, default_assumptions
from finmodel_agents.orchestrator import run_model
from finmodel_agents.valuation import Valuation, reverse_dcf, monte_carlo
from finmodel_agents.kpis import calculate_kpis, PERCENT_KPIS, DAY_KPIS
from finmodel_agents.comps import trading_comps
from finmodel_agents.export import excel_workbook, powerbi_files
from finmodel_agents.utils import Units, finite, pct, multiple, statement_display, safe_div

COLORS = ["#172b4d", "#087f8c", "#b38b4d", "#707bb6"]
FOOTER = "Actual financial data is retrieved from public market-data sources. Forecasts are model-generated estimates and should not be confused with analyst consensus unless explicitly labeled. Critical investment decisions should be verified against company filings and primary sources. This application is for research and education, not financial advice."


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_company(ticker):
    return MarketDataAgent().fetch(ticker)


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_peers(tickers):
    return trading_comps(tickers)


@st.cache_data(show_spinner=False)
def cached_model(data, a, years):
    return run_model(data,a,years)


@st.cache_data(show_spinner=False)
def valuation_extras(hist,data,a,years,forecast,count,seed):
    growth,message = reverse_dcf(hist,data,a,years,data.info.get("currentPrice",np.nan))
    samples,summary = monte_carlo(forecast,data,count,seed)
    return growth,message,samples,summary


@st.cache_data(show_spinner=False)
def export_excel(bundle,units,comps):
    return excel_workbook(bundle,units,comps)


def style():
    st.markdown("""<style>
    .block-container {max-width:1540px;padding-top:2rem;padding-bottom:2rem}
    h1,h2,h3 {letter-spacing:-.035em}
    .eyebrow {font-size:12px;letter-spacing:.17em;color:#087f8c;font-weight:700;text-transform:uppercase;margin-bottom:10px}
    .hero {padding:28px 32px;background:#172b4d;border-radius:14px;margin:14px 0 25px;color:white}
    .hero h2 {color:white;margin:0;font-size:32px}.hero p{color:#c7d6e7;margin:10px 0 0;max-width:800px}
    .kpi-card {background:#fff;border:1px solid #dce4ef;border-top:4px solid var(--accent);border-radius:10px;padding:17px 18px;min-height:122px;margin-bottom:14px}
    .kpi-label {font-size:12px;color:#61718a;font-weight:600;letter-spacing:.02em}
    .kpi-value {font-size:26px;font-weight:700;color:#172b4d;letter-spacing:-.035em;white-space:nowrap}
    .kpi-sub {font-size:11px;color:#75859a;margin-top:4px}
    .step {border:1px solid #dce4ef;border-radius:10px;padding:20px;background:white;min-height:165px}
    .step b{color:#087f8c;font-size:14px}.step p{font-size:14px;color:#61718a;margin:12px 0 0}
    div[data-testid="stTabs"] button {font-size:13px}
    div[data-testid="stDataFrame"] {border-radius:8px}
    div[data-testid="stMetricValue"] {font-size:24px}
    </style>""",unsafe_allow_html=True)


def cards(items):
    cols = st.columns(len(items))
    for n,(label,value,subtitle) in enumerate(items):
        with cols[n]:
            st.markdown(f'<div class="kpi-card" style="--accent:{COLORS[n%len(COLORS)]}"><div class="kpi-label">{html.escape(label)}</div><div class="kpi-value">{html.escape(str(value))}</div><div class="kpi-sub">{html.escape(subtitle)}</div></div>',unsafe_allow_html=True)


def chart(fig,key):
    fig.update_layout(template="plotly_white",font={"family":"Arial","color":"#52647a"},height=350,
        margin={"l":12,"r":12,"t":35,"b":20},paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)",
        legend={"orientation":"h","y":-0.16},colorway=COLORS,hovermode="x unified")
    fig.update_yaxes(tickformat=",.1f",gridcolor="#e8edf4",zerolinecolor="#c8d3e3")
    st.plotly_chart(fig,config={"displayModeBar":False},width="stretch",key=key)


def trend(hist,forecast,rows,units,title,key,percent=False):
    fig = go.Figure()
    for n,row in enumerate(rows):
        if row not in hist.index:
            continue
        values = hist.loc[row]
        scale = 100 if percent else 1/units.scale
        fig.add_trace(go.Scatter(x=list(values.index),y=values.values*scale,name=f"{row} · Actual",mode="lines+markers",line={"color":COLORS[n%4],"width":3}))
        if forecast is not None and row in forecast.index:
            future = forecast.loc[row]
            x = [values.index[-1]]+list(future.index)
            y = [values.iloc[-1]*scale]+list(future.values*scale)
            fig.add_trace(go.Scatter(x=x,y=y,name=f"{row} · Model Forecast",mode="lines+markers",line={"color":COLORS[n%4],"width":2,"dash":"dot"}))
    fig.update_layout(title={"text":title,"font":{"size":16}},yaxis_title="%" if percent else units.label)
    chart(fig,key)


def table(frame,units,forecast=False):
    if frame.empty:
        st.info("No annual statement data is available.")
        return
    display = statement_display(frame,units)
    display.columns = [str(col)+( " · Forecast" if forecast else " · Actual") for col in display.columns]
    st.dataframe(display,width="stretch",height=min(740,38+35*len(display)),column_config={"_index":"Metric"})


def workflow():
    st.subheader("How the model works")
    steps = [("01 · Data","Company resolution → Public market data → Historical statements"),
             ("02 · Model","Normalization → Operating schedules → Three-statement forecast"),
             ("03 · Valuation","DCF → Reverse DCF → Monte Carlo → Trading comps"),
             ("04 · Control","Consensus → KPIs & risks → Audit → Excel & Power BI")]
    for col,(title,body) in zip(st.columns(4),steps):
        with col:
            st.markdown(f'<div class="step"><b>{title}</b><p>{body}</p></div>',unsafe_allow_html=True)


def assumptions_editor(data, a):
    st.subheader("Operating and valuation assumptions")
    st.caption("Operating defaults use bounded historical ratios when available. Capital-market and financing defaults are illustrative inputs, not current market yields. All rates below are percentages; beta and working-capital days are unscaled.")
    values = {}
    with st.form(f"assumption_form_{data.ticker}"):
        cols = st.columns(3)
        for n,(key,value) in enumerate(asdict(a).items()):
            raw = key in ("dso","dio","dpo","beta")
            with cols[n%3]:
                values[key] = st.number_input(LABELS[key]+("" if raw else " (%)"),value=float(value if raw else value*100),step=.1 if key=="beta" else 1.0 if raw else .25,format="%.2f",key=f"driver_{data.ticker}_{key}")/(1 if raw else 100)
        submitted = st.form_submit_button("Apply assumptions",type="primary")
    if submitted:
        try:
            changed = Assumptions(**values)
            changed.validate()
            st.session_state[f"assumptions_{data.ticker}"] = changed
            st.rerun()
        except ValueError as exc:
            st.error(str(exc))


def main():
    st.set_page_config(page_title="FinModel AI | Financial modelling & valuation",page_icon="◈",layout="wide")
    style()
    with st.sidebar:
        st.markdown("## ◈ FinModel AI")
        st.caption("FINANCIAL MODELLING & VALUATION")
        with st.form("company_search"):
            query = st.text_input("Company name or ticker",value="AAPL",placeholder="e.g. Reliance or RELIANCE.NS")
            peers = st.text_input("Peer tickers (optional)",placeholder="MSFT, GOOGL, NVDA")
            analyze = st.form_submit_button("Build financial model",type="primary",width="stretch")
        demo = st.button("Run 1-click demo (AAPL)",width="stretch")
        st.divider()
        years = st.slider("Forecast years",3,5,5)
        count = st.select_slider("Monte Carlo simulations",[250,500,1000,2500,5000,10000],value=1000)
        unit_choice = st.selectbox("Display units",["Auto","Crore","Million","Billion"])
        with st.expander("Simulation settings"):
            seed = st.number_input("Random seed",min_value=0,max_value=2147483647,value=42,step=1)
        refresh = st.button("Refresh public data",width="stretch",disabled="company" not in st.session_state)
        st.caption("No API key required. Public data can be delayed, incomplete or temporarily rate-limited.")
        st.caption("Examples: AAPL · MSFT · NVDA · RELIANCE.NS · TCS.NS · ASIANPAINT.NS · HDFCBANK.NS")
    st.markdown('<div class="eyebrow">Research workspace / Public equities</div>',unsafe_allow_html=True)
    st.title("Financial clarity. From filings to forecasts.")
    if analyze or demo or refresh:
        with st.spinner("Retrieving public financial statements…"):
            try:
                ticker = "AAPL" if demo else st.session_state["company"].ticker if refresh else resolve(query)
                if refresh:
                    fetch_company.clear(ticker)
                    fetch_peers.clear()
                data = fetch_company(ticker)
                st.session_state["company"] = data
                if not refresh:
                    st.session_state["peers"] = [] if demo else [x.strip().upper() for x in re.split(r"[,;\s]+",peers) if x.strip()][:12]
            except ValueError as exc:
                st.error(str(exc))
            except Exception:
                logging.exception("Company load failed")
                st.error("Public data could not be retrieved. Try again shortly or enter an exact exchange ticker.")
    if "company" not in st.session_state:
        st.markdown('<div class="hero"><h2>One company. A complete modelling workspace.</h2><p>Explore historical performance, build transparent forecasts and test valuation assumptions. Start with a listed company or launch the Apple demo.</p></div>',unsafe_allow_html=True)
        cards([("10 workspaces","Research → valuation","Statements, schedules and diagnostics"),("3 scenarios","Bear · Base · Bull","Editable, deterministic financial drivers"),("2 export formats","Excel + Power BI","Formula-linked workbook and direct CSVs")])
        workflow()
        st.info("Live data is loaded when you build a model. If Yahoo is unavailable, an existing local snapshot can be used with its original retrieval date; the app never substitutes invented financials.")
        st.divider()
        st.caption(FOOTER)
        return
    data = st.session_state["company"]
    hist = normalize(data)
    units = Units(data.currency,unit_choice)
    quote_units = Units(data.info.get("currency",data.currency),unit_choice)
    st.subheader(f"{data.name} · {data.ticker}")
    st.caption(f"{data.info.get('sector','Sector unavailable')} / {data.info.get('industry','Industry unavailable')}  ·  {data.info.get('exchange','Exchange unavailable')}  ·  {units.label}")
    st.caption(f"Source: {data.source} · Retrieved {data.retrieved_at} · {'Saved local snapshot' if data.cached else 'Public-source snapshot'}")
    for warning in data.warnings:
        st.warning(warning)
    if hist.income.empty:
        st.info("Historical analysis needs annual statements. Use Refresh public data to retry or select another company.")
        st.caption(FOOTER)
        return
    a = st.session_state.get(f"assumptions_{data.ticker}",default_assumptions(hist,data.info))
    bundle = cached_model(data,a,years)
    for notice in bundle.notices:
        st.warning(notice)
    scenario = st.radio("Model scenario",["Bear","Base","Bull"],index=1,horizontal=True)
    forecast = bundle.forecasts.get(scenario)
    val = bundle.valuations.get(scenario,Valuation(message="Valuation is unavailable without a usable forecast."))
    st.caption(f"Annual Actuals through {hist.years[-1]} · {scenario} Model Forecast · Amounts in {units.label}; prices are per share.")
    tabs = st.tabs(["Executive Dashboard","Historical Actuals","Forecast & Schedules","3-Statement Model","Valuation","Trading Comps","Consensus","KPIs & Risks","Audit","Excel / Power BI"])
    with tabs[0]:
        latest = hist.income.iloc[:,-1]
        cards([("Revenue",units.money(latest["Revenue"]),f"Actual · {hist.years[-1]}"),
               ("EBITDA",units.money(latest["EBITDA"]),f"Margin {pct(safe_div(latest['EBITDA'],latest['Revenue']))}"),
               ("Free cash flow",units.money(hist.cashflow.iloc[:,-1]["FCF"]),"Actual CFO less capex"),
               ("DCF implied price",units.money(val.values.get("Implied Price"),True),f"{scenario} model · {pct(val.values.get('Upside'))} implied upside")])
        left,right = st.columns(2)
        with left:
            trend(hist.income,forecast.income if forecast else None,["Revenue"],units,"Revenue trajectory","revenue")
        with right:
            trend(hist.income,forecast.income if forecast else None,["EBITDA","Net Income"],units,"Profitability","profit")
        left,right = st.columns(2)
        with left:
            trend(hist.cashflow,forecast.cashflow if forecast else None,["FCF"],units,"Free cash flow","fcf")
        with right:
            k = bundle.kpis
            historical_k = k.loc[["Gross margin","EBITDA margin","Net margin"],hist.years]
            forecast_k = calculate_kpis(forecast.income,forecast.balance,forecast.cashflow) if forecast else None
            trend(historical_k,forecast_k,["Gross margin","EBITDA margin","Net margin"],units,"Margin trends","margins",True)
        if bundle.forecasts:
            fig = go.Figure()
            for name,model in bundle.forecasts.items():
                fig.add_trace(go.Scatter(x=model.income.columns,y=model.income.loc["Revenue"]/units.scale,name=name,mode="lines+markers"))
            fig.update_layout(title="Scenario comparison · forecast revenue",yaxis_title=units.label)
            chart(fig,"scenario_revenue")
        workflow()
    with tabs[1]:
        st.subheader("Historical actuals")
        st.caption("Annual fiscal periods from Yahoo Finance. N/A means the source did not provide a value. Derived lines and residual categories are disclosed below.")
        st.markdown("#### Income statement")
        table(hist.income,units)
        st.markdown("#### Balance sheet")
        table(hist.balance,units)
        st.markdown("#### Cash flow")
        table(hist.cashflow,units)
        with st.expander("Normalization and source disclosures"):
            for line in hist.notes:
                st.caption(line)
    with tabs[2]:
        assumptions_editor(data,a)
        st.caption("Bear: revenue growth −3 percentage points, gross / EBITDA margins −2 points, DSO +5 days. Bull: the reverse. Other drivers remain unchanged; supported bounds apply.")
        if forecast:
            st.markdown(f"#### {scenario} operating schedules")
            for name,frame in forecast.schedules.items():
                with st.expander(name,expanded=name=="Revenue Build"):
                    table(frame,units,True)
    with tabs[3]:
        st.subheader(f"Integrated three-statement model · {scenario}")
        if forecast:
            max_balance = forecast.balance.loc["Balance Check"].abs().max()
            max_cash = forecast.cashflow.loc["Cash Reconciliation"].abs().max()
            cards([("Balance check","Balanced" if max_balance<=1 else "Review required",f"Max residual: {max_balance:,.4f} {data.currency}"),
                   ("Cash reconciliation","Reconciled" if max_cash<=1 else "Review required",f"Max residual: {max_cash:,.4f} {data.currency}"),
                   ("Additional debt funding",units.money(forecast.cashflow.loc["Funding Draw"].sum()),"Explicit draws across forecast years")])
            for label,frame in (("Income statement",forecast.income),("Balance sheet",forecast.balance),("Cash flow statement",forecast.cashflow)):
                st.markdown(f"#### {label}")
                table(frame,units,True)
            with st.expander("Model mechanics and simplifying assumptions",expanded=True):
                for line in forecast.notes:
                    st.caption(line)
        else:
            st.info("An integrated forecast is unavailable for this dataset. Review the notices and historical actuals.")
    with tabs[4]:
        st.subheader(f"Valuation overview · {scenario}")
        if val.values:
            v = val.values
            cards([("Current price",quote_units.money(v["Current Price"],True),"Public market quote"),("DCF implied price",units.money(v["Implied Price"],True),"Model estimate per share"),
                ("Upside / downside",pct(v["Upside"]),"Relative to market price"),("WACC",pct(v["WACC"]),"Market equity / book-debt weights"),("Terminal growth",pct(v["Terminal Growth"]),"Gordon growth perpetuity")])
            left,right = st.columns([1,1.25])
            with left:
                st.markdown("#### Enterprise-to-equity bridge")
                bridge = ["PV Forecast FCF","PV Terminal Value","Enterprise Value","Net Debt","Minority Interest","Preferred Equity","Equity Value"]
                st.dataframe(pd.DataFrame({"Valuation component":bridge,"Amount":[units.money(v[k]) for k in bridge]}),hide_index=True,width="stretch")
                st.caption(f"Cost of equity {pct(v['Cost of Equity'])} · After-tax debt cost {pct(v['After-tax Cost of Debt'])} · Debt weight {pct(v['Debt Weight'])}")
            with right:
                sensitivity = val.sensitivity
                z = sensitivity.to_numpy(dtype=float)
                fig = go.Figure(go.Heatmap(z=z,x=[pct(x) for x in sensitivity.columns],y=[pct(x) for x in sensitivity.index],
                    colorscale=[[0,"#f0ddd5"],[.5,"#f3f7f8"],[1,"#087f8c"]],text=[[units.money(x,True) for x in row] for row in z],texttemplate="%{text}",showscale=False,
                    hovertemplate="WACC %{y}<br>Terminal growth %{x}<br>Price %{text}<extra></extra>"))
                fig.update_layout(title="DCF sensitivity · implied price per share",xaxis_title="Terminal growth",yaxis_title="WACC")
                chart(fig,"sensitivity")
            st.caption("Year-end discounting from the latest fiscal period; no stub-period adjustment to today's date. Current market capitalization weights equity, and latest annual book debt approximates market-value debt. Cash includes short-term investments where available. No automatic FX conversion. Minority and preferred claims are deducted when reported.")
            with st.expander("Unlevered cash-flow build"):
                frame = val.cashflows.copy()
                shown = statement_display(frame,units)
                shown.loc["Discount Factor"] = [f"{x:.4f}x" for x in frame.loc["Discount Factor"]]
                st.dataframe(shown,width="stretch")
                st.caption("UFCF = EBIT − unlevered cash taxes + D&A − capex − change in operating working capital.")
            with st.spinner("Calculating reverse DCF and valuation distribution…"):
                implied_growth,message,samples,summary = valuation_extras(hist,data,forecast.assumptions,years,forecast,count,seed)
            st.markdown("#### Reverse DCF · what the market implies")
            cards([("Market-implied revenue growth",pct(implied_growth),"Constant annual growth over the forecast"),("Selected scenario growth",pct(forecast.assumptions.growth),f"{scenario} input"),("Growth gap",pct(implied_growth-forecast.assumptions.growth),"Market-implied less model input")])
            st.caption(message)
            st.markdown("#### Monte Carlo valuation")
            st.caption(f"Seed {seed:,} · {len(samples):,} valid of {count:,} draws. Independent normal driver shocks held constant across each path: revenue growth 3pp, gross / EBITDA margins 2pp, WACC 1pp, terminal growth 0.5pp. Reject non-positive terminal UFCF and WACC–growth spreads ≤0.5pp. These are assumption scenarios, not calibrated probabilities or confidence intervals.")
            if len(samples):
                st.dataframe(pd.DataFrame({"Statistic":summary.index,"Price per share":[units.money(x,True) for x in summary]}),hide_index=True,width="stretch")
                fig = go.Figure(go.Histogram(x=samples,nbinsx=50,marker_color="#087f8c"))
                fig.add_vline(x=v["Current Price"],line_dash="dash",line_color="#b38b4d") if finite(v["Current Price"]) else None
                fig.update_layout(xaxis_title=f"Implied price per share ({data.currency})",yaxis_title="Simulation count",title="Valuation distribution · dashed line is market price")
                chart(fig,"monte_carlo")
            comparison = [(name,item.values.get("Implied Price",np.nan)) for name,item in bundle.valuations.items()]
            fig = go.Figure(go.Bar(x=[x[0] for x in comparison]+["Market"],y=[x[1] for x in comparison]+[v["Current Price"]],marker_color=["#707bb6","#087f8c","#172b4d","#b38b4d"]))
            fig.update_layout(title="Valuation comparison",yaxis_title=f"Price per share ({data.currency})")
            chart(fig,"valuation_comparison")
        else:
            st.info(val.message)
    peers_frame = pd.DataFrame()
    with tabs[5]:
        st.subheader("Trading comparables")
        tickers = st.session_state.get("peers",[])
        if tickers:
            with st.spinner("Retrieving comparable-company metrics…"):
                peers_frame,notes = fetch_peers(tuple(tickers))
            for line in notes:
                st.warning(line)
            if not peers_frame.empty:
                shown = peers_frame.copy()
                for idx,row in peers_frame.iterrows():
                    for col in ("Market Cap","EV","Revenue","EBITDA","Net Income"):
                        currency = row["Quote Currency"] if col in ("Market Cap","EV") else row["Currency"]
                        shown[col] = shown[col].astype(object)
                        shown.at[idx,col] = Units(currency,unit_choice).money(row[col])
                for col in ("Revenue Growth","EBITDA Margin","EV / Revenue","EV / EBITDA","P/E"):
                    shown[col] = shown[col].map(pct if col in ("Revenue Growth","EBITDA Margin") else multiple)
                st.dataframe(shown.drop(columns=["Retrieved"]),hide_index=True,width="stretch")
                comparable_metrics = ["Revenue Growth","EBITDA Margin","EV / Revenue","EV / EBITDA","P/E"]
                summary = peers_frame[comparable_metrics].agg(["median","mean"])
                for col in summary.columns:
                    summary[col] = summary[col].map(pct if col in ("Revenue Growth","EBITDA Margin") else multiple)
                st.dataframe(summary,width="stretch")
                st.caption("Yahoo trailing metrics; revenue growth is the provider's reported quarterly year-over-year growth. Market cap / EV use quote currency; operating metrics use reporting currency. Absolute values are not averaged across currencies. Ratios use available peers only; losses or missing denominators are N/A.")
        else:
            st.info("Enter optional peer tickers in the sidebar and build the model to compare companies.")
    with tabs[6]:
        st.subheader("Analyst consensus · source estimates")
        st.caption("Only estimates actually returned by Yahoo Finance appear here. They are separate from FinModel AI's Bear / Base / Bull forecasts. Periods are provider-relative: current / next quarter and current / next fiscal year.")
        if data.estimates:
            labels = {"0q":"Current quarter","+1q":"Next quarter","0y":"Current fiscal year","+1y":"Next fiscal year"}
            for name,frame in data.estimates.items():
                st.markdown(f"#### {name}")
                shown = frame.copy().astype(object)
                for r in frame.index:
                    for col in frame.columns:
                        value = frame.at[r,col]
                        shown.at[r,col] = (f"{value:,.0f}" if finite(value) else "N/A") if col=="numberOfAnalysts" else pct(value) if col=="growth" else units.money(value,per_share=name=="EPS estimates")
                shown.index = [labels.get(x,x) for x in shown.index]
                shown.columns = [re.sub(r"([a-z])([A-Z])",r"\1 \2",x).replace("avg","Average").title() for x in shown.columns]
                st.dataframe(shown,width="stretch")
        else:
            st.info("No analyst consensus estimates were returned. Model forecasts are available separately when source financials support them.")
    with tabs[7]:
        st.subheader("Financial KPIs")
        frames = [pd.concat([getattr(hist,key),getattr(forecast,key)],axis=1) if forecast else getattr(hist,key) for key in ("income","balance","cashflow")]
        kpis = calculate_kpis(*frames)
        shown = kpis.copy().astype(object)
        for row in kpis.index:
            shown.loc[row] = [pct(x) if row in PERCENT_KPIS else f"{x:,.1f}" if row in DAY_KPIS and finite(x) else "N/A" if row in DAY_KPIS else multiple(x) for x in kpis.loc[row]]
        shown.columns = [col+(" · Actual" if col in hist.years else " · Forecast") for col in shown.columns]
        st.dataframe(shown,width="stretch",height=680)
        st.caption("ROE / ROA / ROIC and asset turnover use average opening and closing balances; the first available period uses closing balances. ROIC uses equity + debt − cash. ROE / ROIC are N/A for non-positive capital bases. Days use closing working capital; quick ratio uses cash plus receivables. DuPont ROE = net margin × asset turnover × equity multiplier.")
        st.markdown("#### Risk screening · historical and Base model")
        st.dataframe(bundle.risks,hide_index=True,width="stretch")
    with tabs[8]:
        st.subheader("Model audit · Base")
        st.dataframe(bundle.checks,hide_index=True,width="stretch")
        st.caption("A passed reconciliation confirms arithmetic consistency, not the accuracy of source data or appropriateness of assumptions. N/A inputs remain visible. Reconciliation tolerance is one reporting-currency unit; the opening-balance gate allows minor source rounding.")
        if forecast:
            for note in forecast.notes:
                st.caption(note)
    with tabs[9]:
        st.subheader("Take the model into your workflow")
        st.markdown("#### Complete Excel financial model")
        st.caption("20 formatted worksheets. Base statements, schedules, DCF and sensitivity use Excel formulas. Yellow assumptions are editable. Scenario comparisons, KPIs, peers and source checks are captured app results; regenerate them after app changes. Export is always the Base workbook with all scenario comparisons.")
        try:
            workbook = export_excel(bundle,units,peers_frame)
        except Exception:
            logging.exception("Excel export failed for %s",data.ticker)
            st.warning("The Excel download is temporarily unavailable. Your analysis and Power BI downloads remain available. Try refreshing the public data.")
        else:
            st.download_button("Download Complete Financial Model.xlsx",workbook,file_name=f"{data.ticker}_Complete_Financial_Model.xlsx",mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",type="primary")
        st.markdown("#### Power BI · direct CSV downloads")
        st.caption("UTF-8 files with raw, unscaled values, fiscal period keys and Actual / Model Forecast labels. Currency, per-share values, rates and ratios retain their meaning.")
        files = powerbi_files(bundle)
        cols = st.columns(3)
        for n,(name,contents) in enumerate(files.items()):
            with cols[n%3]:
                st.download_button(name,contents,file_name=name,mime="text/csv" if name.endswith("csv") else "text/plain",key=f"dl_{name}",width="stretch")
    st.divider()
    st.caption(FOOTER)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        logging.exception("Dashboard rendering failed")
        st.error("This view could not be completed. Refresh public data or retry with another company. The local application log contains diagnostic details.")
