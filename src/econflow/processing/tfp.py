"""
econflow.processing.tfp — Total Factor Productivity computation.

Provides utilities for deriving TFP measures and growth-decomposition
components from PWT data and user-supplied production-function parameters.

Approaches supported (once implemented)
-----------------------------------------
* **Direct PWT** — use ``rtfpna`` / ``ctfp`` columns directly.
* **Growth accounting** — Solow residual via ``Δln(Y) - α·Δln(K) - (1-α)·Δln(L)``.
* **Index number** — Tornqvist index with time-varying factor shares.

Usage (once implemented)
-------------------------
    from econflow.processing.tfp import TFPProcessor
    tfp = TFPProcessor(method="growth_accounting", alpha=0.35)
    panel = tfp.compute(panel, output_col="cgdpo", capital_col="ck", labour_col="emp")
"""

from __future__ import annotations

from typing import Literal

import pandas as pd

TFPMethod = Literal["direct_pwt", "growth_accounting", "tornqvist"]


class TFPProcessor:
    """
    Computes TFP levels and growth rates from a panel DataFrame.

    Parameters
    ----------
    method:
        TFP derivation approach.
    alpha:
        Capital income share (used in growth-accounting and Tornqvist methods).
        Ignored for ``"direct_pwt"``.
    entity_col:
        Column name for the cross-sectional identifier.
    time_col:
        Column name for the time period.
    """

    def __init__(
        self,
        method: TFPMethod = "direct_pwt",
        alpha: float = 0.35,
        entity_col: str = "iso3",
        time_col: str = "year",
    ) -> None:
        self.method = method
        self.alpha = alpha
        self.entity_col = entity_col
        self.time_col = time_col

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def compute(self, df: pd.DataFrame, **column_map: str) -> pd.DataFrame:
        """
        Compute TFP and append it as new columns to *df*.

        Parameters
        ----------
        df:
            Wide-format panel DataFrame.
        **column_map:
            Keyword arguments mapping expected role names to actual column
            names, e.g. ``output_col="cgdpo"``, ``capital_col="ck"``,
            ``labour_col="emp"``.

        Returns
        -------
        pd.DataFrame
            *df* with additional columns ``tfp_level`` and ``tfp_growth``
            appended.
        """
        raise NotImplementedError

    def growth_decomposition(self, df: pd.DataFrame, **column_map: str) -> pd.DataFrame:
        """
        Decompose output growth into factor accumulation and TFP components.

        Returns a DataFrame with columns:
        ``["output_growth", "capital_contrib", "labour_contrib", "tfp_growth"]``.
        """
        raise NotImplementedError

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _solow_residual(
        self,
        df: pd.DataFrame,
        output_col: str,
        capital_col: str,
        labour_col: str,
    ) -> pd.Series:
        """Compute log Solow residual within each entity."""
        raise NotImplementedError
