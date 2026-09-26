# FinModel AI — Autonomous Financial Modelling & Valuation

A multi-agent Streamlit application that turns a listed company name/ticker into a reproducible financial-model workflow: market data, historical statements, operating forecasts, integrated three-statement outputs, scenarios, DCF, reverse DCF, Monte Carlo, optional peer comps, model checks, dashboard, Excel model and Power BI-ready exports.

## What the system does

- Resolves a company name or ticker
- Pulls market and historical financial data at runtime
- Normalizes financial statements
- Builds Bear / Base / Bull forecasts
- Produces integrated three-statement forecast outputs
- Calculates KPIs and financial ratios
- Runs DCF, reverse DCF and Monte Carlo valuation
- Supports optional trading-comparable inputs
- Performs model/audit checks
- Generates a presentation-ready Excel financial model
- Exports Power BI-ready data tables

## Important modelling principle

Actual market data, available external estimates and model-generated forecasts are kept conceptually separate. Forecasts are generated from explicit assumptions and deterministic financial calculations rather than being presented as guaranteed outcomes.

## Run locally on Mac

```bash
chmod +x start_mac.sh
./start_mac.sh
```

Then open the local URL shown by Streamlit (normally `http://localhost:8501`).

## Deploy on Streamlit Community Cloud

1. Create a GitHub repository and upload this project.
2. Sign in to Streamlit Community Cloud with GitHub.
3. Create a new app from the repository.
4. Set the entrypoint to `streamlit_app.py`.
5. Deploy.

No API key is required for the default Yahoo Finance-based data workflow, though external data-provider limitations can affect availability or freshness.

## Suggested demo

Use a liquid, widely followed non-financial company such as `AAPL`, `MSFT`, `NVDA`, `TCS.NS`, or `RELIANCE.NS` for a clean demonstration. Banks, insurers, NBFCs and REITs need sector-specific modelling conventions and should not be interpreted through a generic corporate model without adjustments.

## Disclaimer

This project is for financial modelling, analysis and educational/personal research. Outputs depend on third-party market data and user/model assumptions and should be independently verified before investment or business decisions.

## v8 interview polish
- One-click AAPL demo with peers preloaded.
- Visible multi-agent architecture on the landing page.
- Same entrypoint works locally (`app.py`) and on Streamlit Community Cloud (`streamlit_app.py`).


## v8 display improvements
- Interview-clean UI with reduced developer/technical chrome.
- Market cap and statement values displayed in reporting-currency crores (Cr).
- Per-share valuation metrics remain in the original reporting currency.
