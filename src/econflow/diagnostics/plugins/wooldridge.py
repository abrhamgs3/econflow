"""
econflow.diagnostics.plugins.wooldridge — Wooldridge autocorrelation test (stub).

Implementation plan:
* Regress first-differenced residuals on lagged first-differenced residuals.
* Test H0: coefficient = -0.5 (no serial correlation in levels).
* Reference: Wooldridge (2002), Chapter 10.
"""

from __future__ import annotations

from econflow.diagnostics.base import BaseDiagnostic
from econflow.diagnostics.registry import register_diagnostic
from econflow.estimation.result import DiagnosticResult, EstimationResult


@register_diagnostic(
    "wooldridge",
    label="Wooldridge Autocorrelation Test",
    status="stub",
    notes="H0: no first-order autocorrelation; stub — not yet implemented",
)
class WooldridgeTest(BaseDiagnostic):
    """
    Wooldridge (2002) test for first-order autocorrelation in panel data.

    **Status: stub.**  Interface complete; test logic not yet implemented.
    """

    diagnostic_id = "wooldridge"
    name = "Wooldridge Autocorrelation Test"
    description = (
        "Tests for first-order autocorrelation in panel data residuals.  "
        "H0: no serial correlation.  Not yet implemented."
    )
    supported_estimators = ["fe", "twfe", "fd"]
    required_assumptions = ["Strictly exogenous regressors"]
    output_schema = {"f_stat": "float", "f_pvalue": "float"}

    def run(self, result: EstimationResult, **kwargs: object) -> DiagnosticResult:
        raise NotImplementedError(
            "WooldridgeTest.run() is not yet implemented.  "
            "See the module docstring for the implementation plan."
        )
