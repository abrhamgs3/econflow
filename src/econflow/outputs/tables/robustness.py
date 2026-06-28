"""
econflow.outputs.tables.robustness — Robustness check table builder (stub).

Displays the same focal coefficient across multiple specifications, making
it easy to see how stable the estimate is under different modelling choices.

Interface (full implementation in a future sprint):

    build_robustness_table(
        results: list[EstimationResult],
        focal_variable: str,
        *,
        column_labels: list[str] | None = None,
        coef_fmt: str = "{:.3f}",
        se_fmt: str = "({:.3f})",
        star_thresholds: dict[float, str] | None = None,
        spec_labels: dict[str, str] | None = None,
        title: str = "Robustness Checks",
        subtitle: str = "",
        notes: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> ReportTable
"""

from __future__ import annotations

from typing import Any

from econflow.estimation.result import EstimationResult
from econflow.outputs.model import ReportTable


def build_robustness_table(
    results: list[EstimationResult],
    focal_variable: str,
    *,
    column_labels: list[str] | None = None,
    coef_fmt: str = "{:.3f}",
    se_fmt: str = "({:.3f})",
    star_thresholds: dict[float, str] | None = None,
    spec_labels: dict[str, str] | None = None,
    title: str = "Robustness Checks",
    subtitle: str = "",
    notes: str = "",
    metadata: dict[str, Any] | None = None,
) -> ReportTable:
    """Build a robustness check table.  Not yet implemented."""
    raise NotImplementedError(
        "build_robustness_table is not yet implemented. "
        "See the module docstring for the planned interface."
    )
