"""
econflow.datasets.spatial — SpatialDataset (stub).

A ``SpatialDataset`` is a cross-section or panel augmented with geographic
coordinates, enabling spatial econometric methods (spatial lag, spatial error,
geographically weighted regression).

This is a **stub** — the class hierarchy and interface are defined here but
no spatial methods are implemented.  Spatial econometrics is planned for a
future milestone.

Planned capabilities (not yet implemented)
-------------------------------------------
* Distance-matrix construction (great-circle, economic distance).
* Spatial weight matrices (k-nearest neighbours, queen/rook contiguity).
* Moran's I spatial autocorrelation test.
* Spatial lag and spatial error model fitting via ``spreg`` or ``pysal``.
"""

from __future__ import annotations

import pandas as pd

from econflow.datasets.base import Dataset
from econflow.datasets.types import (
    DatasetMetadata,
    ProvenanceRecord,
    ValidationStatus,
)


class SpatialDataset(Dataset):
    """
    Spatial Dataset: entities with geographic coordinates.

    Extends the base Dataset contract with latitude/longitude columns
    to support spatial econometric methods.  All spatial computation methods
    are stubs pending Milestone 3.

    Parameters
    ----------
    df:
        DataFrame with one row per entity.  Must include *latitude_col* and
        *longitude_col* columns.
    entity_col:
        Entity identifier column (e.g. ``"country"``).
    latitude_col:
        Column with latitude in decimal degrees (default ``"lat"``).
    longitude_col:
        Column with longitude in decimal degrees (default ``"lon"``).
    time_col:
        Optional time column for spatio-temporal panels.
    metadata / provenance:
        Optional metadata and lineage.
    """

    def __init__(
        self,
        df: pd.DataFrame,
        entity_col: str = "country",
        latitude_col: str = "lat",
        longitude_col: str = "lon",
        time_col: str | None = None,
        metadata: DatasetMetadata | None = None,
        provenance: ProvenanceRecord | None = None,
    ) -> None:
        super().__init__(df, metadata=metadata, provenance=provenance)
        self._entity_col = entity_col
        self._latitude_col = latitude_col
        self._longitude_col = longitude_col
        self._time_col = time_col

    # ------------------------------------------------------------------
    # Dataset interface
    # ------------------------------------------------------------------

    @property
    def entity_identifier(self) -> str:
        """Name of the entity column."""
        return self._entity_col

    @property
    def time_identifier(self) -> str | None:
        """Name of the time column, or ``None`` for pure cross-sections."""
        return self._time_col

    @property
    def latitude_col(self) -> str:
        """Name of the latitude column."""
        return self._latitude_col

    @property
    def longitude_col(self) -> str:
        """Name of the longitude column."""
        return self._longitude_col

    # ------------------------------------------------------------------
    # Spatial methods (stubs — Milestone 3)
    # ------------------------------------------------------------------

    def distance_matrix(self, metric: str = "great_circle") -> pd.DataFrame:
        """
        Compute entity-to-entity distance matrix.

        Parameters
        ----------
        metric:
            ``"great_circle"`` (Haversine) or ``"economic"``
            (GDP-weighted distance).
        """
        raise NotImplementedError("Spatial methods planned for Milestone 3")

    def spatial_weights(self, method: str = "knn", k: int = 5) -> object:
        """
        Construct a spatial weights matrix (PySAL ``W`` object).

        Parameters
        ----------
        method:
            ``"knn"`` (k-nearest neighbours) or ``"contiguity"``.
        k:
            Number of neighbours for KNN.
        """
        raise NotImplementedError("Spatial methods planned for Milestone 3")

    def morans_i(self, variable: str) -> dict:
        """
        Compute Moran's I spatial autocorrelation statistic for *variable*.
        """
        raise NotImplementedError("Spatial methods planned for Milestone 3")

    # ------------------------------------------------------------------
    # Internal builders
    # ------------------------------------------------------------------

    def _infer_role(self, col: str) -> str:
        if col == self._entity_col:
            return "entity"
        if col == self._time_col:
            return "time"
        if col in (self._latitude_col, self._longitude_col):
            return "identifier"
        if col.startswith("ln_"):
            return "regressor"
        return "unknown"

    def _validate(self) -> ValidationStatus:
        errors: list[str] = []
        warnings: list[str] = []

        if len(self._df) == 0:
            errors.append("Dataset is empty (0 rows)")
            return ValidationStatus(is_valid=False, errors=errors)

        for col_label, col_name in [
            ("entity", self._entity_col),
            ("latitude", self._latitude_col),
            ("longitude", self._longitude_col),
        ]:
            if col_name not in self._df.columns:
                errors.append(
                    f"{col_label.capitalize()} column '{col_name}' not found. "
                    f"Available: {list(self._df.columns)}"
                )

        return ValidationStatus(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )

    def __repr__(self) -> str:
        return (
            f"<SpatialDataset "
            f"rows={len(self._df)} "
            f"entity_col='{self._entity_col}' "
            f"lat='{self._latitude_col}' "
            f"lon='{self._longitude_col}'>"
        )
