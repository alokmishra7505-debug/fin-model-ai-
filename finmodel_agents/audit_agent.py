import numpy as np


class AuditAgent:
    name = "Model Audit Agent"

    def run(self, forecasts):
        checks = []
        for scenario, df in forecasts.items():
            max_bs = float(np.nanmax(np.abs(df.loc["Balance Check"].values))) if "Balance Check" in df.index else np.nan
            max_cf = float(np.nanmax(np.abs(df.loc["Cash Flow Check"].values))) if "Cash Flow Check" in df.index else np.nan
            checks.append({"Scenario": scenario, "Check": "Balance sheet balances", "Status": "PASS" if np.isfinite(max_bs) and max_bs < 1e-4 else "FAIL", "Max Difference": max_bs})
            checks.append({"Scenario": scenario, "Check": "Cash roll-forward reconciles", "Status": "PASS" if np.isfinite(max_cf) and max_cf < 1e-4 else "FAIL", "Max Difference": max_cf})
            if (df.loc["Revenue"] < 0).any():
                checks.append({"Scenario": scenario, "Check": "Revenue non-negative", "Status": "FAIL", "Max Difference": None})
            else:
                checks.append({"Scenario": scenario, "Check": "Revenue non-negative", "Status": "PASS", "Max Difference": 0.0})
        return checks
