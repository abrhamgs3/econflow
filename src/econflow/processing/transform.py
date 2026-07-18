"""
econflow.processing.transform — Variable transformations.

Provides a functional API and a composable :class:`TransformPipeline` for
common panel-data transformations:

* Log transformation (natural and base-10)
* First differences and *n*-th order differences
* Lag and lead operators (within-group, respecting panel structure)
* Annualised growth rates
* Z-score normalisation (within cross-section or within time)
* Winsorisation at user-specified percentile bounds

Usage (once implemented)
-------------------------
    from econflow.processing.transform import TransformPipeline
    tp = TransformPipeline([
        ("log",    {"columns": ["gdp", "tfp"]}),
        ("lag",    {"columns": ["log_gdp"], "periods": 1}),
        ("growth", {"columns": ["log_gdp"], "periods": 1}),
    ])
    panel = tp.fit_transform(panel, entity_col="iso3", time_col="year")
"""

from __future__ import annotations

from typing import Any

import pandas as pd


class TransformPipeline:
    """
    Composable pipeline of named transformations applied sequentially to a
    panel DataFrame.

    Parameters
    ----------
    steps:
        Ordered list of ``(name, kwargs)`` tuples.  *name* must correspond to
        a registered transform (e.g. ``"log"``, ``"lag"``, ``"growth"``).
    """

    _REGISTRY: dict[str, Any] = {}

    def __init__(self, steps: list[tuple[str, dict[str, Any]]]) -> None:
        self.steps = steps

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def fit_transform(
        self,
        df: pd.DataFrame,
        entity_col: str = "iso3",
        time_col: str = "year",
    ) -> pd.DataFrame:
        """
        Apply all steps sequentially to *df* and return the transformed frame.

        Parameters
        ----------
        df:
            Wide-format panel with entity and time columns.
        entity_col:
            Column name identifying the cross-sectional unit.
        time_col:
            Column name identifying the time period.
        """
        raise NotImplementedError

    # ------------------------------------------------------------------
    # Individual transformations (staticmethods, also callable standalone)
    # ------------------------------------------------------------------

    @staticmethod
    def log(df: pd.DataFrame, columns: list[str], base: float = 2.718281828) -> pd.DataFrame:
        """Apply log transformation to *columns*; adds ``log_`` prefix."""
        raise NotImplementedError

    @staticmethod
    def lag(
        df: pd.DataFrame,
        columns: list[str],
        periods: int = 1,
        entity_col: str = "iso3",
        time_col: str = "year",
    ) -> pd.DataFrame:
        """Add lagged values of *columns* within each entity group."""
        raise NotImplementedError

    @staticmethod
    def growth(
        df: pd.DataFrame,
        columns: list[str],
        periods: int = 1,
        entity_col: str = "iso3",
        time_col: str = "year",
    ) -> pd.DataFrame:
        """Compute annualised growth rates as period-on-period log differences."""
        raise NotImplementedError

    @staticmethod
    def winsorise(
        df: pd.DataFrame,
        columns: list[str],
        lower: float = 0.01,
        upper: float = 0.99,
    ) -> pd.DataFrame:
        """Clip *columns* at the specified quantile bounds."""
        raise NotImplementedError
