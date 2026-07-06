"""
econflow.diagnostics.plugins.serial_correlation — Serial correlation test (stub).

Implementation plan:
* Compute residuals per entity.
* Test first-order autocorrelation via Durbin-Watson or Arellano-Bond AR tests.
"""

from __future__ import annotations

from econflow.diagnostics.base import BaseDiagnostic
from econflow.diagnostics.registry import register_diagnostic
from econflow.estimation.result import DiagnosticResult, EstimationResult


@register_diagnostic(
    "serial_correlation",
    label="Serial Correlation Test",
    status="stub",
    notes="AR(1) test on panel residuals; stub — not yet implemented",
)
class SerialCorrelationTest(BaseDiagnostic):
    """
    Tests for first-order serial correlation in panel residuals.

    **Status: stub.**
    """

    diagnostic_id = "serial_correlation"
    name = "Serial Correlation Test"
    description = (
        "Tests for AR(1) serial correlation in panel residuals.  "
        "Not yet implemented."
    )
    supported_estimators = ["ols", "fe", "twfe", "re"]
    required_assumptions = []
    output_schema = {"statistic": "float", "pvalue": "float"}

    def run(self, result: EstimationResult, **kwargs: object) -> DiagnosticResult:
        raise NotImplementedError(
            "SerialCorrelationTest.run() is not yet implemented.  "
            "See the module docstring for the implementation plan."
        )
