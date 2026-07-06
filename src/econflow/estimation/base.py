"""
econflow.estimation.base — Abstract estimator interface.

All EconFlow estimators inherit from :class:`BaseEstimator` and return an
:class:`EstimationResult`.  This contract allows the sensitivity runner,
diagnostic suite, and output renderers to operate uniformly across model
specifications.

The class-level attributes provide self-documenting metadata that is surfaced
by ``econflow info`` and can be validated by the config system before any data
is loaded.

Backward compatibility
-----------------------
``EstimationResult`` is still importable from this module — all existing
``from econflow.estimation.base import EstimationResult`` statements continue
to work without modification.
"""

from __future__ import annotations

import abc
from datetime import datetime, timezone
from typing import Any

import pandas as pd

# Re-export for backward compat (diagnostics/*, outputs/*, sensitivity/* all
# import EstimationResult from here).
from econflow.estimation.result import DiagnosticResult, EstimationResult

__all__ = ["BaseEstimator", "EstimationResult", "DiagnosticResult", "EstimatorError"]


# ---------------------------------------------------------------------------
# Estimator-level exception
# ---------------------------------------------------------------------------

class EstimatorError(Exception):
    """
    Raised when an estimator cannot complete its work.

    Parameters
    ----------
    message:
        Human-readable description of the failure.
    estimator_id:
        Registry ID of the failing estimator.
    cause:
        Original exception, if any.
    """

    def __init__(
        self,
        message: str,
        *,
        estimator_id: str = "",
        cause: Exception | None = None,
    ) -> None:
        super().__init__(message)
        self.estimator_id = estimator_id
        self.cause = cause

    def __str__(self) -> str:
        base = super().__str__()
        if self.estimator_id:
            base = f"[{self.estimator_id}] {base}"
        if self.cause:
            base = f"{base}\nCaused by: {self.cause!r}"
        return base


# ---------------------------------------------------------------------------
# Abstract base estimator
# ---------------------------------------------------------------------------

