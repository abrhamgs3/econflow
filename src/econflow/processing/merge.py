"""
econflow.processing.merge — Dataset merging across sources.

Merges harmonised long-format DataFrames from multiple connectors into a
single balanced (or unbalanced) panel indexed by ``(iso3, year)``.

Merge strategy
--------------
1. Each source frame is expected to have columns ``["iso3", "year",
   "indicator", "value"]`` after harmonisation.
2. Frames are pivoted to wide format (one column per indicator), then
   joined on ``(iso3, year)`` using a configurable join type (inner / outer /
   left).
3. Duplicate ``(iso3, year, indicator)`` triplets are resolved by a
   configurable priority ordering (e.g. PWT > WB).

Usage (once implemented)
-------------------------
    from econflow.processing.merge import DatasetMerger
    merger = DatasetMerger(join="outer", priority=["pwt", "world_bank", "oecd"])
    panel = merger.merge({"world_bank": df_wb, "oecd": df_oecd, "pwt": df_pwt})
"""

from __future__ import annotations

import pandas as pd


class DatasetMerger:
    """
    Merges multiple harmonised source DataFrames into a panel.

    Parameters
    ----------
    join:
        SQL-style join type applied when combining source frames.
        One of ``"inner"``, ``"outer"``, ``"left"``.
    priority:
        Ordered list of source names; when the same indicator appears in
        multiple sources, the value from the highest-priority source wins.
    """

    def __init__(
        self,
        join: str = "outer",
        priority: list[str] | None = None,
    ) -> None:
        self.join = join
        self.priority = priority or []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def merge(self, frames: dict[str, pd.DataFrame]) -> pd.DataFrame:
        """
        Combine *frames* into a single wide-format panel DataFrame.

        Parameters
        ----------
        frames:
            Mapping of source name → long-format tidy DataFrame.

        Returns
        -------
        pd.DataFrame
            Wide panel with a ``MultiIndex`` of ``(iso3, year)`` and one
            column per indicator.
        """
        raise NotImplementedError

    def coverage_report(self, panel: pd.DataFrame) -> pd.DataFrame:
        """
        Return a DataFrame summarising observation counts and missingness
        rates per indicator across countries and years.
        """
        raise NotImplementedError

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _pivot_to_wide(self, df: pd.DataFrame, source: str) -> pd.DataFrame:
        """Pivot a long-format frame to wide format, namespacing columns."""
        raise NotImplementedError

    def _resolve_duplicates(self, wide: pd.DataFrame) -> pd.DataFrame:
        """Apply *priority* ordering to select values when columns conflict."""
        raise NotImplementedError
