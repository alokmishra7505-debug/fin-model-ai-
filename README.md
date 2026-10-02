# FinModel AI

A locally runnable financial modelling and valuation workspace built with Python and Streamlit. Enter a listed-company ticker or a supported company name to retrieve public financial statements, build deterministic Bear / Base / Bull forecasts, inspect an integrated three-statement model, and export Excel and Power BI files. The basic version needs no API key or paid service.

## Start on macOS

Python 3.11 or newer is recommended. This project was installed and tested with Python 3.14.

```bash
cd /Users/alokmishra/Desktop/PROJECT/FINANCIAL_MODELLING
./start_mac.sh
```

The script creates `.venv` if needed, installs `requirements.txt`, and starts the app at **http://localhost:8501**. Stop it with **Control-C** in the terminal running Streamlit. If necessary, make the script executable with `chmod +x start_mac.sh`. Use `PORT=8502 ./start_mac.sh` when port 8501 is already occupied.

For an existing installed environment, start without checking package downloads:

```bash
.venv/bin/python -m streamlit run streamlit_app.py --server.address 127.0.0.1
```

Manual setup:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m streamlit run streamlit_app.py --server.address 127.0.0.1
```

## Use the application

1. Enter a ticker or company name and optional comma-separated peer tickers, then select **Build financial model**. **Run 1-click demo (AAPL)** retrieves real Apple data.
2. Choose a three-to-five-year horizon, simulation count, display units, and scenario.
3. Under **Forecast & Schedules**, edit operating and valuation assumptions and press **Apply assumptions**. Rates in the app are entered as percentages.
4. Inspect actuals, linked forecasts, DCF, reverse DCF, Monte Carlo, peer comparisons, consensus, KPIs, risks, and reconciliation checks across the ten tabs.
5. Download the complete Excel workbook or any of the eight individual Power BI CSV files plus the relationship guide.

Examples: `AAPL`, `MSFT`, `NVDA`, `RELIANCE.NS`, `TCS.NS`, `ASIANPAINT.NS`, `HDFCBANK.NS`. Names such as Apple, Microsoft, Reliance, Tata Consultancy Services, and Asian Paints have direct aliases. Multiword company names also use Yahoo search where available; always confirm the resolved ticker and exchange. Peer requests are limited to 12 companies per model.

INR statements default to **₹ crore** (1 crore = 10,000,000). Other currencies default to millions in the reporting currency. Unit selection changes display scale only: it never converts currencies, percentages, share counts, or per-share prices.

## Architecture

`app.py` owns the dashboard; `streamlit_app.py` is the local/cloud entry point. `finmodel_agents/` contains ordinary deterministic Python services; these “agents” do not call an LLM or invent financial data.

| Module | Responsibility |
| --- | --- |
| `resolver.py` | Company aliases, exchange tickers, and public company search |
| `market_data.py` | Yahoo Finance profiles, annual statements, consensus, timestamped fallback snapshots |
| `normalizer.py` | Common historical line items, missing-data markers, reported-total residuals |
| `forecasting.py` | Editable assumptions, historical calibration, scenario adjustments |
| `schedules.py` | Revenue, working capital, capex / depreciation, debt, taxes, shares / EPS |
| `three_statement.py` | Income statement, balance sheet, cash flow and explicit funding draws |
| `valuation.py` | CAPM / WACC, FCFF DCF, sensitivity, reverse DCF and seeded Monte Carlo |
| `comps.py`, `kpis.py` | Trading metrics, operating / return ratios and DuPont analysis |
| `risk.py`, `audit.py` | Rule-based flags and model reconciliation checks |
| `export.py` | Formula-linked Excel and relational CSV exports |
| `orchestrator.py` | Unified model pipeline |
| `utils.py` | Safe ratios, units, currency and accounting presentation |

`tests/` contains isolated synthetic fixtures and calculation / UI / Excel formula tests. These fixtures are never presented as actual financials. `scripts/live_smoke.py` tests four real companies and writes exports plus a machine-readable test report to `exports/`. `data/cache/` stores successful public snapshots; both cache and generated exports are ignored by Git.

## Financial methods and limitations

- **Data basis:** annual fiscal statements and available Yahoo metrics, with explicit Actual / Estimate / Model Forecast labels. Source timestamps are UTC retrieval times, not a guarantee of real-time prices. Yahoo data may be delayed, restated, incomplete, rate-limited, or unavailable. In-app data is cached for one hour; **Refresh public data** refreshes it. If live statements fail, the last successful disk snapshot is clearly dated and labelled. No synthetic fallback is used.
- **Historical normalization:** expenses and capex appear as positive uses. Other asset and liability categories include residual reported components. Unavailable source values remain N/A. A usable annual revenue and opening cash / assets / liabilities / equity basis is required to forecast. An opening imbalance greater than the higher of one currency unit or 0.001% of assets pauses forecasting; audit reconciliation tolerance is one currency unit.
- **Forecasts:** constant annual growth, margins, tax and capital-intensity drivers; DSO / DIO / DPO use 365 days. Operating defaults use bounded historical ratios; fallback assumptions are visible and editable. Rates for risk-free return, equity premium, borrowing and financing are illustrative, not fetched market yields. Bear / Bull change growth by ∓3 percentage points, gross and EBITDA margins by ∓2 points, and DSO by ±5 days, subject to bounds.
- **Three statements:** equity rolls forward through net income less dividends; cash rolls through CFO, capex and financing. Required funding is an explicit debt draw. Interest uses opening debt, so new financing affects interest in the next year. No unexplained balancing plug is inserted. Missing optional opening components may be explicitly assumed zero and disclosed. Other assets / liabilities stay fixed, shares stay constant, debt maturity proportions stay fixed, and no acquisitions, FX movements, buybacks, stock compensation, deferred taxes or tax-loss carryforwards are modelled. D&A is capped by available net PPE plus capex. Total equity can include minorities; parent/minority profit allocation is not forecast.
- **DCF:** UFCF = EBIT − unlevered cash taxes + D&A − capex − change in operating working capital. CAPM determines cost of equity; market capitalization and book debt approximate market-value capital weights. After-tax debt cost uses the model tax rate. Annual year-end discounting starts from the latest actual fiscal period, not an exact valuation-date stub period. Latest annual cash / debt form the bridge; reported minority and preferred claims are deducted when available. All included cash / short-term investments are treated as non-operating; operating cash needs are not separately removed from that bridge. Non-positive terminal UFCF or WACC ≤ terminal growth disables the perpetuity valuation. Missing shares disable per-share valuation.
- **Reverse DCF:** solves for constant annual revenue growth needed to match the current price, holding other operating drivers, WACC and terminal growth fixed. The search is bounded to -50% through +100%; a missing solution is displayed as unavailable.
- **Monte Carlo:** seeded independent normal shocks to annual revenue growth (3pp standard deviation), gross / EBITDA margins (2pp), WACC (1pp), and terminal growth (0.5pp). Each path holds its sampled drivers constant across years. Non-positive terminal UFCF, non-positive WACC and WACC–growth spreads of 0.5pp or less are rejected, with valid draw counts displayed. These are illustrative assumption scenarios, not empirically calibrated probabilities or confidence intervals.
- **Comparables:** Yahoo trailing metrics; provider revenue growth generally represents quarterly year-over-year growth. Market capitalization / EV use quote currency; financial amounts use reporting currency. No FX conversion is performed. Multiples with non-positive denominators are N/A. Summary multiples / margins use available peers only; absolute amounts are not averaged across currencies.
- **Special industries:** banks and insurers require equity / regulatory-capital models. The app shows available historical data and KPIs but disables the generic industrial forecast and FCFF valuation for the Financial Services sector. HDFCBANK.NS is therefore supported as historical analysis, not as a bank valuation model. Cross-currency quotes / statements also disable DCF until a consistent basis is available.
- **Interpretation:** this is a generic annual research model, not a company-specific investment-banking forecast. Critical decisions require verification against filings and primary sources. It is not financial advice.

## Excel workbook

The workbook contains 20 sheets: Cover, Assumptions, Historical IS / BS / CF, Revenue Build, Working Capital, Capex & Depreciation, Debt Schedule, Forecast IS / BS / CF, DCF, Comps, Sensitivity, Scenario Analysis, KPIs, Model Checks, Dashboard, and Sources.

Blue = hardcoded inputs; green = links; black = formulas; yellow fill = editable assumptions. Monetary cells use the selected scale once, per-share prices retain full currency units, negatives use red parentheses, zeros use dashes, and sheets include frozen headings, professional headers and a dashboard chart.

Base statements, schedules, DCF and sensitivity recalculate through Excel formulas. Enter rate assumptions in Excel as decimals or percentages (for example, `12%`), unlike the app's percentage-point inputs. Scenario comparison, KPI, comparable and source-check tables are explicitly labelled captured app outputs. Regenerate the workbook through the app to refresh those tables. Excel does not refresh Yahoo data itself.

Formula outputs include independently computed cached results for preview readers. Automated tests evaluate the generated formulas, detect cycles, and change assumptions to reconcile the resulting statements and DCF against the Python engine. Native Excel application recalculation / rendering was not automated in this environment.

## Power BI

Download `Company.csv`, `Periods.csv`, `FinancialActuals.csv`, `Forecasts.csv`, `KPIs.csv`, `Valuation.csv`, `Assumptions.csv`, `ModelChecks.csv`, and `PowerBI_README.txt` individually. Values are **unscaled** and currency-labelled. The guide includes relationship keys and example DAX measures. Do not sum balance-sheet stocks across dates or sum ratios / per-share values. Select a single scenario, metric and statement when using the long-form facts. Power BI Desktop is a Windows application; the CSV exports are usable independently on macOS.

## Tests

```bash
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m pytest -q
.venv/bin/python scripts/live_smoke.py
```

The deterministic suite covers units, safe division, WACC, DCF, reverse DCF, sensitivity, reproducible simulation, cash / balance reconciliation, missing inputs, financial institutions, currency conflicts, Excel formulas and recalculation, CSV relationships, and Streamlit interactions. Live tests require internet and cover AAPL, MSFT, RELIANCE.NS and TCS.NS. Provider unavailability is reported separately rather than represented as a successful model test.

## Streamlit Community Cloud

1. Put this project in a GitHub repository, excluding `.venv`, `data/cache`, and generated exports.
2. Create an app in Streamlit Community Cloud, select the repository / branch, and set the entry point to `streamlit_app.py`.
3. Select a supported Python version, preferably 3.12 or newer. Dependencies are installed from `requirements.txt`; no secrets are needed.
4. The shared configuration leaves the bind address to the hosting platform. The Mac startup script explicitly binds to localhost for local use.

For the corrected replacement package and the older cloud-app migration, see [DEPLOYMENT.md](DEPLOYMENT.md). Build a clean ZIP using `.venv/bin/python scripts/package_project.py`; it excludes environments, caches, financial exports and secrets.

Cloud egress can be rate-limited by Yahoo; local snapshots are ephemeral on hosted instances. Review public-data usage and redistribution terms before a public deployment. See the [official Streamlit deployment guide](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app).

## Troubleshooting

- **No financials:** confirm the exact exchange suffix, retry **Refresh public data**, or choose another ticker. A missing analyst-estimate panel does not prevent a historical model.
- **DCF unavailable:** check that WACC exceeds terminal growth, terminal UFCF is positive, shares and market cap exist, currencies match, and the company is not a financial institution.
- **Port in use:** reuse the running app or start on another port using `PORT=8502 ./start_mac.sh`.
- **Install or connection errors:** verify Python and internet access. The first installation requires package downloads; later runs can use the direct Streamlit command above.

Official API references: [yfinance](https://ranaroussi.github.io/yfinance/reference/index.html), [Streamlit](https://docs.streamlit.io/develop/api-reference).
