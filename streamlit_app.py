import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

from finmodel_agents import FinancialModelOrchestrator

st.set_page_config(page_title="FinModel AI v7", page_icon="📊", layout="wide")
st.title("FinModel AI — Financial Modelling & Valuation Platform")
st.caption("Enter a company or ticker to build a complete financial model, forecast, valuation and downloadable Excel model.")


# Finance-professional UI theme: restrained color, clear KPI cards, clean chart canvas.
st.markdown("""
<style>
[data-testid="stMetric"] {
  background: linear-gradient(135deg, #0B1F33 0%, #17365D 100%);
  border: 1px solid #2F75B5;
  padding: 14px 14px 10px 14px;
  border-radius: 10px;
}
[data-testid="stMetricLabel"], [data-testid="stMetricValue"] { color: white !important; }
[data-testid="stSidebar"] { border-right: 1px solid rgba(100,116,139,.25); }
.stTabs [data-baseweb="tab-list"] { gap: 4px; }
.stTabs [data-baseweb="tab"] { border-radius: 7px 7px 0 0; padding: 8px 12px; }
</style>
""", unsafe_allow_html=True)


def money(x):
    try:
        x = float(x)
        return f"{x:,.2f}" if np.isfinite(x) else "N/A"
    except Exception:
        return "N/A"


CRORE = 10_000_000

def cr_value(x):
    try:
        x = float(x)
        return x / CRORE if np.isfinite(x) else np.nan
    except Exception:
        return np.nan

def crore_df(df):
    """Scale monetary financial-statement tables to crores for display only."""
    out = df.copy()
    numeric_cols = out.select_dtypes(include=[np.number]).columns
    if len(numeric_cols):
        out.loc[:, numeric_cols] = out.loc[:, numeric_cols] / CRORE
    return out

def crore_model(model):
    """Scale all amount rows in a statement-style model while preserving ratio/check rows."""
    out = model.copy()
    ratio_rows = {
        "Revenue Growth", "Gross Margin", "EBITDA Margin", "EBIT Margin",
        "Net Margin", "FCF Margin", "Tax Rate", "ROE", "ROA",
        "Balance Check", "Cash Flow Check"
    }
    for idx in out.index:
        if str(idx) not in ratio_rows:
            out.loc[idx] = pd.to_numeric(out.loc[idx], errors="coerce") / CRORE
    return out


with st.sidebar:
    st.header("Run model")
    company_input = st.text_input("Company name or ticker", value="AAPL", help="Examples: Apple, AAPL, Reliance Industries, RELIANCE.NS")
    peers_text = st.text_input("Peer tickers (optional)", value="", help="Comma-separated, e.g. MSFT,GOOGL,AMZN")
    years = st.slider("Forecast years", 3, 10, 5)
    simulations = st.slider("Monte Carlo simulations", 100, 2000, 500, 100)
    run = st.button("Run complete model", type="primary", width="stretch")
    demo_run = st.button("▶ Run 1-click demo (AAPL)", width="stretch")
    st.divider()
    st.caption("Tip: for Indian stocks, ticker form such as RELIANCE.NS remains the most reliable input. Company-name search is also supported when Yahoo Finance resolves it.")

if run or demo_run:
    selected_company = "AAPL" if demo_run else company_input
    peers = ["MSFT", "GOOGL", "AMZN"] if demo_run else [x.strip() for x in peers_text.split(",") if x.strip()]
    try:
        with st.status("Running financial modelling agents…", expanded=True) as status:
            st.write("1. Resolving company/ticker")
            st.write("2. Fetching market data and annual statements")
            st.write("3. Normalizing historical statements")
            st.write("4. Deriving operating assumptions and schedules")
            st.write("5. Building Bear / Base / Bull integrated 3-statement forecasts")
            st.write("6. Running KPIs, DCF, reverse DCF and Monte Carlo")
            st.write("7. Pulling optional trading comps and available consensus data")
            st.write("8. Running model audit checks")
            result = FinancialModelOrchestrator().run(selected_company, peer_tickers=peers, years=years, simulations=simulations)
            st.session_state.result = result
            status.update(label="Financial model complete", state="complete", expanded=False)
    except Exception as exc:
        st.error(f"Model run failed: {exc}")
        st.stop()

