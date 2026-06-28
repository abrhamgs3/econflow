"""
econflow.outputs.tables.falsification — Falsification test table builder (stub).

Presents results of placebo / falsification tests alongside the main estimate,
showing that the effect is not driven by spurious coincidence.

Interface (full implementation in a future sprint):

    build_falsification_table(
        main_result: EstimationResult,
        placebo_results: list[EstimationResult],
        focal_variable: str,
        *,
        placebo_labels: list[str] | None = None,
        coef_fmt: str = "{:.3f}",
        se_fmt: str = "({:.3f})",
        star_thresholds: dict[float, str] | None = None,
        title: str = "Falsification Tests",
        subtitle: str = "",
        notes: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> ReportTable
"""

from __future__ import annotations

from typing import Any

from econflow.estimation.result import EstimationResult
from econflow.outputs.model import ReportTable


def build_falsification_table(
    main_result: EstimationResult,
    placebo_results: list[EstimationResult],
    focal_variable: str,
    *,
    placebo_labels: list[str] | None = None,
    coef_fmt: str = "{:.3f}",
    se_fmt: str = "({:.3f})",
    star_thresholds: dict[float, str] | None = None,
    title: str = "Falsification Tests",
    subtitle: str = "",
    notes: str = "",
    metadata: dict[str, Any] | None = None,
) -> ReportTable:
    """Build a falsification test table.  Not yet implemented."""
    raise NotImplementedError(
        "build_falsification_table is not yet implemented. "
        "See the module docstring for the planned interface."
    )
