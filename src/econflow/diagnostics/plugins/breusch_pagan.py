"""
econflow.diagnostics.plugins.breusch_pagan — Breusch-Pagan heteroskedasticity test.

Tests H0: homoskedastic residuals.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from econflow.diagnostics.base import BaseDiagnostic
from econflow.diagnostics.registry import register_diagnostic
from econflow.estimation.result import DiagnosticResult, EstimationResult


@register_diagnostic(
    "breusch_pagan",
    label="Breusch-Pagan Test",
    notes="H0: homoskedastic residuals; requires data= argument",
)
class BreuschPagan(BaseDiagnostic):
    """
    Breusch-Pagan test for heteroskedasticity.

    Usage: ``run(result, data=df)``
    """

    diagnostic_id = "breusch_pagan"
    name = "Breusch-Pagan Test"
    description = (
        "Tests whether the residual variance is constant across observations.  "
        "H0: homoskedasticity.  Rejection suggests heteroskedastic residuals, "
        "in which case robust standard errors should be used."
    )
    supported_estimators = ["ols", "fe", "twfe", "re"]
    required_assumptions = ["Residuals approximately normally distributed"]
    output_schema = {
        "lm_stat": "float — Lagrange multiplier statistic",
        "lm_pvalue": "float — p-value for LM test",
        "f_stat": "float — F-statistic alternative",
        "f_pvalue": "float — F-test p-value",
    }

    def run(
        self,
        result: EstimationResult,
        *,
        data: pd.DataFrame | None = None,
        **kwargs: object,
    ) -> DiagnosticResult:
        if data is None:
            return self._not_applicable("Pass data= to compute residuals")

        dep = result.provenance.get("params", {}).get("dependent", "")
        regs = result.provenance.get("params", {}).get("regressors", [])
        if not dep or not regs:
            return self._not_applicable("Cannot determine dependent/regressors from provenance")

        available = [c for c in [dep] + list(regs) if c in data.columns]
        if dep not in available or len(regs) == 0:
            return self._not_applicable("Required columns not found in data")

        subset = data.dropna(subset=[dep] + list(regs))
        y = subset[dep].values
        X = subset[list(regs)].values

        try:
            from statsmodels.stats.diagnostic import het_breuschpagan  # noqa: PLC0415
            X_const = np.column_stack([np.ones(len(X)), X])
            beta = np.linalg.lstsq(X_const, y, rcond=None)[0]
            residuals = y - X_const @ beta
            lm, lm_p, f_stat, f_p = het_breuschpagan(residuals, X_const)
        except Exception as exc:
            return self._not_applicable(f"Computation failed: {exc}")

        if lm_p < 0.05:
            conclusion = (
                f"Reject H0 (LM={lm:.3f}, p={lm_p:.4f}): heteroskedasticity detected. "
                "Use robust or clustered standard errors."
            )
            level = "warning"
        else:
            conclusion = (
                f"Fail to reject H0 (LM={lm:.3f}, p={lm_p:.4f}): "
                "no significant heteroskedasticity."
            )
            level = "info"

        return DiagnosticResult(
            diagnostic_id=self.diagnostic_id,
            diagnostic_name=self.name,
            statistic=float(lm),
            pvalue=float(lm_p),
            conclusion=conclusion,
            level=level,
            extra={"lm_stat": float(lm), "lm_pvalue": float(lm_p),
                   "f_stat": float(f_stat), "f_pvalue": float(f_p)},
        )
