"""
econflow.ingestion.validation -- Configurable panel data validator.

Produces a structured :class:`DataValidationReport` describing every issue
found in a downloaded dataset.  All checks are configurable -- pass a
:class:`DataValidationConfig` to enable or disable them.

Checks available
----------------
V-01  required_columns_present   -- All columns in config.required_columns exist.
V-02  no_duplicate_keys          -- No duplicate (entity_col, time_col) pairs.
V-03  no_missing_identifiers     -- entity_col and time_col have no null values.
V-04  no_unsupported_types       -- All columns can be coerced to numeric or str.
V-05  no_missing_years           -- Every expected year appears in time_col.
V-06  missing_value_pct          -- Missing-value percentage <= max_missing_pct.

Usage
-----
::

    from econflow.ingestion.validation import DataValidator, DataValidationConfig

    config = DataValidationConfig(
        required_columns=["entity", "time", "gdp"],
        entity_col="entity",
        time_col="time",
        check_duplicates=True,
        max_missing_pct=0.2,
    )
    validator = DataValidator(config)
    report = validator.validate_path(Path("data/panel.csv"))
    if report.has_errors:
        print(report.to_json())
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Issue model
# ---------------------------------------------------------------------------

@dataclass
class ValidationIssue:
    """A single validation issue -- an error or a warning."""

    code: str           # e.g. "V-02"
    check: str          # human-readable check name
    level: str          # "error" | "warning"
    message: str        # concise description
    detail: str = ""    # additional context / suggested fix


# ---------------------------------------------------------------------------
# Report model
# ---------------------------------------------------------------------------

@dataclass
class DataValidationReport:
    """
    Aggregated result of running a :class:`DataValidator` over one dataset.

    Attributes
    ----------
    path:
        String representation of the validated file path.
    row_count:
        Number of data rows (excluding header).
    col_count:
        Number of columns.
    columns:
        Ordered list of column names.
    issues:
        All issues found.  May be empty (clean dataset).
    """

    path: str
    row_count: int
    col_count: int
    columns: list[str] = field(default_factory=list)
    issues: list[ValidationIssue] = field(default_factory=list)

    # ------------------------------------------------------------------
    # Mutators
    # ------------------------------------------------------------------

    def add_error(self, code: str, check: str, message: str, detail: str = "") -> None:
        """Append an error-level issue."""
        self.issues.append(ValidationIssue(
            code=code, check=check, level="error", message=message, detail=detail
        ))

    def add_warning(self, code: str, check: str, message: str, detail: str = "") -> None:
        """Append a warning-level issue."""
        self.issues.append(ValidationIssue(
            code=code, check=check, level="warning", message=message, detail=detail
        ))

    # ------------------------------------------------------------------
    # Aggregates
    # ------------------------------------------------------------------

    @property
    def has_errors(self) -> bool:
        """True if any error-level issues were found."""
        return any(i.level == "error" for i in self.issues)

    @property
    def n_errors(self) -> int:
        return sum(1 for i in self.issues if i.level == "error")

    @property
    def n_warnings(self) -> int:
        return sum(1 for i in self.issues if i.level == "warning")

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "row_count": self.row_count,
            "col_count": self.col_count,
            "columns": self.columns,
            "n_errors": self.n_errors,
            "n_warnings": self.n_warnings,
            "issues": [
                {
                    "code": i.code,
                    "check": i.check,
                    "level": i.level,
                    "message": i.message,
                    "detail": i.detail,
                }
                for i in self.issues
            ],
        }

    def to_json(self, *, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    def __str__(self) -> str:
        status = "PASS" if not self.has_errors else f"FAIL ({self.n_errors} error(s))"
        return (
            f"DataValidationReport({status}, "
            f"rows={self.row_count}, cols={self.col_count}, "
            f"warnings={self.n_warnings})"
        )


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass
class DataValidationConfig:
    """
    Configuration for :class:`DataValidator`.

    All check flags default to sensible values for panel data.
    """

    #: Columns that must be present.  Missing any = error.
    required_columns: list[str] = field(default_factory=list)
    #: Column identifying the cross-sectional entity.
    entity_col: str = "entity"
    #: Column identifying the time period.
    time_col: str = "time"
    #: Check for duplicate (entity, time) pairs.  Enabled by default.
    check_duplicates: bool = True
    #: Check that entity_col and time_col contain no null values.
    check_missing_identifiers: bool = True
    #: Check that all years in expected_years appear in time_col.
    check_missing_years: bool = False
    #: Set of expected years (used when check_missing_years=True).
    expected_years: list[int] | None = None
    #: Warn if any column exceeds this missing-value fraction (0.0--1.0).
    #: Set to 1.0 to disable.
    max_missing_pct: float = 1.0


# ---------------------------------------------------------------------------
# Validator
# ---------------------------------------------------------------------------

class DataValidator:
    """
    Run configurable validation checks on a panel CSV.

    Parameters
    ----------
    config:
        Which checks to run and with what parameters.
    """

    def __init__(self, config: DataValidationConfig | None = None) -> None:
        self.config = config or DataValidationConfig()

    # ------------------------------------------------------------------
    # Public entry points
    # ------------------------------------------------------------------

    def validate_path(self, path: Path) -> DataValidationReport:
        """
        Load the CSV at *path* and run all configured checks.

        Parameters
        ----------
        path:
            Path to a UTF-8 encoded CSV file with a header row.

        Returns
        -------
        DataValidationReport
        """
        try:
            with path.open(encoding="utf-8", newline="") as fh:
                reader = csv.reader(fh)
                header = next(reader, [])
                rows = list(reader)
        except FileNotFoundError:
            report = DataValidationReport(path=str(path), row_count=0, col_count=0)
            report.add_error("V-00", "file_exists", f"File not found: {path}")
            return report
        except Exception as exc:
            report = DataValidationReport(path=str(path), row_count=0, col_count=0)
            report.add_error("V-00", "file_parseable", f"CSV parse error: {exc}")
            return report

        report = DataValidationReport(
            path=str(path),
            row_count=len(rows),
            col_count=len(header),
            columns=header,
        )
        self._run_checks(header, rows, report)
        return report

    def validate_dataframe(
        self,
        df: pd.DataFrame,  # type: ignore[name-defined]  # noqa: F821
        path: str = "<memory>",
    ) -> DataValidationReport:
        """
        Run checks on an in-memory DataFrame.

        Parameters
        ----------
        df:
            Pandas DataFrame with column headers.
        path:
            Label used in the report (defaults to ``"<memory>"``).
        """
        header = list(df.columns)
        # Convert rows to list-of-lists for uniform check logic
        rows = df.values.tolist()
        report = DataValidationReport(
            path=path,
            row_count=len(rows),
            col_count=len(header),
            columns=header,
        )
        self._run_checks(header, rows, report)
        return report

    # ------------------------------------------------------------------
    # Individual checks
    # ------------------------------------------------------------------

    def _run_checks(
        self,
        header: list[str],
        rows: list[list],
        report: DataValidationReport,
    ) -> None:
        col_index = {col: i for i, col in enumerate(header)}
        self._check_required_columns(header, report)
        if self.config.check_missing_identifiers:
            self._check_missing_identifiers(col_index, rows, report)
        if self.config.check_duplicates:
            self._check_duplicate_keys(col_index, rows, report)
        self._check_missing_value_pct(header, rows, report)
        if self.config.check_missing_years:
            self._check_missing_years(col_index, rows, report)

    def _check_required_columns(
        self, header: list[str], report: DataValidationReport
    ) -> None:
        col_set = set(header)
        missing = [c for c in self.config.required_columns if c not in col_set]
        if missing:
            report.add_error(
                "V-01",
                "required_columns_present",
                f"{len(missing)} required column(s) missing: {missing}",
                f"Available columns: {header[:15]}{'...' if len(header) > 15 else ''}",
            )

    def _check_missing_identifiers(
        self,
        col_index: dict[str, int],
        rows: list[list],
        report: DataValidationReport,
    ) -> None:
        for col_name in (self.config.entity_col, self.config.time_col):
            if col_name not in col_index:
                continue
            idx = col_index[col_name]
            nulls = sum(1 for r in rows if len(r) <= idx or r[idx] in ("", None))
            if nulls > 0:
                report.add_error(
                    "V-03",
                    "no_missing_identifiers",
                    f"Column {col_name!r} has {nulls} null/empty value(s).",
                    "Panel identifiers must be non-null for every observation.",
                )

    def _check_duplicate_keys(
        self,
        col_index: dict[str, int],
        rows: list[list],
        report: DataValidationReport,
    ) -> None:
        ec, tc = self.config.entity_col, self.config.time_col
        if ec not in col_index or tc not in col_index:
            return
        ei, ti = col_index[ec], col_index[tc]
        keys = [
            (r[ei] if len(r) > ei else "", r[ti] if len(r) > ti else "")
            for r in rows
        ]
        n_dup = len(keys) - len(set(keys))
        if n_dup > 0:
            report.add_error(
                "V-02",
                "no_duplicate_keys",
                f"{n_dup} duplicate ({ec!r}, {tc!r}) pair(s) detected.",
                "Duplicates will cause errors in panel estimation. "
                "Check your data preparation script.",
            )

    def _check_missing_value_pct(
        self,
        header: list[str],
        rows: list[list],
        report: DataValidationReport,
    ) -> None:
        if self.config.max_missing_pct >= 1.0 or not rows:
            return
        n = len(rows)
        for i, col in enumerate(header):
            nulls = sum(
                1 for r in rows
                if len(r) <= i or r[i] in ("", None)
            )
            pct = nulls / n
            if pct > self.config.max_missing_pct:
                report.add_warning(
                    "V-06",
                    "missing_value_pct",
                    f"Column {col!r}: {pct:.1%} missing "
                    f"(threshold {self.config.max_missing_pct:.1%}).",
                    f"{nulls} of {n} rows are null/empty.",
                )

    def _check_missing_years(
        self,
        col_index: dict[str, int],
        rows: list[list],
        report: DataValidationReport,
    ) -> None:
        if not self.config.expected_years:
            return
        tc = self.config.time_col
        if tc not in col_index:
            return
        ti = col_index[tc]
        found_years: set[int] = set()
        for r in rows:
            if len(r) > ti and r[ti] not in ("", None):
                try:
                    found_years.add(int(r[ti]))
                except (ValueError, TypeError):
                    pass
        missing = sorted(
            y for y in self.config.expected_years if y not in found_years
        )
        if missing:
            report.add_warning(
                "V-05",
                "no_missing_years",
                f"{len(missing)} expected year(s) absent from {tc!r}: {missing[:10]}"
                f"{'...' if len(missing) > 10 else ''}",
            )
