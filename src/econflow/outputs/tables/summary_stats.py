"""
econflow.outputs.tables.summary_stats — Summary statistics table builder.

Produces a :class:`ReportTable` of standard descriptive statistics for a
:class:`pandas.DataFrame`, one variable per row.

    Variable  |  N     Mean    Std Dev  Min    P25    P50    P75    Max
    ----------|-----------------------------------------------------------
    y         |  450   3.142   1.201   -0.12  2.34   3.08   3.92   6.44
    x1        |  450   0.000   1.000   -2.98 -0.67   0.01   0.68   2.97
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from econflow.outputs.model import ReportTable, TableRow

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fmt(value: float | None, fmt: str) -> str:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return ""
    return fmt.format(value)


# ---------------------------------------------------------------------------
# Public builder
# ---------------------------------------------------------------------------

def build_summary_stats_table(
    data: pd.DataFrame,
    *,
    variables: list[str] | None = None,
    variable_labels: dict[str, str] | None = None,
    title: str = "Summary Statistics",
    subtitle: str = "",
    fmt: str = "{:.3f}",
    int_fmt: str = "{:,}",
    percentiles: tuple[float, ...] = (0.25, 0.50, 0.75),
    include_nobs: bool = True,
    include_mean: bool = True,
    include_std: bool = True,
    include_min: bool = True,
    include_max: bool = True,
    notes: str = "",
    metadata: dict[str, Any] | None = None,
) -> ReportTable:
    """
    Build a summary statistics table from a :class:`pandas.DataFrame`.

    Parameters
    ----------
    data:
        Source data.  Only numeric columns are included.
    variables:
        Column subset to include, in order.  Defaults to all numeric columns.
    variable_labels:
        Mapping of column name to display label.
    title:
        Table title / caption.
    subtitle:
        Optional subtitle.
    fmt:
        ``str.format`` template for continuous statistics.
    int_fmt:
        ``str.format`` template for observation counts.
    percentiles:
        Percentiles to include as columns, given as fractions (e.g. 0.25).
    include_nobs, include_mean, include_std, include_min, include_max:
        Toggle individual statistic columns.
    notes:
        Free-text methodological note.
    metadata:
        Arbitrary key-value pairs stored in the table.

    Returns
    -------
    ReportTable
        A fully populated table ready for rendering.
    """
    # --- Column selection ---------------------------------------------------
    numeric_cols = data.select_dtypes(include="number").columns.tolist()
    if variables is not None:
        selected = [v for v in variables if v in data.columns]
    else:
        selected = numeric_cols

    varlabels = variable_labels or {}

    # --- Build column header list -------------------------------------------
    stat_cols: list[str] = []
    if include_nobs:
        stat_cols.append("N")
    if include_mean:
        stat_cols.append("Mean")
    if include_std:
        stat_cols.append("Std Dev")
    if include_min:
        stat_cols.append("Min")
    for p in sorted(percentiles):
        stat_cols.append(f"P{int(p * 100)}")
    if include_max:
        stat_cols.append("Max")

    table = ReportTable(
        title=title,
        table_type="summary_stats",
        columns=stat_cols,
        subtitle=subtitle,
        notes=notes,
        metadata=metadata or {},
    )

    # --- One row per variable -----------------------------------------------
    for var in selected:
        series = data[var].dropna()
        display_label = varlabels.get(var, var)

        cells: dict[str, str] = {}

        if include_nobs:
            cells["N"] = int_fmt.format(int(series.count()))
        if include_mean:
            cells["Mean"] = _fmt(float(series.mean()), fmt)
        if include_std:
            cells["Std Dev"] = _fmt(float(series.std()), fmt)
        if include_min:
            cells["Min"] = _fmt(float(series.min()), fmt)
        for p in sorted(percentiles):
            pct_label = f"P{int(p * 100)}"
            cells[pct_label] = _fmt(float(series.quantile(p)), fmt)
        if include_max:
            cells["Max"] = _fmt(float(series.max()), fmt)

        table.add_row(TableRow(
            label=display_label,
            cells=cells,
            row_type="data",
        ))

    return table
