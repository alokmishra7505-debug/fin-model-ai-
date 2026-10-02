"""Exercise the full UI using real snapshots produced by live_smoke.py.

Skipped on fresh checkouts until the explicit network smoke test has run.
"""
from pathlib import Path
import pytest
from streamlit.testing.v1 import AppTest
from finmodel_agents.market_data import MarketDataAgent


@pytest.mark.parametrize("ticker",["AAPL","MSFT","RELIANCE.NS","TCS.NS"])
def test_real_company_dashboard(ticker):
    data=MarketDataAgent()._load(ticker)
    if data is None:
        pytest.skip("Run scripts/live_smoke.py to create real provider snapshots")
    at=AppTest.from_file(str(Path(__file__).resolve().parents[1]/"streamlit_app.py"),default_timeout=60)
    at.session_state["company"]=data
    at.session_state["peers"]=[]
    at.run()
    assert not at.exception
    assert not at.error
    assert len(at.tabs)==10
    assert len(at.get("download_button"))==10
    assert not at.get("json")
    assert not at.get("code")
    next(x for x in at.selectbox if x.label=="Display units").set_value("Billion").run()
    assert not at.exception
    assert not at.error
