"""Live provider checks: python scripts/live_smoke.py (requires internet)."""
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from finmodel_agents.market_data import MarketDataAgent
from finmodel_agents.orchestrator import run_model
from finmodel_agents.export import excel_workbook,powerbi_files
from finmodel_agents.utils import Units


def main():
    report=[]
    for ticker in ("AAPL","MSFT","RELIANCE.NS","TCS.NS"):
        data=MarketDataAgent().fetch(ticker,use_cache=False)
        if data.income.empty:
            record={"ticker":ticker,"status":"DATA UNAVAILABLE","warnings":data.warnings}
        else:
            bundle=run_model(data)
            record={"ticker":ticker,"status":"PASS" if bundle.forecasts and not (bundle.checks.Status=="FAIL").any() else "REVIEW",
                    "currency":data.currency,"periods":bundle.historical.years,"checks":bundle.checks.to_dict("records"),
                    "notices":bundle.notices,"valuation_available":bool(bundle.valuations.get("Base") and bundle.valuations["Base"].values)}
            directory=Path("exports")/ticker
            directory.mkdir(parents=True,exist_ok=True)
            (directory/f"{ticker}_Complete_Financial_Model.xlsx").write_bytes(excel_workbook(bundle,Units(data.currency)))
            for name,contents in powerbi_files(bundle).items():
                (directory/name).write_bytes(contents)
        report.append(record)
        print(f"{ticker}: {record['status']}",flush=True)
    Path("exports/live_smoke_results.json").write_text(json.dumps(report,indent=2))
    if any(r["status"]=="REVIEW" for r in report):
        sys.exit(1)


if __name__=="__main__":
    main()
