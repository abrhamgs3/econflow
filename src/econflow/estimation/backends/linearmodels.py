"""
econflow.estimation.backends.linearmodels — Mixin for linearmodels-backed estimators.

All six implemented EconFlow estimators currently use ``linearmodels``:
PooledOLS, EntityFE, TwoWayFE, RandomEffects, FirstDifference, IV2SLS.

``LinearmodelsMixin`` collects the data-preparation helpers that are specific
to ``linearmodels``'s API so they can be reused without crowding
:class:`~econflow.estimation.base.BaseEstimator` with library-specific code.

Usage
-----
::

    from econflow.estimation.base import BaseEstimator
    from econflow.estimation.backends.linearmodels import LinearmodelsMixin
    from econflow.estimation.protocol import BACKEND_LINEARMODELS

    class MyPanelEstimator(BaseEstimator, LinearmodelsMixin):
        backend = BACKEND_LINEARMODELS

        def fit(self, data):
            data = self._resolve_dataframe(data)
            panel = self._to_panel(data.dropna(...), entity_col, time_col)
            ...
"""

from __future__ import annotations

from typing import ClassVar

import pandas as pd

from econflow.estimation.protocol import (
    BACKEND_LINEARMODELS,
    BackendCapabilities,
)

__all__ = ["LinearmodelsMixin"]


class LinearmodelsMixin:
    """
    Mixin for estimators backed by the ``linearmodels`` library.

    Provides
    --------
    backend : ClassVar[str]
        Set to ``BACKEND_LINEARMODELS``.  Concrete subclasses may keep this
        value or override it with a more specific string.
    _to_panel(data, entity_col, time_col) → pd.DataFrame
        Set a ``(entity_col, time_col)`` ``MultiIndex`` required by all
        ``linearmodels`` panel estimators.  Equivalent to the historical
        ``BaseEstimator._to_panel()`` helper.
    _check_linearmodels() → str | None
        Return the installed ``linearmodels`` version or ``None`` if not
        installed.
    _backend_capabilities() → BackendCapabilities
        Return the capability profile for ``linearmodels``.
    """

    backend: ClassVar[str] = BACKEND_LINEARMODELS

    # ------------------------------------------------------------------
    # Data preparation
    # ------------------------------------------------------------------

    def _to_panel(
        self,
        data: pd.DataFrame,
        entity_col: str,
        time_col: str,
    ) -> pd.DataFrame:
        """
        Set a ``(entity_col, time_col)`` MultiIndex for ``linearmodels``.

        ``linearmodels`` panel estimators (``PooledOLS``, ``PanelOLS``,
        ``RandomEffects``, ``FirstDifferenceOLS``, ``IV2SLS``) require the
        input DataFrame to have a ``(entity, time)`` two-level ``MultiIndex``.
        This method creates that index from flat DataFrame columns and sorts it
        for deterministic ordering.

        Parameters
        ----------
        data:
            Flat wide-format panel DataFrame with *entity_col* and *time_col*
            as ordinary columns (not as index levels).
        entity_col:
            Name of the cross-sectional identifier column.
        time_col:
            Name of the time-period identifier column.

        Returns
        -------
        pd.DataFrame
            Copy of *data* with a sorted ``(entity_col, time_col)``
            ``MultiIndex``.
        """
        return data.set_index([entity_col, time_col]).sort_index()

    # ------------------------------------------------------------------
    # Backend introspection
    # ------------------------------------------------------------------

    def _check_linearmodels(self) -> str | None:
        """
        Return the installed ``linearmodels`` version string, or ``None``.

        Used by validation logic to provide a helpful error message when the
        library is not available.
        """
        try:
            import linearmodels  # noqa: PLC0415
            return getattr(linearmodels, "__version__", "unknown")
        except ImportError:
            return None

    def _backend_capabilities(self) -> BackendCapabilities:
        """
        Return the capability profile for the ``linearmodels`` backend.

        ``linearmodels`` supports panel data, IV/2SLS, and GMM.  It does not
        natively support Bayesian estimation, spatial models, or quantile
        regression.
        """
        return BackendCapabilities(
            backend=BACKEND_LINEARMODELS,
            supports_panel=True,
            supports_cross_section=False,
            supports_time_series=False,
            supports_spatial=False,
            supports_bayesian=False,
            supports_iv=True,
            supports_quantile=False,
            supports_gmm=True,
        )
