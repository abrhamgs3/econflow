"""
econflow.outputs.tables.heterogeneity — Heterogeneity analysis table builder (stub).

Displays sub-group estimates to explore whether the average treatment effect
is driven by particular segments of the sample.

Interface (full implementation in a future sprint):

    build_heterogeneity_table(
        results: list[EstimationResult],
        focal_variable: str,
        *,
        group_labels: list[str] | None = None,
        coef_fmt: str = "{:.3f}",
        se_fmt: str = "({:.3f})",
        star_thresholds: dict[float, str] | None = None,
        include_nobs: bool = True,
        title: str = "Heterogeneity Analysis",
        subtitle: str = "",
        notes: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> ReportTable
"""

from __future__ import annotations

from typing import Any

from econflow.estimation.result import EstimationResult
from econflow.outputs.model import ReportTable


def build_heterogeneity_table(
    results: list[EstimationResult],
    focal_variable: str,
    *,
    group_labels: list[str] | None = None,
    coef_fmt: str = "{:.3f}",
    se_fmt: str = "({:.3f})",
    star_thresholds: dict[float, str] | None = None,
    include_nobs: bool = True,
    title: str = "Heterogeneity Analysis",
    subtitle: str = "",
    notes: str = "",
    metadata: dict[str, Any] | None = None,
) -> ReportTable:
    """Build a heterogeneity analysis table.  Not yet implemented."""
    raise NotImplementedError(
        "build_heterogeneity_table is not yet implemented. "
        "See the module docstring for the planned interface."
    )