class BaseEstimator(abc.ABC):
    """
    Abstract base for all EconFlow panel estimators.

    Subclasses must:

    1. Set class-level metadata attributes (``name``, ``description``, …).
    2. Implement :meth:`validate`, :meth:`fit`, and :meth:`diagnostics`.
    3. Decorate the class with ``@register(estimator_id)``.

    The concrete :meth:`run` method chains ``validate → fit → diagnostics``
    and returns the enriched :class:`EstimationResult`.

    Class attributes
    ----------------
    estimator_id:
        Short registry key set by ``@register()`` (e.g. ``"twfe"``).
    name:
        Human-readable name.
    description:
        One-paragraph description of the estimator.
    supported_data:
        Data formats the estimator accepts (e.g. ``["balanced_panel",
        "unbalanced_panel"]``).
    required_parameters:
        Parameter names that *must* be present in the ``params`` dict
        passed to the constructor.
    optional_parameters:
        Parameter names that *may* be present with their default values.
    """

    # Subclasses should override these
    estimator_id: str = "base"
    name: str = "BaseEstimator"
    description: str = ""
    supported_data: list[str] = ["panel"]
    required_parameters: list[str] = ["dependent", "regressors"]
    optional_parameters: dict[str, Any] = {}

    def __init__(self, params: dict[str, Any] | None = None) -> None:
        """
        Parameters
        ----------
        params:
            Configuration dict.  At minimum must contain the keys listed in
            :attr:`required_parameters`.  Validated by :meth:`validate`.
        """
        self.params: dict[str, Any] = dict(params or {})

    # ------------------------------------------------------------------
    # Abstract interface — subclasses must implement these
    # ------------------------------------------------------------------

    @abc.abstractmethod
    def validate(self, data: pd.DataFrame) -> None:
        """
        Validate *data* and ``self.params`` before estimation.

        Should raise :class:`EstimatorError` with a descriptive message if
        validation fails.  Does not return a value.

        Parameters
        ----------
        data:
            Wide-format panel DataFrame.
        """

    @abc.abstractmethod
    def fit(self, data: pd.DataFrame) -> EstimationResult:
        """
        Estimate the model and return a populated :class:`EstimationResult`.

        Parameters
        ----------
        data:
            Wide-format panel DataFrame containing all referenced columns.
        """

    @abc.abstractmethod
    def diagnostics(self, result: EstimationResult) -> list[DiagnosticResult]:
        """
        Compute post-estimation diagnostics.

        Returns a list of :class:`DiagnosticResult` objects to be attached
        to the result.  Return an empty list if no diagnostics are applicable
        or if the estimator is a stub.

        Parameters
        ----------
        result:
            The :class:`EstimationResult` returned by :meth:`fit`.
        """

    # ------------------------------------------------------------------
    # Optional interface — subclasses may override
    # ------------------------------------------------------------------

    def predict(
        self,
        result: EstimationResult,
        newdata: pd.DataFrame | None = None,
    ) -> pd.Series:
        """
        Generate predictions from a fitted result.

        Default implementation applies the estimated coefficients to
        *newdata* (or the original sample if *newdata* is ``None``).
        Subclasses should override for more specialised prediction logic.

        Parameters
        ----------
        result:
            A fitted :class:`EstimationResult`.
        newdata:
            DataFrame to predict on.  Must contain all regressor columns.
        """
        raise NotImplementedError(
            f"{self.__class__.__name__}.predict() is not implemented. "
            "Override this method to provide prediction logic."
        )

    # ------------------------------------------------------------------
    # Concrete convenience wrapper
    # ------------------------------------------------------------------

    def run(self, data: pd.DataFrame) -> EstimationResult:
        """
        Full estimation pipeline: ``validate → fit → diagnostics``.

        Equivalent to::

            estimator.validate(data)
            result = estimator.fit(data)
            result.diagnostic_results = estimator.diagnostics(result)
            return result

        Parameters
        ----------
        data:
            Wide-format panel DataFrame.

        Returns
        -------
        EstimationResult
            Fully populated result with diagnostic results attached.
        """
        self.validate(data)
        result = self.fit(data)
        result.diagnostic_results = self.diagnostics(result)
        return result

    # ------------------------------------------------------------------
    # Shared helpers available to all subclasses
    # ------------------------------------------------------------------

    def _require_params(self, *keys: str) -> None:
        """
        Assert that all *keys* are present and non-empty in ``self.params``.

        Raises
        ------
        EstimatorError
            With a list of missing keys.
        """
        missing = [k for k in keys if not self.params.get(k)]
        if missing:
            raise EstimatorError(
                f"Missing required parameters: {missing}",
                estimator_id=self.estimator_id,
            )

    def _require_columns(self, data: pd.DataFrame, *cols: str) -> None:
        """
        Assert that all *cols* are present in *data*.

        Raises
        ------
        EstimatorError
            With the list of missing column names.
        """
        missing = [c for c in cols if c not in data.columns]
        if missing:
            raise EstimatorError(
                f"Missing columns in data: {missing}",
                estimator_id=self.estimator_id,
            )

    def _to_panel(
        self,
        data: pd.DataFrame,
        entity_col: str,
        time_col: str,
    ) -> pd.DataFrame:
        """
        Set a (entity, time) MultiIndex required by linearmodels.

        Returns a copy of *data* with the MultiIndex set and columns
        sorted for determinism.
        """
        return data.set_index([entity_col, time_col]).sort_index()

    def _resolve_dataframe(
        self,
        data: "pd.DataFrame | Any",
    ) -> "pd.DataFrame":
        """
        Coerce *data* to a plain ``pd.DataFrame``.

        If *data* is a :class:`~econflow.datasets.panel.PanelDataset` the flat
        (non-MultiIndex) representation is returned via ``to_dataframe()``.
        If *data* is any other :class:`~econflow.datasets.base.Dataset`, the
        ``dataframe`` property is used.  Plain ``pd.DataFrame`` objects are
        returned as-is.

        This is the only Dataset-to-DataFrame conversion point in the
        estimation layer; P0 safety is preserved because ``to_dataframe()``
        produces a byte-for-byte copy of the flat frame the ``PanelDataset``
        was built from.
        """
        try:
            from econflow.datasets.panel import PanelDataset as _PDS  # noqa
            from econflow.datasets.base import Dataset as _DS          # noqa
        except ImportError:
            return data  # datasets package not installed — pass through
        if isinstance(data, _PDS):
            return data.to_dataframe()
        if isinstance(data, _DS):
            return data.dataframe
        return data


    def _provenance_stamp(self) -> dict[str, Any]:
        """Return a provenance dict with current UTC timestamp, version, and params."""
        from econflow import __version__
        return {
            "estimator_id":    self.estimator_id,
            "econflow_version": __version__,
            "timestamp_utc":   datetime.now(tz=timezone.utc).isoformat(),
            "params": {k: v for k, v in self.params.items()
                       if isinstance(v, (str, int, float, bool, list, type(None)))},
        }

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} params={self.params!r}>"
