"""
Panel data validation for EconFlow.

A validation report is a plain dict — no custom classes.  This makes it easy
to serialise to JSON, log, and pass across process boundaries.

Blockers vs. warnings
---------------------
``report_has_blockers`` distinguishes hard failures (missing required columns,
duplicate panel keys) from soft warnings (high missingness in optional columns).
The pipeline aborts on blockers; warnings are logged and continue.

Configurable schema
-------------------
The module-level ``DEFAULT_REQUIRED_COLUMNS`` is used when no ``required_columns``
argument is passed to :func:`validate_data`.  Downstream projects should pass
their own column list rather than relying on the default.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from econflow.data.loaders import load_panel
from econflow.logging import get_logger

log = get_logger(__name__)

# Default required columns (reference implementation: AI & Productivity paper).
# Pass a different list to validate_data() to use a custom schema.
DEFAULT_REQUIRED_COLUMNS: list[str] = [
    "country", "year", "ln_ai", "ln_tfp", "ln_hc", "ln_gdp"
]

# Deprecated alias kept for backward compatibility — use DEFAULT_REQUIRED_COLUMNS.
REQUIRED_COLUMNS = DEFAULT_REQUIRED_COLUMNS


def validate_data(
    path: str | Path,
    required_columns: list[str] | None = None,
    entity_col: str = "country",
    time_col: str = "year",
    log_vars: list[str] | None = None,
) -> dict:
    """Run schema and quality checks on a panel CSV.

    Parameters
    ----------
    path:
        Path to the panel CSV.
    required_columns:
        Columns that must be present.  Defaults to ``DEFAULT_REQUIRED_COLUMNS``.
        Pass an explicit list to validate a custom dataset schema.
    entity_col:
        Column identifying the cross-sectional entity (default: ``"country"``).
    time_col:
        Column identifying the time period (default: ``"year"``).
    log_vars:
        Numeric columns expected to be finite (e.g. log-transformed variables).
        Defaults to the intersection of the required columns and the DataFrame
        columns that start with ``"ln_"``.

    Returns
    -------
    dict
        Validation report with keys: ``path``, ``required_columns``,
        ``missing_columns``, ``duplicate_panel_keys``,
        ``missing_by_column``, ``log_vars_non_finite``, ``coverage``.
    """
    required_columns = required_columns if required_columns is not None else DEFAULT_REQUIRED_COLUMNS  # noqa: E501
    log.info("Validating panel at %s", path)

    df = load_panel(path)

    # ── required columns ───────────────────────────────────────────────────
    missing_columns = [c for c in required_columns if c not in df.columns]
    if missing_columns:
        log.warning("Required columns missing: %s", missing_columns)

    # ── duplicate panel keys ───────────────────────────────────────────────
    panel_key = [c for c in (entity_col, time_col) if c in df.columns]
    duplicate_panel_keys = 0
    if len(panel_key) == 2:
        duplicate_panel_keys = int(df.duplicated(panel_key).sum())
        if duplicate_panel_keys:
            log.warning("Duplicate (%s, %s) rows: %d", entity_col, time_col, duplicate_panel_keys)

    # ── missingness ────────────────────────────────────────────────────────
    missing_by_column = {k: int(v) for k, v in df.isna().sum().to_dict().items()}

    # ── coverage ───────────────────────────────────────────────────────────
    coverage: dict[str, int] = {"rows": int(len(df))}
    if entity_col in df.columns:
        coverage["entities"] = int(df[entity_col].nunique())
    if time_col in df.columns:
        coverage["periods"] = int(df[time_col].nunique())
    log.info("Coverage: %s", coverage)

    # ── non-finite check on log-transformed variables ──────────────────────
    if log_vars is None:
        log_vars = [c for c in df.columns if c.startswith("ln_")]
    log_vars_non_finite: dict[str, int] = {}
    for col in log_vars:
        if col in df.columns:
            series = pd.to_numeric(df[col], errors="coerce")
            non_finite = int(
                (~series.replace([float("inf"), float("-inf")], pd.NA).notna()).sum()
            )
            log_vars_non_finite[col] = non_finite
            if non_finite:
                log.warning("%s has %d non-finite values", col, non_finite)

    report = {
        "path": str(path),
        "required_columns": required_columns,
        "missing_columns": missing_columns,
        "duplicate_panel_keys": duplicate_panel_keys,
        # keep old key for backward compat with callers that read this field by name
        "duplicate_country_year": duplicate_panel_keys,
        "missing_by_column": missing_by_column,
        "log_vars_non_finite": log_vars_non_finite,
        "coverage": coverage,
    }
    log.info("Validation complete — blockers: %s", report_has_blockers(report))
    return report


def report_has_blockers(report: dict) -> bool:
    """Return ``True`` if the validation report contains pipeline-blocking issues."""
    if report.get("missing_columns"):
        return True
    if report.get("duplicate_panel_keys", 0) > 0:
        return True
    return False


def save_validation_report(report: dict, output_path: str | Path) -> None:
    """Write the validation report to a JSON file.

    Parameters
    ----------
    report:
        Dict returned by :func:`validate_data`.
    output_path:
        Destination path (parent directories are created if needed).
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    log.debug("Validation report saved to %s", output_path)
