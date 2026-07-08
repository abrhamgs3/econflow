"""
econflow.processing.quality — Data quality auditing and coverage reporting.

Produces structured quality reports that flag:

* Missing-value rates per indicator, country, and year.
* Implausible values (negative TFP levels, rates outside [0, 100], etc.).
* Temporal gaps (non-consecutive years within an entity).
* Cross-source inconsistencies where the same indicator appears in multiple
  sources with divergent values.

The :class:`QualityReporter` generates a :class:`QualityReport` object that
can be serialised to JSON or rendered as a Rich table in the CLI.

Usage (once implemented)
-------------------------
    from econflow.processing.quality import QualityReporter
    reporter = QualityReporter(panel)
    report = reporter.run()
    print(report.summary())
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd


@dataclass
class IndicatorQuality:
    """Quality metrics for a single panel data indicator column.

    Produced by :func:`compute_quality_report` and collected into a
    :class:`QualityReport`.  Used by ``econflow validate --data`` to surface
    data quality issues before the pipeline runs.

    Attributes
    ----------
    name : str
        Column name of the indicator in the panel DataFrame.
    n_obs : int
        Total number of rows (entity × time observations).
    n_missing : int
        Number of rows where this indicator is NaN.
    missing_pct : float
        ``n_missing / n_obs * 100``.
    n_countries : int
        Number of unique entity IDs with at least one non-missing value.
    n_years : int
        Number of unique time periods with at least one non-missing value.
    n_implausible : int
        Rows flagged as implausible by domain-specific range checks.
    flags : list[str]
        Human-readable warning strings (e.g. ``"high missingness"``).
    """

    name: str
    n_obs: int = 0
    n_missing: int = 0
    missing_pct: float = 0.0
    n_countries: int = 0
    n_years: int = 0
    n_implausible: int = 0
    flags: list[str] = field(default_factory=list)


@dataclass
class QualityReport:
    """
    Aggregated quality metrics for a full panel dataset.

    Attributes
    ----------
    indicators:
        Per-indicator quality breakdowns.
    overall_missing_pct:
        Fraction of missing cells across the entire panel.
    warnings:
        Human-readable warning strings emitted during the audit.
    """

    indicators: list[IndicatorQuality] = field(default_factory=list)
    overall_missing_pct: float = 0.0
    warnings: list[str] = field(default_factory=list)

    def summary(self) -> str:
        """Return a plain-text summary of the report."""
        raise NotImplementedError

    def to_dict(self) -> dict:
        """Serialise the report to a plain dictionary (JSON-serialisable)."""
        raise NotImplementedError


class QualityReporter:
    """
    Audits a wide-format panel DataFrame and produces a :class:`QualityReport`.

    Parameters
    ----------
    df:
        Wide-format panel with a ``(iso3, year)`` MultiIndex or columns.
    entity_col:
        Column name for the cross-sectional identifier.
    time_col:
        Column name for the time period.
    rules:
        Optional dict of ``{indicator: (min_val, max_val)}`` plausibility
        bounds.
    """

    def __init__(
        self,
        df: pd.DataFrame,
        entity_col: str = "iso3",
        time_col: str = "year",
        rules: dict[str, tuple[float, float]] | None = None,
    ) -> None:
        self.df = df
        self.entity_col = entity_col
        self.time_col = time_col
        self.rules = rules or {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self) -> QualityReport:
        """
        Execute all quality checks and return a :class:`QualityReport`.
        """
        raise NotImplementedError

    def missing_heatmap_data(self) -> pd.DataFrame:
        """
        Return a country × year matrix of missing-value fractions suitable
        for rendering as a heatmap.
        """
        raise NotImplementedError
