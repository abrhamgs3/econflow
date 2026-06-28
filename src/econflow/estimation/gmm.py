"""
econflow.estimation.gmm — System GMM estimator (stub).

Implementation plan:
* Use ``linearmodels.IV2SLS`` for a limited-information version, or
* Integrate ``pydynpd`` (Arellano-Bond / Blundell-Bond) once available.
"""

from __future__ import annotations

import pandas as pd

from econflow.estimation.base import BaseEstimator, EstimationResult
from econflow.estimation.registry import register
from econflow.estimation.result import DiagnosticResult


@register(
    "gmm",
    label="System GMM",
    status="stub",
    notes="Arellano-Bond / Blundell-Bond; not yet implemented",
    supported_data=["balanced_panel", "unbalanced_panel"],
)
class SystemGMM(BaseEstimator):
    """
    System GMM estimator (Arellano-Bond / Blundell-Bond).

    **Status: stub.** Interface is complete; estimation logic is not yet
    implemented.  Calling :meth:`fit` raises ``NotImplementedError``.

    Parameters (``params`` dict keys)
    -----------------------------------
    dependent : str   Required.
    regressors : list[str]   Required.
    endog : list[str]   Endogenous regressors.  Default ``[]``.
    lags : int   Number of lags to use as instruments.  Default ``2``.
    entity_col : str   Default ``"entity"``.
    time_col : str   Default ``"time"``.
    """

    estimator_id = "gmm"
    name = "System GMM"
    description = (
        "Dynamic panel estimator (Arellano-Bond / Blundell-Bond system GMM).  "
        "Addresses endogeneity and lagged-dependent-variable bias via moment "
        "conditions.  Not yet implemented."
    )
    supported_data = ["balanced_panel", "unbalanced_panel"]
    required_parameters = ["dependent", "regressors"]
    optional_parameters = {
        "endog": [],
        "lags": 2,
        "entity_col": "entity",
        "time_col": "time",
    }

    def validate(self, data: pd.DataFrame) -> None:
        self._require_params("dependent", "regressors")

    def fit(self, data: pd.DataFrame) -> EstimationResult:
        raise NotImplementedError(
            "SystemGMM.fit() is not yet implemented.  "
            "This estimator is a documented stub.  "
            "See the module docstring for the implementation plan."
        )

    def diagnostics(self, result: EstimationResult) -> list[DiagnosticResult]:
        return []
