"""
econflow.diagnostics.overid — Sargan-Hansen J-test for over-identifying restrictions.

Tests whether the instruments used in IV / GMM estimation are valid (i.e.
uncorrelated with the error term in the structural equation).  Only applicable
when the model is over-identified (more instruments than endogenous regressors).

The J-statistic is:

    J = n · g(θ̂)′ Ŵ g(θ̂)  ~ χ²(q − k) under H₀

where *g(θ̂)* is the sample moment vector, *Ŵ* is the optimal weighting
matrix, *q* is the number of instruments, and *k* is the number of
endogenous regressors.

Usage (once implemented)
-------------------------
    from econflow.diagnostics.overid import sargan_hansen_test
    result = sargan_hansen_test(iv_result)
    print(result.statistic, result.pvalue, result.df)
"""

from __future__ import annotations

from dataclasses import dataclass

from econflow.estimation.base import EstimationResult


@dataclass
class OverIDResult:
    """
    Output of the Sargan-Hansen J-test.

    Attributes
    ----------
    statistic:
        J-statistic value.
    df:
        Degrees of freedom (``n_instruments − n_endog``).
    pvalue:
        p-value under χ²(*df*) null distribution.
    conclusion:
        ``"instruments_valid"`` if H₀ not rejected at 5 %,
        ``"instruments_suspect"`` otherwise.
    """

    statistic: float
    df: int
    pvalue: float
    conclusion: str


def sargan_hansen_test(result: EstimationResult) -> OverIDResult:
    """
    Compute the Sargan-Hansen J-test from an IV/GMM estimation result.

    Parameters
    ----------
    result:
        :class:`~econflow.estimation.base.EstimationResult` from
        :class:`~econflow.estimation.iv.IVEstimator` or
        :class:`~econflow.estimation.gmm.GMMEstimator`.

    Returns
    -------
    OverIDResult
        Test statistic, df, p-value, and conclusions string.

    Raises
    ------
    econflow.core.exceptions.DiagnosticsError
        If the model is exactly identified (df = 0) — the test is not
        computable.
    """
    raise NotImplementedError