st.markdown("### How the model works")
arch_cols = st.columns(4)
architecture = [
    ("1. Company Data", "Company identification → market data → historical financial statements"),
    ("2. Financial Model", "Historical normalization → operating schedules → integrated 3-statement forecast"),
    ("3. Valuation", "DCF → reverse DCF → scenario analysis → trading comparables"),
    ("4. Review & Export", "KPIs → risk checks → model audit → Excel / Power BI export"),
]
for col, (head, body) in zip(arch_cols, architecture):
    with col:
        st.markdown(
            f"<div style='min-height:120px;padding:16px;border:1px solid rgba(47,117,181,.35);"
            f"border-radius:12px;background:rgba(47,117,181,.06)'><b>{head}</b><br><br>{body}</div>",
            unsafe_allow_html=True,
        )

with st.expander("What the system produces", expanded=False):
    st.markdown("""
- Historical financial statements and normalized KPIs
- Base / Bull / Bear 3-statement forecasts and operating schedules
- DCF, reverse DCF, Monte Carlo and optional trading comps
- Model checks, risk flags and source/audit metadata
- Linked Excel financial model plus Power BI-ready tables

**Important:** actual/source data, model forecasts and available consensus estimates are kept separate.
""")

if "result" not in st.session_state:
    st.info("For a fast demo, click **Run 1-click demo (AAPL)** in the sidebar. Or enter any supported company/ticker and run the complete model.")
    st.stop()

r = st.session_state.result
meta = r["meta"]
hist = r["historical"]
fc = r["forecasts"]
val = r["valuation"]
kpis = r["kpis"]
info = r["data"].info

title = meta.get("Company") or meta.get("Ticker")
st.subheader(f"{title} ({meta.get('Ticker')})")
st.caption(
    f"{meta.get('Exchange') or 'Exchange N/A'} | {meta.get('Currency') or 'Currency N/A'} | "
    f"{meta.get('Sector') or 'Sector N/A'} | Source: {meta.get('Source')} | Fetched: {meta.get('Data Timestamp UTC')}"
)

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Market Cap (Cr)", f"{cr_value(info.get('marketCap')):,.1f}" if info.get("marketCap") else "N/A")
current_price = info.get("currentPrice") or info.get("regularMarketPrice")
c2.metric("Current Price", money(current_price))
c3.metric("DCF Implied Price", money(val.get("Implied Price")))
c4.metric("WACC", f"{val.get('WACC', np.nan):.1%}" if np.isfinite(val.get("WACC", np.nan)) else "N/A")
c5.metric("MC Median Price", money(r["monte_carlo"].get("p50")))

tabs = st.tabs([
    "Executive Dashboard", "Historical Actuals", "Forecast & Schedules", "3-Statement Model",
    "Valuation", "Trading Comps", "Consensus", "KPIs & Risks", "Audit", "Excel / Power BI"
])

