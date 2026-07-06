"""
econflow.datasets.cross_section — CrossSectionDataset.

A ``CrossSectionDataset`` represents a single cross-sectional snapshot:
one row per entity, no repeated time observations.  This is appropriate
for country-level averages, census data, or any single-period comparison.

Unlike :class:`~econflow.datasets.panel.PanelDataset`, there is no
``time_identifier`` (the time context, if any, is stored in ``metadata``).
``panel_balance`` always returns ``None``.
"""

from __future__ import annotations

import pandas as pd

from econflow.datasets.base import Dataset
from econflow.datasets.types import (
    DatasetMetadata,
    ProvenanceRecord,
    ValidationStatus,
)


class CrossSectionDataset(Dataset):
    """
    Cross-sectional Dataset: one observation per entity (no time dimension).

    Parameters
    ----------
    df:
        DataFrame with one row per entity.
    entity_col:
        Column that uniquely identifies each entity (e.g. ``"country"``).
    metadata:
        Optional human-readable metadata.  Consider setting ``metadata.title``
        and noting the reference year in ``metadata.description``.
    provenance:
        Optional lineage record.
    """

    def __init__(
        self,
        df: pd.DataFrame,
        entity_col: str = "country",
        metadata: DatasetMetadata | None = None,
        provenance: ProvenanceRecord | None = None,
    ) -> None:
        super().__init__(df, metadata=metadata, provenance=provenance)
        self._entity_col = entity_col

    # ------------------------------------------------------------------
    # Dataset interface
    # ------------------------------------------------------------------

    @property
    def entity_identifier(self) -> str:
        """Name of the entity column."""
        return self._entity_col

    @property
    def time_identifier(self) -> None:
        """Always ``None`` — cross-sections have no time dimension."""
        return None

    # panel_balance inherited from base → returns None

    # ------------------------------------------------------------------
    # Internal builders
    # ------------------------------------------------------------------

    def _infer_role(self, col: str) -> str:
        if col == self._entity_col:
            return "entity"
        if col.startswith("ln_"):
            return "regressor"
        return "unknown"

    def _validate(self) -> ValidationStatus:
        errors: list[str] = []
        warnings: list[str] = []

        if len(self._df) == 0:
            errors.append("Dataset is empty (0 rows)")
            return ValidationStatus(is_valid=False, errors=errors)

        if self._entity_col not in self._df.columns:
            errors.append(
                f"Entity column '{self._entity_col}' not found. "
                f"Available: {list(self._df.columns)}"
            )
        elif self._df[self._entity_col].duplicated().any():
            n_dupes = int(self._df[self._entity_col].duplicated().sum())
            errors.append(
                f"{n_dupes} duplicate '{self._entity_col}' values found. "
                "Each entity must appear exactly once in a cross-section."
            )

        return ValidationStatus(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )

    def __repr__(self) -> str:
        n_entities = (
            self._df[self._entity_col].nunique()
            if self._entity_col in self._df.columns
            else len(self._df)
        )
        return (
            f"<CrossSectionDataset "
            f"rows={len(self._df)} "
            f"entities={n_entities} "
            f"entity_col='{self._entity_col}'>"
        )
