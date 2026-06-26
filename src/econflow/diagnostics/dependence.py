"""
econflow.diagnostics.dependence — Pesaran cross-sectional dependence test.

Tests for cross-sectional dependence (CSD) in panel data residuals using
the Pesaran (2004) CD statistic:

    CD = sqrt(2T / (N(N-1))) · Σ_{i<j} ρ̂_{ij}  ~ N(0, 1) under H₀

where ρ̂_{ij} is the sample correlation of residuals between entities *i*
and *j*.  CSD is common in macro panels with global shocks and, if ignored,
leads to severely under-sized tests.

Usage (once implemented)
-------------------------
    from econflow.diagnostics.dependence import pesaran_cd_test
    result = pesaran_cd_test(fe_result, panel)
    print(result.statistic, result.pvalue)
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from econflow.estimation.base import EstimationResult


@dataclass
class CDTestResult:
    """
    Output of the Pesaran cross-sectional dependence test.

    Attributes
    ----------
    statistic:
        CD test statistic (standard normal under H₀).
    pvalue:
        Two-sided p-value.
    avg_abs_corr:
        Average absolute pair-wise residual correlation (ρ̄).
    conclusion:
        ``"no_csd"`` if H₀ not rejected at 5 %,
        ``"csd_present"`` otherwise.
    """

    statistic: float
    pvalue: float
    avg_abs_corr: float
    conclusion: str


def pesaran_cd_test(
    result: EstimationResult,
    df: pd.DataFrame,
    entity_col: str = "iso3",
    time_col: str = "year",
) -> CDTestResult:
    """
    Compute the Pesaran CD statistic from panel residuals.

    Parameters
    ----------
    result:
        An :class:`~econflow.estimation.base.EstimationResult`; residuals are
        recovered from the ``extra["residuals"]`` key if present, or
        recomputed from *df*.
    df:
        The panel DataFrame used for estimation.
    entity_col / time_col:
        Panel dimension identifiers.

    Returns
    -------
    CDTestResult
        CD statistic, p-value, average absolute correlation, and conclusion.
    """
    raise NotImplementedError
