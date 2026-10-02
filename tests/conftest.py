"""Synthetic accounting fixture for tests only; never served as actual data."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import pandas as pd
import pytest
from finmodel_agents.market_data import MarketData


@pytest.fixture
def sample_data():
    income = pd.DataFrame({pd.Timestamp("2024-12-31"):{"Total Revenue":1e9,"Cost Of Revenue":6e8,"Gross Profit":4e8,
        "Operating Income":2e8,"EBITDA":2.4e8,"Interest Expense":1e7,"Pretax Income":1.9e8,"Tax Provision":4.75e7,
        "Net Income":1.425e8,"Diluted EPS":1.425},pd.Timestamp("2025-12-31"):{"Total Revenue":1.1e9,"Cost Of Revenue":6.6e8,
        "Gross Profit":4.4e8,"Operating Income":2.2e8,"EBITDA":2.64e8,"Interest Expense":1e7,"Pretax Income":2.1e8,
        "Tax Provision":5.25e7,"Net Income":1.575e8,"Diluted EPS":1.575}})
    b = {"Cash Cash Equivalents And Short Term Investments":1e8,"Accounts Receivable":1.5e8,"Inventory":1e8,
         "Current Assets":4e8,"Net PPE":4e8,"Total Assets":1e9,"Accounts Payable":1.1e8,"Current Debt":2e7,
         "Current Liabilities":2e8,"Long Term Debt":1.8e8,"Total Debt":2e8,"Total Liabilities Net Minority Interest":5e8,
         "Stockholders Equity":5e8}
    balance = pd.DataFrame({d:b.copy() for d in income.columns})
    c = {"Operating Cash Flow":2e8,"Capital Expenditure":-6e7,"Free Cash Flow":1.4e8,"Depreciation And Amortization":4e7,
         "Net Issuance Payments Of Debt":0,"Cash Dividends Paid":-3e7}
    cashflow = pd.DataFrame({d:c.copy() for d in income.columns})
    return MarketData("TEST",{"longName":"Test Manufacturing (synthetic test fixture)","sector":"Technology","currency":"USD",
        "financialCurrency":"USD","currentPrice":20.0,"marketCap":2e9,"sharesOutstanding":1e8,"beta":1.1},income,balance,cashflow,
        retrieved_at="2026-01-01T00:00:00+00:00",source="Synthetic test fixture")
