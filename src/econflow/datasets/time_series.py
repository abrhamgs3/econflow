"""
econflow.datasets.time_series — TimeSeriesDataset.

A ``TimeSeriesDataset`` represents observations for a single entity over
multiple time periods.  Examples: IMF world-level TFP growth, a single
country's macroeconomic indicators, or a global index time series.

Unlike :class:`~econflow.datasets.panel.PanelDataset`, there is no
``entity_identifier`` (the entity context, if any, is stored in
``metadata``).  ``panel_balance`` always returns ``None``.
"""

from __future__ import annotations

import pandas as pd

from econflow.datasets.base import Dataset
from econflow.datasets.types import (
    DatasetMetadata,
    ProvenanceRecord,
    ValidationStatus,
)


class TimeSeriesDataset(Dataset):
    """
    Time-series Dataset: one observation per time period for a single entity.

    Parameters
    ----------
    df:
        DataFrame with one row per time period, sorted (or sortable) by
        *time_col*.
    time_col:
        Column that identifies the time period (e.g. ``"year"``).
    metadata:
        Optional human-readable metadata.  Consider setting
        ``metadata.description`` to identify the entity (e.g. ``"World Bank
        global TFP index"``).
    provenance:
        Optional lineage record.
    """

    def __init__(
        self,
        df: pd.DataFrame,
        time_col: str = "year",
        metadata: DatasetMetadata | None = None,
        provenance: ProvenanceRecord | None = None,
    ) -> None:
        super().__init__(df, metadata=metadata, provenance=provenance)
        self._time_col = time_col

    # ------------------------------------------------------------------
    # Dataset interface
    # ------------------------------------------------------------------

    @property
    def entity_identifier(self) -> None:
        """Always ``None`` — a time series has a single implicit entity."""
        return None

    @property
    def time_identifier(self) -> str:
        """Name of the time column."""
        return self._time_col

    # panel_balance inherited from base → returns None

    # ------------------------------------------------------------------
    # Internal builders
    # ------------------------------------------------------------------

    def _infer_role(self, col: str) -> str:
        if col == self._time_col:
            return "time"
        if col.startswith("ln_"):
            return "regressor"
        return "unknown"

    def _validate(self) -> ValidationStatus:
        errors: list[str] = []
        warnings: list[str] = []

        if len(self._df) == 0:
            errors.append("Dataset is empty (0 rows)")
            return ValidationStatus(is_valid=False, errors=errors)

        if self._time_col not in self._df.columns:
            errors.append(
                f"Time column '{self._time_col}' not found. "
                f"Available: {list(self._df.columns)}"
            )
        elif self._df[self._time_col].duplicated().any():
            n_dupes = int(self._df[self._time_col].duplicated().sum())
            errors.append(
                f"{n_dupes} duplicate '{self._time_col}' values found. "
                "Each time period must appear exactly once in a time series."
            )

        return ValidationStatus(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )

    def __repr__(self) -> str:
        n_periods = (
            self._df[self._time_col].nunique()
            if self._time_col in self._df.columns
            else len(self._df)
        )
        return (
            f"<TimeSeriesDataset "
            f"rows={len(self._df)} "
            f"periods={n_periods} "
            f"time_col='{self._time_col}'>"
        )
