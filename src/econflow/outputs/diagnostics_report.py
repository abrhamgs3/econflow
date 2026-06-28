"""
econflow.outputs.diagnostics_report — Diagnostics report builder.

Converts a list of :class:`~econflow.estimation.result.DiagnosticResult`
objects into a :class:`~econflow.outputs.model.ReportTable` suitable for
inclusion in a publication appendix.

Table layout::

    Test              | Estimator  | Statistic  | p-value   | Conclusion
    ------------------|------------|------------|-----------|---------------
    Hausman           | fe         | 14.23      | 0.007     | Reject RE
    Breusch-Pagan LM  | ols        | 8.41       | 0.015     | Heteroskedastic
    ...
"""

from __future__ import annotations

from typing import Any

from econflow.estimation.result import DiagnosticResult
from econflow.outputs.model import ReportTable, TableRow

# Column names
_COLUMNS = ["Estimator", "Statistic", "p-value", "Conclusion"]


def _fmt_stat(value: float | None, fmt: str = "{:.3f}") -> str:
    return fmt.format(value) if value is not None else "—"


def _conclusion(result: DiagnosticResult) -> str:
    """Return a short human-readable conclusion string."""
    if result.level == "skip":
        return "N/A"
    # Infer pass/fail from level
    if result.level in ("error", "warning"):
        return "Fail"
    if result.level == "info":
        return "Pass"
    return result.conclusion[:40] if result.conclusion else "—"


def build_diagnostics_report(
    results: list[DiagnosticResult],
    *,
    title: str = "Diagnostic Test Results",
    subtitle: str = "",
    stat_fmt: str = "{:.3f}",
    group_by_estimator: bool = True,
    notes: str = "",
    metadata: dict[str, Any] | None = None,
) -> ReportTable:
    """
    Build a diagnostics summary table.

    Parameters
    ----------
    results:
        Flat list of :class:`DiagnosticResult` objects from one or more
        estimator runs.
    title:
        Table title / caption.
    subtitle:
        Optional subtitle.
    stat_fmt:
        ``str.format`` template for the test statistic.
    group_by_estimator:
        If ``True``, insert a separator row between estimator groups.
    notes:
        Free-text methodological note.
    metadata:
        Arbitrary key-value pairs stored in the table.

    Returns
    -------
    ReportTable
    """
    table = ReportTable(
        title=title,
        table_type="diagnostics",
        columns=_COLUMNS,
        subtitle=subtitle,
        notes=notes,
        metadata=metadata or {},
    )

    if not results:
        return table

    if group_by_estimator:
        # Group by estimator_id preserving insertion order
        groups: dict[str, list[DiagnosticResult]] = {}
        for r in results:
            groups.setdefault(r.extra.get("estimator_id", ""), []).append(r)

        first_group = True
        for estimator_id, group in groups.items():
            if not first_group:
                table.add_separator()
            first_group = False

            for r in group:
                _add_row(table, r, stat_fmt)
    else:
        for r in results:
            _add_row(table, r, stat_fmt)

    # Footer
    table.footer.append(
        "Pass = null hypothesis not rejected at α=0.05; "
        "Fail = null hypothesis rejected; N/A = diagnostic not applicable."
    )

    return table


def _add_row(
    table: ReportTable,
    result: DiagnosticResult,
    stat_fmt: str,
) -> None:
    """Append a single diagnostic row to *table*."""
    pval_str = _fmt_stat(result.pvalue, stat_fmt) if result.pvalue is not None else "—"
    stat_str = _fmt_stat(result.statistic, stat_fmt)

    table.add_row(TableRow(
        label=result.diagnostic_name,
        cells={
            "Estimator": result.extra.get("estimator_id", ""),
            "Statistic": stat_str,
            "p-value": pval_str,
            "Conclusion": _conclusion(result),
        },
        row_type="data",
    ))
