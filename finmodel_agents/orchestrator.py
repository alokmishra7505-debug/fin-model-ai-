import pandas as pd
import yfinance as yf

from .resolver_agent import CompanyResolverAgent
from .data_agent import MarketDataAgent
from .normalize_agent import NormalizationAgent
from .schedule_agent import ScheduleAgent
from .three_statement_agent import ThreeStatementAgent
from .valuation_agent import ValuationAgent
from .kpi_agent import KPIAgent
from .audit_agent import AuditAgent
from .comps_agent import CompsAgent
from .consensus_agent import ConsensusAgent
from .reverse_dcf_agent import ReverseDCFAgent
from .monte_carlo_agent import MonteCarloAgent
from .export_agent import ExportAgent


class FinancialModelOrchestrator:
    def __init__(self):
        self.resolver_agent = CompanyResolverAgent()
        self.data_agent = MarketDataAgent()
        self.norm_agent = NormalizationAgent()
        self.schedule_agent = ScheduleAgent()
        self.three_statement_agent = ThreeStatementAgent()
        self.valuation_agent = ValuationAgent()
        self.kpi_agent = KPIAgent()
        self.audit_agent = AuditAgent()
        self.comps_agent = CompsAgent()
        self.consensus_agent = ConsensusAgent()
        self.reverse_dcf_agent = ReverseDCFAgent()
        self.monte_carlo_agent = MonteCarloAgent()
        self.export_agent = ExportAgent()

    def run(self, company_or_ticker, overrides=None, peer_tickers=None, years=5, simulations=500):
        resolved = self.resolver_agent.resolve(company_or_ticker)
        ticker = resolved["ticker"]
        data = self.data_agent.fetch(ticker)
        hist = self.norm_agent.run(data)

        assumptions = self.schedule_agent.derive(hist, data.info)
        if overrides:
            for k, v in overrides.items():
                if v is not None:
                    assumptions[k] = v

        forecasts = {}
        scenario_assumptions = {}
        for scenario in ["Bear", "Base", "Bull"]:
            a = self.schedule_agent.scenario(assumptions, scenario)
            scenario_assumptions[scenario] = a
            forecasts[scenario] = self.three_statement_agent.run(hist, a, years=years)

        combined = pd.concat([hist, forecasts["Base"]], axis=1)
        kpis = self.kpi_agent.run(combined)
        flags = self.kpi_agent.flags(kpis)

        valuation = self.valuation_agent.dcf(
            data.info,
            hist,
            forecasts["Base"],
            terminal_growth=assumptions.get("terminal_growth", 0.025),
            risk_free=assumptions.get("risk_free_rate", 0.043),
            erp=assumptions.get("equity_risk_premium", 0.055),
        )
        sensitivity = self.valuation_agent.sensitivity(data.info, hist, forecasts["Base"])
        reverse_dcf = self.reverse_dcf_agent.run(
            self.valuation_agent, data.info, hist, forecasts["Base"],
            terminal_growth=assumptions.get("terminal_growth", 0.025)
        )
        monte_carlo = self.monte_carlo_agent.run(
            self.valuation_agent, data.info, hist, forecasts["Base"], assumptions,
            simulations=simulations
        )

        peers = peer_tickers or []
        comps = self.comps_agent.run(peers)
        comps_summary = self.comps_agent.summary(comps)

        try:
            consensus = self.consensus_agent.run(yf.Ticker(ticker))
        except Exception:
            consensus = {}

        audit = self.audit_agent.run(forecasts)
        meta = {
            "Input": company_or_ticker,
            "Resolved Ticker": ticker,
            "Ticker": ticker,
            "Company": data.info.get("longName") or resolved.get("name") or ticker,
            "Currency": data.info.get("currency"),
            "Exchange": data.info.get("exchange") or resolved.get("exchange"),
            "Sector": data.info.get("sector"),
            "Industry": data.info.get("industry"),
            "Data Timestamp UTC": data.timestamp_utc,
            "Source": "Yahoo Finance via yfinance",
            "Forecast Method": "Deterministic integrated 3-statement driver model",
            "Forecast Years": years,
            "Important": "Actuals, available analyst consensus, and model-generated forecasts are kept separate.",
        }
        return {
            "data": data,
            "resolved": resolved,
            "historical": hist,
            "assumptions": assumptions,
            "scenario_assumptions": scenario_assumptions,
            "forecasts": forecasts,
            "combined": combined,
            "kpis": kpis,
            "valuation": valuation,
            "sensitivity": sensitivity,
            "reverse_dcf": reverse_dcf,
            "monte_carlo": monte_carlo,
            "comps": comps,
            "comps_summary": comps_summary,
            "consensus": consensus,
            "audit": audit,
            "flags": flags,
            "meta": meta,
        }
