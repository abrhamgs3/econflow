"""
econflow.diagnostics.specification — Hausman specification test.

Tests the null hypothesis that the random-effects estimator is consistent
(i.e. the individual effects are uncorrelated with the regressors).  Rejection
favours the fixed-effects model.

The test statistic is:

    H = (β_FE − β_RE)′ [Var(β_FE) − Var(β_RE)]⁻¹ (β_FE − β_RE)

distributed asymptotically as χ²(k) under H₀, where k is the number of
time-varying regressors compared.

Usage (once implemented)
-------------------------
    from econflow.diagnostics.specification import hausman_test
    result = hausman_test(fe_result, re_result)
    print(result.statistic, result.pvalue)
"""

from __future__ import annotations

from dataclasses import dataclass

from econflow.estimation.base import EstimationResult


@dataclass
class HausmanResult:
    """
    Output of the Hausman specification test.

    Attributes
    ----------
    statistic:
        Chi-squared test statistic.
    df:
        Degrees of freedom (number of compared coefficients).
    pvalue:
        p-value under χ²(*df*) null distribution.
    verdict:
        ``"fixed_effects"`` if H₀ rejected at 5 %, ``"random_effects"``
        otherwise.
    """

    statistic: float
    df: int
    pvalue: float
    verdict: str


def hausman_test(
    fe_result: EstimationResult,
    re_result: EstimationResult,
    regressors: list[str] | None = None,
) -> HausmanResult:
    """
    Compute the Hausman test comparing *fe_result* and *re_result*.

    Parameters
    ----------
    fe_result:
        :class:`~econflow.estimation.base.EstimationResult` from
        :class:`~econflow.estimation.fixed_effects.TwoWayFE`.
    re_result:
        :class:`~econflow.estimation.base.EstimationResult` from
        :class:`~econflow.estimation.random_effects.RandomEffectsGLS`.
    regressors:
        Subset of regressors to include in the test.  ``None`` uses all
        common regressors.

    Returns
    -------
    HausmanResult
        Test statistic, degrees of freedom, p-value, and model verdict.

    Raises
    ------
    econflow.core.exceptions.DiagnosticsError
        If the coefficient covariance difference matrix is not positive
        semi-definite.
    """
    raise NotImplementedError
