"""
econflow.estimation.backends.pymc — Mixin for PyMC-backed estimators.

**Status: Planned — Milestone 6.**

``PyMC`` implements Bayesian probabilistic programming using MCMC (NUTS
sampler) and variational inference (ADVI).  Estimators backed by ``PyMC``
return posterior distributions embedded in the
:class:`~econflow.estimation.result.EstimationResult` rather than point
estimates and standard errors.

The primary helpers needed are ``_build_model()`` (constructs a
``pm.Model`` context) and ``_extract_posterior_summary()`` (converts an
``arviz.InferenceData`` object to the standard ``EstimationResult`` format).
"""

from __future__ import annotations

from typing import ClassVar

from econflow.estimation.protocol import (
    BACKEND_PYMC,
    BackendCapabilities,
)

__all__ = ["PyMCMixin"]


class PyMCMixin:
    """
    Mixin for Bayesian estimators backed by the ``PyMC`` library.

    **Planned — Milestone 6.**

    Attributes
    ----------
    backend : ClassVar[str]
        ``BACKEND_PYMC``.

    Methods (all raise NotImplementedError until Milestone 6)
    ---------------------------------------------------------
    _build_pymc_model(data, dependent, regressors) → pm.Model
        Construct a ``pm.Model`` from the input data.
    _extract_posterior_summary(trace) → dict
        Summarise an ArviZ ``InferenceData`` into the ``EstimationResult`` format.
    _check_pymc() → str | None
        Return the installed version or ``None``.
    _backend_capabilities() → BackendCapabilities
        Return the ``PyMC`` capability profile.
    """

    backend: ClassVar[str] = BACKEND_PYMC

    def _build_pymc_model(
        self,
        data: object,
        dependent: str,
        regressors: list[str],
    ) -> object:
        """
        Construct a ``pm.Model`` from the input data.

        **Planned — Milestone 6.**

        Raises
        ------
        NotImplementedError
            Until Milestone 6 implementation lands.
        """
        raise NotImplementedError(
            "PyMCMixin._build_pymc_model() is planned for Milestone 6."
        )

    def _extract_posterior_summary(self, trace: object) -> dict:
        """
        Summarise an ArviZ ``InferenceData`` object.

        **Planned — Milestone 6.**

        Raises
        ------
        NotImplementedError
            Until Milestone 6 implementation lands.
        """
        raise NotImplementedError(
            "PyMCMixin._extract_posterior_summary() is planned for Milestone 6."
        )

    def _check_pymc(self) -> str | None:
        """Return the installed ``PyMC`` version string, or ``None``."""
        try:
            import pymc  # noqa: PLC0415
            return getattr(pymc, "__version__", "unknown")
        except ImportError:
            return None

    def _backend_capabilities(self) -> BackendCapabilities:
        """Return the capability profile for the ``PyMC`` backend."""
        return BackendCapabilities(
            backend=BACKEND_PYMC,
            supports_panel=True,
            supports_cross_section=True,
            supports_time_series=True,
            supports_spatial=True,
            supports_bayesian=True,
            supports_iv=False,
            supports_quantile=False,
            supports_gmm=False,
        )
