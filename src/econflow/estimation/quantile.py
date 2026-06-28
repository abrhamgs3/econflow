"""
econflow.estimation.quantile — Panel quantile regression (stub).

Implementation plan:
* Use ``statsmodels.regression.quantile_regression.QuantReg`` for pooled
  quantile regression as a first step.
* A full panel quantile estimator (Koenker 2004, or Canay 2011) requires
  additional implementation work.
"""

from __future__ import annotations

import pandas as pd

from econflow.estimation.base import BaseEstimator, EstimationResult
from econflow.estimation.registry import register
from econflow.estimation.result import DiagnosticResult


@register(
    "quantile",
    label="Panel Quantile Regression",
    status="stub",
    notes="Koenker (2004) / Canay (2011); not yet implemented",
    supported_data=["balanced_panel", "unbalanced_panel"],
)
class PanelQuantile(BaseEstimator):
    """
    Panel quantile regression estimator.

    **Status: stub.**  Interface is complete; estimation logic is not yet
    implemented.  Calling :meth:`fit` raises ``NotImplementedError``.

    Parameters (``params`` dict keys)
    -----------------------------------
    dependent : str   Required.
    regressors : list[str]   Required.
    quantile : float   Quantile to estimate (e.g. ``0.5`` for median).  Default ``0.5``.
    entity_col : str   Default ``"entity"``.
    time_col : str   Default ``"time"``.
    """

    estimator_id = "quantile"
    name = "Panel Quantile Regression"
    description = (
        "Panel quantile regression (Koenker 2004 / Canay 2011).  "
        "Estimates conditional quantiles of the dependent variable.  "
        "Not yet implemented."
    )
    supported_data = ["balanced_panel", "unbalanced_panel"]
    required_parameters = ["dependent", "regressors"]
    optional_parameters = {
        "quantile": 0.5,
        "entity_col": "entity",
        "time_col": "time",
    }

    def validate(self, data: pd.DataFrame) -> None:
        self._require_params("dependent", "regressors")
        q = self.params.get("quantile", 0.5)
        if not (0 < q < 1):
            from econflow.estimation.base import EstimatorError  # noqa: PLC0415
            raise EstimatorError(
                f"quantile must be in (0, 1), got {q}.",
                estimator_id=self.estimator_id,
            )

    def fit(self, data: pd.DataFrame) -> EstimationResult:
        raise NotImplementedError(
            "PanelQuantile.fit() is not yet implemented.  "
            "This estimator is a documented stub.  "
            "See the module docstring for the implementation plan."
        )

    def diagnostics(self, result: EstimationResult) -> list[DiagnosticResult]:
        return []
