"""
econflow.estimation.result — Standard estimation result objects.

Every estimator registered in the EconFlow estimation framework returns an
:class:`EstimationResult`.  Diagnostic plugins return a
:class:`DiagnosticResult`.  Both are immutable dataclasses with full JSON
serialization so they can be stored in provenance records.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any

import pandas as pd

# ---------------------------------------------------------------------------
# Diagnostic result (defined first to avoid forward reference in EstimationResult)
# ---------------------------------------------------------------------------

@dataclass
class DiagnosticResult:
    """
    Standardised output from a single diagnostic plugin.

    Attributes
    ----------
    diagnostic_id:
        Registry ID of the diagnostic (e.g. ``"hausman"``).
    diagnostic_name:
        Human-readable name.
    statistic:
        Test statistic value, or ``None`` if not applicable.
    pvalue:
        p-value of the test, or ``None`` if not computable.
    conclusion:
        One-sentence plain-English interpretation (e.g. "Reject H0: ...").
    level:
        Severity level: ``"info"``, ``"warning"``, or ``"error"``.
    estimator_id:
        Registry ID of the estimator that was diagnosed (e.g. ``"fe"``).
        Populated automatically by
        :meth:`~econflow.diagnostics.base.BaseDiagnostic.run_with_context`.
    extra:
        Diagnostic-specific supplementary data (degrees of freedom,
        bandwidth, etc.).
    """

    diagnostic_id: str
    diagnostic_name: str
    statistic: float | None = None
    pvalue: float | None = None
    conclusion: str = ""
    level: str = "info"
    estimator_id: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        # Convert NaN to None for JSON compatibility
        if d["statistic"] is not None and d["statistic"] != d["statistic"]:
            d["statistic"] = None
        if d["pvalue"] is not None and d["pvalue"] != d["pvalue"]:
            d["pvalue"] = None
        return d

    def to_json(self, *, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DiagnosticResult:
        return cls(
            diagnostic_id=data.get("diagnostic_id", ""),
            diagnostic_name=data.get("diagnostic_name", ""),
            statistic=data.get("statistic"),
            pvalue=data.get("pvalue"),
            conclusion=data.get("conclusion", ""),
            level=data.get("level", "info"),
            estimator_id=data.get("estimator_id", ""),
            extra=dict(data.get("extra", {})),
        )


# ---------------------------------------------------------------------------
# Estimation result
# ---------------------------------------------------------------------------

@dataclass
class EstimationResult:
    """
    Standardised container for panel econometric estimation output.

    Every registered estimator returns exactly this object, allowing
    the sensitivity runner, diagnostic suite, and output renderers to
    operate uniformly across model specifications.

    Attributes
    ----------
    estimator_id:
        Registry ID of the estimator (e.g. ``"twfe"``).
    estimator_name:
        Human-readable estimator name.
    params:
        Coefficient point estimates, indexed by variable name.
    std_err:
        Standard errors aligned with *params*.
    conf_int:
        95 % confidence intervals — two-column DataFrame with columns
        ``["lower", "upper"]``.
    pvalues:
        Two-sided p-values aligned with *params*.
    nobs:
        Effective number of observations used in estimation.
    ngroups:
        Number of unique entities (0 if not applicable).
    df_resid:
        Residual degrees of freedom.
    rsquared:
        R-squared or within-R-squared for FE models.
    rsquared_adj:
        Adjusted R-squared.
    f_statistic:
        Joint F-statistic, or ``None`` if not computed.
    f_pvalue:
        p-value of the F-test, or ``None``.
    entity_col:
        Column name used as the entity dimension.
    time_col:
        Column name used as the time dimension.
    entities:
        Sorted list of entity identifiers included in the sample.
    time_periods:
        Sorted list of time periods included in the sample.
    diagnostic_results:
        List of :class:`DiagnosticResult` objects attached after fitting.
    warnings:
        Human-readable warnings generated during estimation.
    provenance:
        Dict of provenance metadata (timestamp, git commit, params used, ...).
    extra:
        Estimator-specific supplementary statistics (J-stat, etc.).
    """

    # Identity
    estimator_id: str
    estimator_name: str

    # Coefficients
    params: pd.Series
    std_err: pd.Series
    conf_int: pd.DataFrame
    pvalues: pd.Series

    # Fit statistics
    nobs: int
    ngroups: int
    df_resid: int
    rsquared: float
    rsquared_adj: float
    f_statistic: float | None = None
    f_pvalue: float | None = None

    # Sample information
    entity_col: str = "entity"
    time_col: str = "time"
    entities: list[str] = field(default_factory=list)
    time_periods: list = field(default_factory=list)

    # Diagnostics, warnings, provenance
    diagnostic_results: list[DiagnosticResult] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    provenance: dict[str, Any] = field(default_factory=dict)
    extra: dict[str, Any] = field(default_factory=dict)

    # ------------------------------------------------------------------
    # Derived properties
    # ------------------------------------------------------------------

    @property
    def tvalues(self) -> pd.Series:
        """t-statistics: ``params / std_err``."""
        return self.params / self.std_err

    def summary_frame(self) -> pd.DataFrame:
        """
        Tidy DataFrame combining params, std_err, t-values, p-values,
        and 95 % confidence intervals.

        Returns
        -------
        pd.DataFrame
            Index = variable names. Columns: ``coef``, ``std_err``,
            ``t_stat``, ``pvalue``, ``ci_lower``, ``ci_upper``.
        """
        return pd.DataFrame(
            {
                "coef":     self.params,
                "std_err":  self.std_err,
                "t_stat":   self.tvalues,
                "pvalue":   self.pvalues,
                "ci_lower": self.conf_int["lower"],
                "ci_upper": self.conf_int["upper"],
            }
        )

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable dict (Series -> list, DataFrame -> list of dicts)."""
        return {
            "estimator_id":   self.estimator_id,
            "estimator_name": self.estimator_name,
            "params":         self.params.to_dict(),
            "std_err":        self.std_err.to_dict(),
            "conf_int":       self.conf_int.to_dict(),
            "pvalues":        self.pvalues.to_dict(),
            "nobs":           self.nobs,
            "ngroups":        self.ngroups,
            "df_resid":       self.df_resid,
            "rsquared":       self.rsquared,
            "rsquared_adj":   self.rsquared_adj,
            "f_statistic":    self.f_statistic,
            "f_pvalue":       self.f_pvalue,
            "entity_col":     self.entity_col,
            "time_col":       self.time_col,
            "entities":       self.entities,
            "time_periods":   [str(t) for t in self.time_periods],
            "diagnostic_results": [d.to_dict() for d in self.diagnostic_results],
            "warnings":       self.warnings,
            "provenance":     self.provenance,
            "extra":          self.extra,
        }

    def to_json(self, *, indent: int = 2) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False,
                          default=str)

    def __str__(self) -> str:
        return (
            f"EstimationResult({self.estimator_name!r}, "
            f"nobs={self.nobs}, R2={self.rsquared:.4f}, "
            f"vars={list(self.params.index)})"
        )
