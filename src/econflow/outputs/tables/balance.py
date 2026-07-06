"""
econflow.outputs.tables.balance — Balance table builder (stub).

Compares means across treatment and control groups, optionally including
p-values from t-tests for equality of means.

Interface (full implementation in a future sprint):

    build_balance_table(
        data: pd.DataFrame,
        *,
        group_col: str,
        variables: list[str] | None = None,
        variable_labels: dict[str, str] | None = None,
        treatment_value: Any = 1,
        control_value: Any = 0,
        fmt: str = "{:.3f}",
        include_pvalue: bool = True,
        title: str = "Balance Table",
        subtitle: str = "",
        notes: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> ReportTable
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from econflow.outputs.model import ReportTable


def build_balance_table(
    data: pd.DataFrame,
    *,
    group_col: str,
    variables: list[str] | None = None,
    variable_labels: dict[str, str] | None = None,
    treatment_value: Any = 1,
    control_value: Any = 0,
    fmt: str = "{:.3f}",
    include_pvalue: bool = True,
    title: str = "Balance Table",
    subtitle: str = "",
    notes: str = "",
    metadata: dict[str, Any] | None = None,
) -> ReportTable:
    """Build a covariate balance table.  Not yet implemented."""
    raise NotImplementedError(
        "build_balance_table is not yet implemented. "
        "See the module docstring for the planned interface."
    )
