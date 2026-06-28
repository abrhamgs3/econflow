"""
econflow.outputs.tables.regression — Regression table builder.

Converts one or more :class:`EstimationResult` objects into a single
:class:`ReportTable` in standard econometric format:

    Variable     |  (1)        (2)        (3)
    -------------|------------------------------
    x1           |  0.543***  0.521**    0.498**
                 | (0.123)   (0.215)    (0.198)
    x2           | -0.234*  -0.189
                 | (0.145)  (0.133)
    -------------|------------------------------
    Observations |   150       150        120
    R²           |   0.72      0.68       0.71
    Estimator    |   TWFE      FE         OLS
    Entity FE    |   Yes       Yes        No
    Time FE      |   Yes       No         No
"""

from __future__ import annotations

from typing import Any

from econflow.estimation.result import EstimationResult
from econflow.outputs.model import ReportTable, TableRow

# ---------------------------------------------------------------------------
# Default significance stars
# ---------------------------------------------------------------------------

DEFAULT_STARS: dict[float, str] = {
    0.01: "***",
    0.05: "**",
    0.10: "*",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _stars(pvalue: float | None, thresholds: dict[float, str]) -> str:
    """Return significance stars for *pvalue*."""
    if pvalue is None:
        return ""
    for threshold in sorted(thresholds):
        if pvalue < threshold:
            return thresholds[threshold]
    return ""


def _fmt_coef(
    coef: float,
    pvalue: float | None,
    fmt: str,
    thresholds: dict[float, str],
) -> str:
    return fmt.format(coef) + _stars(pvalue, thresholds)


def _fmt_se(se: float, fmt: str) -> str:
    return fmt.format(se)


def _collect_variables(
    results: list[EstimationResult],
    variable_order: list[str] | None,
) -> list[str]:
    """Return the union of all regressor names, preserving order."""
    seen: dict[str, None] = {}
    for r in results:
        for var in r.params.index:
            seen[str(var)] = None
    if variable_order:
        ordered = [v for v in variable_order if v in seen]
        remaining = [v for v in seen if v not in set(variable_order)]
        return ordered + remaining
    return list(seen)


# ---------------------------------------------------------------------------
# Public builder
# ---------------------------------------------------------------------------

def build_regression_table(
    results: list[EstimationResult],
    *,
    title: str = "Regression Results",
    subtitle: str = "",
    column_labels: list[str] | None = None,
    variable_order: list[str] | None = None,
    variable_labels: dict[str, str] | None = None,
    coef_fmt: str = "{:.3f}",
    se_fmt: str = "({:.3f})",
    star_thresholds: dict[float, str] | None = None,
    include_nobs: bool = True,
    include_rsquared: bool = True,
    include_fstatistic: bool = False,
    include_estimator: bool = True,
    include_entity_fe: bool = True,
    include_time_fe: bool = True,
    notes: str = "",
    metadata: dict[str, Any] | None = None,
) -> ReportTable:
    """
    Build a regression table from one or more :class:`EstimationResult` objects.

    Parameters
    ----------
    results:
        Ordered list of estimation results.  Each becomes one column.
    title:
        Table title / caption.
    subtitle:
        Optional subtitle.
    column_labels:
        Column header labels.  Defaults to ``["(1)", "(2)", ...]``.
    variable_order:
        Explicit ordering of regressors.  Variables not in this list are
        appended alphabetically.
    variable_labels:
        Mapping of regressor name to display label.
    coef_fmt:
        ``str.format`` template for coefficient values.
    se_fmt:
        ``str.format`` template for standard error values (wrapped in
        parentheses by convention).
    star_thresholds:
        Mapping of p-value threshold to star string.  Defaults to
        ``{0.01: "***", 0.05: "**", 0.10: "*"}``.
    include_nobs, include_rsquared, include_fstatistic:
        Whether to include the respective footer statistics.
    include_estimator, include_entity_fe, include_time_fe:
        Whether to include estimator metadata rows.
    notes:
        Free-text methodological note appended after the footer.
    metadata:
        Arbitrary key-value pairs stored in the table.

    Returns
    -------
    ReportTable
        A fully populated table ready for rendering.
    """
    if not results:
        raise ValueError("results must contain at least one EstimationResult")

    stars = star_thresholds or DEFAULT_STARS
    n_models = len(results)
    cols = column_labels or [f"({i + 1})" for i in range(n_models)]
    if len(cols) != n_models:
        raise ValueError(
            f"column_labels length ({len(cols)}) must match results length ({n_models})"
        )

    varlabels = variable_labels or {}
    variables = _collect_variables(results, variable_order)

    table = ReportTable(
        title=title,
        table_type="regression",
        columns=cols,
        subtitle=subtitle,
        notes=notes,
        metadata=metadata or {},
    )

    # ----- Coefficient rows -----
    for var in variables:
        coef_cells: dict[str, str] = {}
        se_cells: dict[str, str] = {}
        has_any = False

        for col, result in zip(cols, results):
            if var in result.params.index:
                coef = float(result.params[var])
                pval = float(result.pvalues[var]) if var in result.pvalues.index else None
                se = float(result.std_err[var]) if var in result.std_err.index else None
                coef_cells[col] = _fmt_coef(coef, pval, coef_fmt, stars)
                se_cells[col] = _fmt_se(se, se_fmt) if se is not None else ""
                has_any = True
            else:
                coef_cells[col] = ""
                se_cells[col] = ""

        if has_any:
            display_label = varlabels.get(var, var)
            table.add_row(TableRow(
                label=display_label,
                cells=coef_cells,
                sub_cells=se_cells,
                row_type="data",
            ))

    # ----- Separator -----
    table.add_separator()

    # ----- Footer statistics -----
    if include_nobs:
        nobs_cells = {col: str(r.nobs) for col, r in zip(cols, results)}
        table.add_row(TableRow(
            label="Observations",
            cells=nobs_cells,
            row_type="stats",
        ))

    if include_rsquared:
        r2_cells = {col: f"{r.rsquared:.3f}" for col, r in zip(cols, results)}
        table.add_row(TableRow(
            label="R²",
            cells=r2_cells,
            row_type="stats",
        ))

    if include_fstatistic:
        f_cells = {
            col: (f"{r.f_statistic:.2f}" if r.f_statistic is not None else "")
            for col, r in zip(cols, results)
        }
        table.add_row(TableRow(
            label="F-statistic",
            cells=f_cells,
            row_type="stats",
        ))

    if include_estimator:
        est_cells = {col: r.estimator_name for col, r in zip(cols, results)}
        table.add_row(TableRow(
            label="Estimator",
            cells=est_cells,
            row_type="stats",
        ))

    if include_entity_fe:
        fe_cells = {
            col: ("Yes" if r.extra.get("entity_effects", False) else "No")
            for col, r in zip(cols, results)
        }
        table.add_row(TableRow(
            label="Entity FE",
            cells=fe_cells,
            row_type="stats",
        ))

    if include_time_fe:
        tfe_cells = {
            col: ("Yes" if r.extra.get("time_effects", False) else "No")
            for col, r in zip(cols, results)
        }
        table.add_row(TableRow(
            label="Time FE",
            cells=tfe_cells,
            row_type="stats",
        ))

    # Footer notes about stars
    threshold_note = "  ".join(
        f"p<{t}: {s}" for t, s in sorted(stars.items())
    )
    table.footer.append(threshold_note)

    return table
