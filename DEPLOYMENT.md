# Deploy the corrected base project

The screenshot's cloud app uses `finmodel_agents/export_agent.py` and a different
entry point. This project is a complete replacement base, not a one-file patch
for that older codebase. Changing this local folder does not update the cloud app.

1. Extract `FinModel_AI_ready_base.zip` into a clean folder.
2. Put its contents in the GitHub repository / branch connected to your Streamlit
   app. Keep `streamlit_app.py`, `app.py`, `requirements.txt`, `.streamlit/` and
   `finmodel_agents/` together at the repository root. Do not mix the old
   `export_agent.py` implementation into this replacement.
3. In Streamlit Community Cloud, select that branch and `streamlit_app.py` as the
   main file. Use Python 3.14, matching the locally tested environment.
4. Reboot the cloud app after the new source is deployed so its caches reload.
5. Run `TCS.NS`, open Valuation, and download the Excel workbook. Repeat with
   `AAPL`, `MSFT`, and `RELIANCE.NS`. Missing values must display as N/A; they must
   not prevent the export or expose a traceback.

No API secrets are required. The shared configuration leaves the bind address
to the hosting platform. `./start_mac.sh` explicitly binds to localhost for local
use. The deployment ZIP excludes local caches, downloaded financials, virtual
environments, secrets, and generated exports.

## Fix included

XlsxWriter cannot store NaN or Infinity as Excel numbers. Numeric cells and
formula cached results are validated before writing and display `N/A` for
unavailable values. They are not replaced with fabricated zeroes or Excel error
formulas. Unexpected Excel-export failures are contained within the download
section; the rest of the model and CSV downloads remain usable.

Reference: https://xlsxwriter.readthedocs.io/worksheet.html#worksheet-write-number

## Verify locally

```bash
./start_mac.sh
# In another terminal:
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m pytest -q
.venv/bin/python scripts/live_smoke.py
```

The live checks require internet. A successful local test does not establish
that a separately deployed cloud app has received these files.
