from types import SimpleNamespace
from datetime import date
from io import BytesIO
from zipfile import ZipFile
import pandas as pd
import pytest
from finmodel_agents import market_data
from finmodel_agents.nse_data import NSEArchiveAgent, parse_indas_filing


def filing(symbol='TCS',start='01-04-2025',currency='INR'):
    tables = [
        [('NSE Symbol',symbol),('Name of company','Test issuer'),('Nature of report standalone or consolidated','Consolidated'),('Description of presentation currency',currency),('Level of rounding used in financial results','Lakhs')],
        [('Date of end of reporting period','31-03-2026'),('Date of start of reporting period',start),('Revenue from operations','2,67,02,100'),('Diluted earnings (loss) per share from continuing and discontinued operations','136.01')],
        [('Date of end of reporting period','31-03-2026'),('Total assets','1,82,37,200')],
        [('Date of end of reporting period','31-03-2026'),('Date of start of reporting period',start),('Net cash flows from (used in) operating activities','52,09,400')]]
    return '<html>'+''.join('<table>'+''.join('<tr>'+''.join('<td>'+x+'</td>' for x in row)+'</tr>' for row in rows)+'</table>' for rows in tables)+'</html>'


def test_nse_units_and_period_validation():
    p,i,b,c=parse_indas_filing(filing(),'TCS')
    assert p['financialCurrency']=='INR'
    assert i.iloc[:,0]['Total Revenue']==2670210000000
    assert i.iloc[:,0]['Diluted EPS']==136.01
    for content in (filing(symbol='OTHER'),filing(start='01-01-2026'),filing(currency='USD')):
        with pytest.raises(ValueError): parse_indas_filing(content,'TCS')


def test_empty_yahoo_profile_uses_official_fallback(sample_data,monkeypatch,tmp_path):
    obj=SimpleNamespace(info={},income_stmt=sample_data.income,balance_sheet=sample_data.balance,cashflow=sample_data.cashflow,revenue_estimate=pd.DataFrame(),earnings_estimate=pd.DataFrame())
    monkeypatch.setattr(market_data.yf,'Ticker',lambda _:obj)
    monkeypatch.setattr(market_data,'ROOT',tmp_path)
    monkeypatch.setattr(NSEArchiveAgent,'profile',lambda self,symbol:{'longName':'Tata Consultancy Services Limited','currency':'INR','exchange':'NSE'})
    monkeypatch.setattr(NSEArchiveAgent,'annual_filing',lambda *args:None)
    monkeypatch.setattr(NSEArchiveAgent,'closing_quote',lambda *args:{'currentPrice':3000.,'priceAsOf':'2026-10-01','priceSourceUrl':'https://nsearchives.nseindia.com/test'})
    d=market_data.MarketDataAgent().fetch('TCS.NS',use_cache=False)
    assert d.currency=='INR'
    assert d.name=='Tata Consultancy Services Limited'
    assert d.info['currentPrice']==3000
    assert len(d.provenance)>=2


def test_bhavcopy_dated_close(monkeypatch,tmp_path):
    out=BytesIO()
    with ZipFile(out,'w') as z:
        z.writestr('daily.csv','TckrSymb,SctySrs,TradDt,ClsPric\nTCS,EQ,2026-10-01,3000\n')
    monkeypatch.setattr(NSEArchiveAgent,'download',lambda *args,**kw:out.getvalue())
    quote=NSEArchiveAgent(tmp_path).closing_quote('TCS',date(2026,10,2))
    assert quote['currentPrice']==3000
    assert quote['priceAsOf']=='2026-10-01'
    assert 'not live' in quote['priceBasis']
