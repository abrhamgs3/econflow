"""
econflow.estimation.backends.doubleml — Mixin for DoubleML-backed estimators.

**Status: Planned — Milestone 5.**

``DoubleML`` implements the double/debiased machine-learning framework of
Chernozhukov et al. (2018).  It supports partially linear regression (PLR),
interactive regression (IRM), partially linear IV regression (PLIV), and
interactive IV regression (IIVM).

``DoubleML`` estimators receive a :class:`doubleml.DoubleMLData` object rather
than a ``pd.DataFrame``, so the primary role of ``DoubleMLMixin`` will be
``_to_doubleml_data()`` — a conversion helper from EconFlow's
:class:`~econflow.datasets.panel.PanelDataset` to ``DoubleMLData``.
"""

from __future__ import annotations

from typing import ClassVar

from econflow.estimation.protocol import (
    BACKEND_DOUBLEML,
    BackendCapabilities,
)

__all__ = ["DoubleMLMixin"]


class DoubleMLMixin:
    """
    Mixin for estimators backed by the ``DoubleML`` library.

    **Planned — Milestone 5.**

    Attributes
    ----------
    backend : ClassVar[str]
        ``BACKEND_DOUBLEML``.

    Methods (all raise NotImplementedError until Milestone 5)
    ---------------------------------------------------------
    _to_doubleml_data(data, outcome, treatment, regressors) → DoubleMLData
        Convert a panel/cross-section DataFrame to ``DoubleMLData``.
    _check_doubleml() → str | None
        Return the installed version or ``None``.
    _backend_capabilities() → BackendCapabilities
        Return the ``DoubleML`` capability profile.
    """

    backend: ClassVar[str] = BACKEND_DOUBLEML

    def _to_doubleml_data(
        self,
        data: object,
        outcome: str,
        treatment: str,
        regressors: list[str],
    ) -> object:
        """
        Convert data to a ``DoubleMLData`` object.

        **Planned — Milestone 5.**

        Raises
        ------
        NotImplementedError
            Until Milestone 5 implementation lands.
        """
        raise NotImplementedError(
            "DoubleMLMixin._to_doubleml_data() is planned for Milestone 5."
        )

    def _check_doubleml(self) -> str | None:
        """Return the installed ``DoubleML`` version string, or ``None``."""
        try:
            import doubleml  # noqa: PLC0415
            return getattr(doubleml, "__version__", "unknown")
        except ImportError:
            return None

    def _backend_capabilities(self) -> BackendCapabilities:
        """Return the capability profile for the ``DoubleML`` backend."""
        return BackendCapabilities(
            backend=BACKEND_DOUBLEML,
            supports_panel=True,
            supports_cross_section=True,
            supports_time_series=False,
            supports_spatial=False,
            supports_bayesian=False,
            supports_iv=True,
            supports_quantile=False,
            supports_gmm=False,
        )
