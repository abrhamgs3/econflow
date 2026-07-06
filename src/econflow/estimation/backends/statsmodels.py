"""
econflow.estimation.backends.statsmodels — Mixin for statsmodels-backed estimators.

**Status: Planned — Milestone 4.**

``statsmodels`` supports OLS, GLS, WLS, panel regression via
``statsmodels.formula.api``, quantile regression (QuantReg), and a wide
range of time-series models (ARMA, VAR, state-space, etc.).

When Milestone 4 lands, concrete estimators backed by ``statsmodels`` will
inherit from ``StatsmodelsMixin`` alongside
:class:`~econflow.estimation.base.BaseEstimator`.

Current state
-------------
The mixin is a stub — it declares the ``backend`` class attribute and the
capability profile so that protocol conformance tests can reference it, but
none of the helper methods have a concrete implementation yet.
"""

from __future__ import annotations

from typing import ClassVar

from econflow.estimation.protocol import (
    BACKEND_STATSMODELS,
    BackendCapabilities,
)

__all__ = ["StatsmodelsMixin"]


class StatsmodelsMixin:
    """
    Mixin for estimators backed by the ``statsmodels`` library.

    **Planned — Milestone 4.**

    Attributes
    ----------
    backend : ClassVar[str]
        ``BACKEND_STATSMODELS``.

    Methods (all raise NotImplementedError until Milestone 4)
    ---------------------------------------------------------
    _to_formula(dependent, regressors, intercept) → str
        Build a patsy formula string accepted by ``statsmodels.formula.api``.
    _check_statsmodels() → str | None
        Return the installed version or ``None``.
    _backend_capabilities() → BackendCapabilities
        Return the ``statsmodels`` capability profile.
    """

    backend: ClassVar[str] = BACKEND_STATSMODELS

    def _to_formula(
        self,
        dependent: str,
        regressors: list[str],
        intercept: bool = True,
    ) -> str:
        """
        Build a patsy-style formula for ``statsmodels.formula.api``.

        **Planned — Milestone 4.**

        Parameters
        ----------
        dependent:
            Dependent variable column name.
        regressors:
            List of regressor column names.
        intercept:
            Include an intercept term (``+ 1``) if ``True``.

        Raises
        ------
        NotImplementedError
            Until Milestone 4 implementation lands.
        """
        raise NotImplementedError(
            "StatsmodelsMixin._to_formula() is planned for Milestone 4. "
            "Use LinearmodelsMixin for panel estimators in the meantime."
        )

    def _check_statsmodels(self) -> str | None:
        """Return the installed ``statsmodels`` version string, or ``None``."""
        try:
            import statsmodels  # noqa: PLC0415
            return getattr(statsmodels, "__version__", "unknown")
        except ImportError:
            return None

    def _backend_capabilities(self) -> BackendCapabilities:
        """Return the capability profile for the ``statsmodels`` backend."""
        return BackendCapabilities(
            backend=BACKEND_STATSMODELS,
            supports_panel=False,
            supports_cross_section=True,
            supports_time_series=True,
            supports_spatial=False,
            supports_bayesian=False,
            supports_iv=False,
            supports_quantile=True,
            supports_gmm=False,
        )