with tabs[0]:
    base = fc["Base"]
    chart = (base.loc[["Revenue", "EBITDA", "Net Income", "FCF"]] / CRORE).T.reset_index(names="Period")
    fig_forecast = px.line(chart, x="Period", y=["Revenue", "EBITDA", "Net Income", "FCF"], markers=True, title=f"Base-case forecast ({meta.get('Currency') or ''} Cr)", color_discrete_sequence=["#4472C4", "#70AD47", "#7030A0", "#ED7D31"])
    fig_forecast.update_layout(legend_title_text="", plot_bgcolor="white", paper_bgcolor="white", yaxis_title=f"{meta.get('Currency') or 'Currency'} Crore")
    st.plotly_chart(fig_forecast, width="stretch")

    m = kpis.reset_index(names="Period")
    margin_cols = [c for c in ["Gross Margin", "EBITDA Margin", "Net Margin", "FCF Margin"] if c in m.columns]
    if margin_cols:
        fig_margin = px.line(m, x="Period", y=margin_cols, markers=True, title="Margins and cash conversion", color_discrete_sequence=["#2F75B5", "#70AD47", "#ED7D31", "#7030A0"])
        fig_margin.update_layout(legend_title_text="", plot_bgcolor="white", paper_bgcolor="white")
        st.plotly_chart(fig_margin, width="stretch")

    left, right = st.columns(2)
    with left:
        st.write("**Rule-based risk flags**")
        for flag in r["flags"]:
            st.write("•", flag)
    with right:
        mc = r["monte_carlo"]
        st.write("**Monte Carlo valuation range**")
        st.write({"P10": money(mc.get("p10")), "Median": money(mc.get("p50")), "P90": money(mc.get("p90")), "Simulations": mc.get("count")})

with tabs[1]:
    st.caption("Historical annual data from the market-data provider. These are actual/source values, not model forecasts.")
    st.caption(f"Monetary values shown in {meta.get('Currency') or 'Currency'} crore (Cr).")
    st.dataframe(crore_model(hist).style.format("{:,.1f}"), width="stretch")

with tabs[2]:
    scen = st.selectbox("Scenario", ["Bear", "Base", "Bull"], index=1, key="forecast_scenario")
    st.caption(f"Monetary values shown in {meta.get('Currency') or 'Currency'} crore (Cr).")
    st.dataframe(crore_model(fc[scen]).style.format("{:,.1f}"), width="stretch")
    st.write("**Base assumptions**")
    st.dataframe(pd.DataFrame({"Assumption": list(r["assumptions"].keys()), "Value": list(r["assumptions"].values())}), width="stretch")
    st.caption("Bull/Bear scenarios adjust revenue growth and margins around the base assumptions. The forecast is deterministic and formula-driven.")

with tabs[3]:
    scen3 = st.radio("3-statement scenario", ["Base", "Bull", "Bear"], horizontal=True)
    model = fc[scen3]
    st.caption(f"Monetary values shown in {meta.get('Currency') or 'Currency'} crore (Cr). Per-share valuation metrics remain in reporting currency.")
    st.write("**Income Statement**")
    st.dataframe(crore_model(model.loc[["Revenue", "COGS", "Gross Profit", "EBITDA", "D&A", "EBIT", "Interest Expense", "Pretax Income", "Tax", "Net Income"]]).style.format("{:,.1f}"), width="stretch")
    st.write("**Balance Sheet**")
    st.dataframe(crore_model(model.loc[["Cash", "Accounts Receivable", "Inventory", "Net PPE", "Other Assets", "Total Assets", "Accounts Payable", "Total Debt", "Other Liabilities", "Equity", "Total Liabilities & Equity", "Balance Check"]]).style.format("{:,.1f}"), width="stretch")
    st.write("**Cash Flow / Schedules**")
    st.dataframe(crore_model(model.loc[["CFO", "Capex", "Debt Issuance/(Repayment)", "Dividends", "Net Change in Cash", "Cash Flow Check", "FCF"]]).style.format("{:,.1f}"), width="stretch")
    st.warning("Generic corporate model: 'Other Liabilities' is the balancing residual. Banks, NBFCs, insurers and REITs require sector-specific models and should not rely on this generic template.")

with tabs[4]:
    l, rr = st.columns([1, 2])
    with l:
        st.write("**DCF**")
        st.json({k: (round(float(v), 4) if isinstance(v, (float, int, np.floating)) and np.isfinite(v) else v) for k, v in val.items() if k != "UFCF"})
        st.write("**Reverse DCF**")
        st.json(r["reverse_dcf"])
        st.write("**Monte Carlo**")
        st.json(r["monte_carlo"])
    with rr:
        sens = r["sensitivity"].pivot(index="WACC", columns="Terminal Growth", values="Implied Price")
        st.plotly_chart(px.imshow(sens, aspect="auto", text_auto=".2f", title="DCF sensitivity — implied price"), width="stretch")

