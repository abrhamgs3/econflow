"""
econflow.diagnostics.plugins.vif — Variance Inflation Factor check.

Flags multicollinearity among regressors.  VIF > 10 is a common threshold.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from econflow.diagnostics.base import BaseDiagnostic
from econflow.diagnostics.registry import register_diagnostic
from econflow.estimation.result import DiagnosticResult, EstimationResult


@register_diagnostic(
    "vif",
    label="Variance Inflation Factor",
    notes="VIF > 10 indicates problematic multicollinearity",
)
class VIFCheck(BaseDiagnostic):
    """
    Variance Inflation Factor check.

    Requires the original data.  Pass it via ``run(result, data=df)``.
    """

    diagnostic_id = "vif"
    name = "Variance Inflation Factor (VIF)"
    description = (
        "Detects multicollinearity among regressors.  "
        "VIF > 5 is a mild warning; VIF > 10 is a strong warning."
    )
    supported_estimators = ["*"]
    required_assumptions = []
    output_schema = {
        "vif_values": "dict[str, float] — VIF per regressor",
        "max_vif": "float — maximum VIF",
        "threshold": "float — threshold used (default 10.0)",
    }

    def run(
        self,
        result: EstimationResult,
        *,
        data: pd.DataFrame | None = None,
        threshold: float = 10.0,
        **kwargs: object,
    ) -> DiagnosticResult:
        if data is None:
            return self._not_applicable("Pass data= to compute VIF")

        regs = list(result.params.index)
        # Drop constant if present
        regs = [r for r in regs if r.lower() not in ("const", "intercept", "constant")]
        if len(regs) < 2:
            return DiagnosticResult(
                diagnostic_id=self.diagnostic_id,
                diagnostic_name=self.name,
                conclusion="VIF not meaningful with fewer than 2 regressors.",
                level="info",
                extra={"vif_values": {}, "max_vif": float("nan"), "threshold": threshold},
            )

        available = [r for r in regs if r in data.columns]
        if not available:
            return self._not_applicable("Regressor columns not found in data")

        X = data[available].dropna().values
        if X.shape[0] < X.shape[1] + 1:
            return self._not_applicable("Insufficient observations to compute VIF")

        vif_values: dict[str, float] = {}
        try:
            from statsmodels.stats.outliers_influence import (  # noqa: PLC0415
                variance_inflation_factor,
            )
            X_with_const = np.column_stack([np.ones(len(X)), X])
            for i, var in enumerate(available):
                vif_values[var] = float(
                    variance_inflation_factor(X_with_const, i + 1)
                )
        except Exception:
            # Fallback: manual VIF via R² of auxiliary regressions
            for i, var in enumerate(available):
                other = [j for j in range(len(available)) if j != i]
                if not other:
                    continue
                try:
                    y = X[:, i]
                    Xo = np.column_stack([np.ones(len(X)), X[:, other]])
                    beta = np.linalg.lstsq(Xo, y, rcond=None)[0]
                    yhat = Xo @ beta
                    ss_res = np.sum((y - yhat) ** 2)
                    ss_tot = np.sum((y - y.mean()) ** 2)
                    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0.0
                    vif_values[var] = 1 / (1 - r2) if r2 < 1 else float("inf")
                except Exception:
                    vif_values[var] = float("nan")

        max_vif = max((v for v in vif_values.values() if v == v), default=float("nan"))
        flagged = [v for v, val in vif_values.items() if val > threshold]

        if flagged:
            conclusion = (
                f"Multicollinearity concern: {flagged} have VIF > {threshold}. "
                f"Max VIF = {max_vif:.2f}."
            )
            level = "warning"
        else:
            conclusion = f"No multicollinearity concern (max VIF = {max_vif:.2f} < {threshold})."
            level = "info"

        return DiagnosticResult(
            diagnostic_id=self.diagnostic_id,
            diagnostic_name=self.name,
            statistic=max_vif if max_vif == max_vif else None,
            conclusion=conclusion,
            level=level,
            extra={"vif_values": vif_values, "max_vif": max_vif, "threshold": threshold},
        )
