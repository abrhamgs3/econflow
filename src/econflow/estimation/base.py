"""
econflow.estimation.base — Abstract estimator interface.

All APRP estimators subclass :class:`BaseEstimator` and return a
:class:`EstimationResult` dataclass.  This contract allows the sensitivity
runner, diagnostic suite, and output renderers to operate uniformly across
model specifications.

Result contract
---------------
Every :class:`EstimationResult` must expose:
* ``params``   — coefficient point estimates (``pd.Series``).
* ``std_err``  — standard errors (``pd.Series``).
* ``pvalues``  — two-sided p-values (``pd.Series``).
* ``nobs``     — number of observations used.
* ``rsquared`` — R-squared or pseudo-R-squared.
* ``extra``    — dict of estimator-specific statistics (F-stat, J-stat, etc.).
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import Any

import pandas as pd


@dataclass
class EstimationResult:
    """
    Standardised container for econometric estimation output.

    Attributes
    ----------
    estimator_name:
        String identifier for the estimator class.
    params:
        Coefficient point estimates indexed by variable name.
    std_err:
        Standard errors aligned with *params*.
    pvalues:
        Two-sided p-values aligned with *params*.
    conf_int:
        95 % confidence intervals as a two-column DataFrame.
    nobs:
        Effective sample size.
    rsquared:
        R-squared or within-R-squared (FE models).
    extra:
        Estimator-specific supplementary statistics.
    """

    estimator_name: str
    params: pd.Series
    std_err: pd.Series
    pvalues: pd.Series
    conf_int: pd.DataFrame
    nobs: int
    rsquared: float
    extra: dict[str, Any] = field(default_factory=dict)

    # ------------------------------------------------------------------
    # Derived statistics
    # ------------------------------------------------------------------

    @property
    def tvalues(self) -> pd.Series:
        """t-statistics computed as ``params / std_err``."""
        return self.params / self.std_err

    def summary_frame(self) -> pd.DataFrame:
        """
        Return a tidy DataFrame combining params, std_err, t-values,
        p-values, and confidence intervals.
        """
        raise NotImplementedError


class BaseEstimator(abc.ABC):
    """
    Abstract base for all APRP panel estimators.

    Parameters
    ----------
    dependent:
        Column name of the dependent variable.
    regressors:
        Column names of the explanatory variables (excluding constant).
    entity_col:
        Column name for the cross-sectional identifier.
    time_col:
        Column name for the time period.
    cluster:
        Column name on which to cluster standard errors, or ``None``.
    """

    estimator_name: str = "base"

    def __init__(
        self,
        dependent: str,
        regressors: list[str],
        entity_col: str = "iso3",
        time_col: str = "year",
        cluster: str | None = None,
    ) -> None:
        self.dependent = dependent
        self.regressors = regressors
        self.entity_col = entity_col
        self.time_col = time_col
        self.cluster = cluster

    # ------------------------------------------------------------------
    # Abstract interface
    # ------------------------------------------------------------------

    @abc.abstractmethod
    def fit(self, df: pd.DataFrame) -> EstimationResult:
        """
        Fit the model on *df* and return an :class:`EstimationResult`.

        Parameters
        ----------
        df:
            Wide-format panel DataFrame containing all referenced columns.
        """

    # ------------------------------------------------------------------
    # Concrete helpers
    # ------------------------------------------------------------------

    def _validate_columns(self, df: pd.DataFrame) -> None:
        """
        Assert that all required columns are present in *df*.

        Raises
        ------
        econflow.core.exceptions.EstimationError
            If any column is missing.
        """
        raise NotImplementedError

    def __repr__(self) -> str:
        return (
            f"<{self.__class__.__name__} "
            f"dep='{self.dependent}' regressors={self.regressors}>"
        )
