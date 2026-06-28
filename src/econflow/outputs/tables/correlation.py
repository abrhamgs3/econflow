"""
econflow.outputs.tables.correlation — Correlation matrix table builder (stub).

Renders a pairwise Pearson (or Spearman) correlation matrix as a lower-
triangular or full :class:`ReportTable`.

Interface (full implementation in a future sprint):

    build_correlation_table(
        data: pd.DataFrame,
        *,
        variables: list[str] | None = None,
        variable_labels: dict[str, str] | None = None,
        method: str = "pearson",   # "pearson" | "spearman" | "kendall"
        lower_triangle: bool = True,
        fmt: str = "{:.3f}",
        include_pvalue: bool = False,
        title: str = "Correlation Matrix",
        subtitle: str = "",
        notes: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> ReportTable
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from econflow.outputs.model import ReportTable


def build_correlation_table(
    data: pd.DataFrame,
    *,
    variables: list[str] | None = None,
    variable_labels: dict[str, str] | None = None,
    method: str = "pearson",
    lower_triangle: bool = True,
    fmt: str = "{:.3f}",
    include_pvalue: bool = False,
    title: str = "Correlation Matrix",
    subtitle: str = "",
    notes: str = "",
    metadata: dict[str, Any] | None = None,
) -> ReportTable:
    """Build a pairwise correlation matrix table.  Not yet implemented."""
    raise NotImplementedError(
        "build_correlation_table is not yet implemented. "
        "See the module docstring for the planned interface."
    )