with tabs[5]:
    if r["comps"] is None or r["comps"].empty:
        st.info("No peer tickers were supplied. Add comma-separated peer tickers in the sidebar and rerun the model.")
    else:
        st.dataframe(r["comps"], width="stretch")
        st.write("**Peer multiple distribution**")
        st.json(r["comps_summary"])

with tabs[6]:
    if not r["consensus"]:
        st.info("No analyst-consensus tables were available from the current data provider for this ticker. Model forecasts remain separate from consensus.")
    else:
        for name, df in r["consensus"].items():
            st.write(f"**{name}**")
            st.dataframe(df, width="stretch")

with tabs[7]:
    pct_cols = [c for c in ["Revenue Growth", "Gross Margin", "EBITDA Margin", "EBIT Margin", "Net Margin", "FCF Margin", "ROE", "ROA"] if c in kpis.columns]
    st.dataframe(kpis.style.format("{:.2%}", subset=pct_cols), width="stretch")
    st.write("**Flags**")
    for flag in r["flags"]:
        st.write("•", flag)

with tabs[8]:
    audit_df = pd.DataFrame(r["audit"])
    st.dataframe(audit_df, width="stretch")
    if not audit_df.empty and (audit_df["Status"] == "FAIL").any():
        st.error("One or more model checks failed. Review assumptions/model output before using the valuation.")
    else:
        st.success("Core balance-sheet and cash roll-forward checks passed for all scenarios.")
    st.json(meta)

with tabs[9]:
    orch = FinancialModelOrchestrator()

    linked_tmp = Path(tempfile.gettempdir()) / f"{meta['Ticker']}_Complete_Financial_Model.xlsx"
    orch.export_agent.export_linked_financial_model(linked_tmp, r)
    st.success("Linked financial model ready: editable assumptions, formula-driven schedules, 3 statements, DCF, sensitivity, checks and dashboard in one workbook.")
    st.download_button(
        "Download Complete Linked Financial Model.xlsx",
        data=linked_tmp.read_bytes(),
        file_name=linked_tmp.name,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        width="stretch",
    )

    raw_tmp = Path(tempfile.gettempdir()) / f"{meta['Ticker']}_Raw_Model_Output.xlsx"
    orch.export_agent.export_excel(raw_tmp, r)
    with st.expander("Optional: raw agent output workbook"):
        st.download_button(
            "Download raw output workbook",
            data=raw_tmp.read_bytes(),
            file_name=raw_tmp.name,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            width="stretch",
        )

    pbi = orch.export_agent.power_bi_tables(r)
    st.markdown("### Power BI-ready tables")
    st.caption("Download each table directly as CSV. No ZIP extraction needed.")

    for name, df in pbi.items():
        csv_bytes = df.to_csv(index=False).encode("utf-8")
        st.download_button(
            label=f"Download {name}.csv",
            data=csv_bytes,
            file_name=f"{meta['Ticker']}_{name}.csv",
            mime="text/csv",
            width="stretch",
            key=f"download_{name}",
        )

    powerbi_readme = (
        "Load Company, Period, FinancialActuals, Forecasts, KPIs, Valuation, Assumptions and ModelChecks. "
        "Create 1-to-many relationships from Company[Ticker] to fact tables and Period[Period] to Actual/Forecast/KPI tables. "
        "Suggested measures: Revenue, EBITDA, EBITDA Margin, Net Income, FCF, Revenue Growth, Debt/EBITDA, ROE, DCF Implied Price."
    )
    st.download_button(
        "Download Power BI setup notes",
        data=powerbi_readme.encode("utf-8"),
        file_name=f"{meta['Ticker']}_PowerBI_README.txt",
        mime="text/plain",
        width="stretch",
    )

st.divider()
st.caption("This is a modelling tool, not a guarantee of investment outcomes. Verify material figures against company filings and primary sources before acting on the output.")
