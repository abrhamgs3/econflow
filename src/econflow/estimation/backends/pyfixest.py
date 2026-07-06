"""
econflow.estimation.backends.pyfixest — Mixin for pyfixest-backed estimators.

**Status: Planned — Milestone 4.**

``pyfixest`` provides fast Stata-like fixed-effects regression in Python with
a clean ``feols()`` / ``fepois()`` API.  It handles high-dimensional FE via
the Frisch-Waugh-Lovell (FWL) theorem and supports cluster-robust SEs,
bootstrapped SEs, and difference-in-differences estimands.
"""

from __future__ import annotations

from typing import ClassVar

from econflow.estimation.protocol import (
    BACKEND_PYFIXEST,
    BackendCapabilities,
)

__all__ = ["PyfixestMixin"]


class PyfixestMixin:
    """
    Mixin for estimators backed by the ``pyfixest`` library.

    **Planned — Milestone 4.**

    Attributes
    ----------
    backend : ClassVar[str]
        ``BACKEND_PYFIXEST``.

    Methods (all raise NotImplementedError until Milestone 4)
    ---------------------------------------------------------
    _to_fixest_formula(dependent, regressors, fe_vars) → str
        Build a ``pyfixest``-style formula with fixed-effects ``| fe_var1 + fe_var2``.
    _check_pyfixest() → str | None
        Return the installed version or ``None``.
    _backend_capabilities() → BackendCapabilities
        Return the ``pyfixest`` capability profile.
    """

    backend: ClassVar[str] = BACKEND_PYFIXEST

    def _to_fixest_formula(
        self,
        dependent: str,
        regressors: list[str],
        fe_vars: list[str] | None = None,
    ) -> str:
        """
        Build a ``pyfixest``-style formula string.

        **Planned — Milestone 4.**

        Raises
        ------
        NotImplementedError
            Until Milestone 4 implementation lands.
        """
        raise NotImplementedError(
            "PyfixestMixin._to_fixest_formula() is planned for Milestone 4."
        )

    def _check_pyfixest(self) -> str | None:
        """Return the installed ``pyfixest`` version string, or ``None``."""
        try:
            import pyfixest  # noqa: PLC0415
            return getattr(pyfixest, "__version__", "unknown")
        except ImportError:
            return None

    def _backend_capabilities(self) -> BackendCapabilities:
        """Return the capability profile for the ``pyfixest`` backend."""
        return BackendCapabilities(
            backend=BACKEND_PYFIXEST,
            supports_panel=True,
            supports_cross_section=True,
            supports_time_series=False,
            supports_spatial=False,
            supports_bayesian=False,
            supports_iv=True,
            supports_quantile=False,
            supports_gmm=False,
        )
