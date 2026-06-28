"""
econflow.outputs.tables.sensitivity — Sensitivity analysis table builder (stub).

Summarises how a point estimate and inference change as a single parameter
(e.g. bandwidth, trim fraction, exclusion threshold) is varied across a grid.

Interface (full implementation in a future sprint):

    build_sensitivity_table(
        results: list[EstimationResult],
        parameter_name: str,
        parameter_values: list[Any],
        focal_variable: str,
        *,
        coef_fmt: str = "{:.3f}",
        se_fmt: str = "({:.3f})",
        star_thresholds: dict[float, str] | None = None,
        title: str = "Sensitivity Analysis",
        subtitle: str = "",
        notes: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> ReportTable
"""

from __future__ import annotations

from typing import Any

from econflow.estimation.result import EstimationResult
from econflow.outputs.model import ReportTable


def build_sensitivity_table(
    results: list[EstimationResult],
    parameter_name: str,
    parameter_values: list[Any],
    focal_variable: str,
    *,
    coef_fmt: str = "{:.3f}",
    se_fmt: str = "({:.3f})",
    star_thresholds: dict[float, str] | None = None,
    title: str = "Sensitivity Analysis",
    subtitle: str = "",
    notes: str = "",
    metadata: dict[str, Any] | None = None,
) -> ReportTable:
    """Build a sensitivity analysis table.  Not yet implemented."""
    raise NotImplementedError(
        "build_sensitivity_table is not yet implemented. "
        "See the module docstring for the planned interface."
    )
