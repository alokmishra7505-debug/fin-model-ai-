from streamlit.testing.v1 import AppTest
from pathlib import Path
import pandas as pd

APP = str(Path(__file__).resolve().parents[1]/"streamlit_app.py")


def test_landing_page():
    at=AppTest.from_file(APP,default_timeout=60).run()
    assert not at.exception
    assert not at.error
    assert len(at.get("json"))==0
    assert len(at.get("code"))==0


def test_complete_dashboard_and_assumption_update(sample_data):
    at=AppTest.from_file(APP,default_timeout=60)
    at.session_state["company"]=sample_data
    at.session_state["peers"]=[]
    at.run()
    assert not at.exception
    assert not at.error
    assert len(at.tabs)==10
    assert len(at.get("json"))==0
    assert len(at.get("code"))==0
    assert len(at.get("download_button"))==10
    growth=next(x for x in at.number_input if x.label=="Revenue growth (%)")
    growth.set_value(12.0)
    next(x for x in at.button if x.label=="Apply assumptions").click()
    at.run()
    assert not at.exception
    assert not at.error
    assert at.session_state["assumptions_TEST"].growth==.12
    at.radio[0].set_value("Bull").run()
    assert not at.error


def test_missing_annual_data_has_clean_message(sample_data):
    sample_data.income=sample_data.income.iloc[:,0:0]
    at=AppTest.from_file(APP,default_timeout=60)
    at.session_state["company"]=sample_data
    at.run()
    assert not at.exception
    assert not at.error
    assert any("needs annual statements" in x.value for x in at.info)


def test_consensus_and_missing_peer_metrics(sample_data,monkeypatch):
    import app
    sample_data.estimates={"Revenue estimates":pd.DataFrame({"numberOfAnalysts":[12],"avg":[1.2e9],"low":[1.1e9],"high":[1.3e9],"growth":[.1]},index=["+1y"])}
    peer=pd.DataFrame([{"Ticker":"PEER","Company":"Peer company","Currency":"USD","Quote Currency":"USD","Market Cap":1e9,
        "EV":1.1e9,"Revenue":5e8,"EBITDA":float("nan"),"Net Income":1e7,"Revenue Growth":.1,"EBITDA Margin":float("nan"),
        "EV / Revenue":2.2,"EV / EBITDA":float("nan"),"P/E":100.0,"Retrieved":"2026-01-01"}])
    monkeypatch.setattr(app,"fetch_peers",lambda tickers:(peer,[]))
    at=AppTest.from_file(APP,default_timeout=60)
    at.session_state["company"]=sample_data
    at.session_state["peers"]=["PEER"]
    at.run()
    assert not at.exception
    assert not at.error
    assert not at.get("json")
    assert any("Revenue estimates" in m.value for m in at.markdown)
