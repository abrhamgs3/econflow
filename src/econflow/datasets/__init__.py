"""
econflow.datasets — Dataset abstraction layer (Architecture Stabilization Milestone 2).

Replaces raw ``pd.DataFrame`` passing with typed Dataset objects that carry
metadata, provenance, variable registries, missingness diagnostics, and
panel structure information alongside the data.

Dataset hierarchy
-----------------
Dataset (abstract base)
├── PanelDataset          — entity × time panel (primary type for EconFlow)
├── CrossSectionDataset   — single cross-section (one row per entity)
├── TimeSeriesDataset     — single entity over time
└── SpatialDataset        — entities with geographic coordinates (stub)

Shared types
------------
DatasetMetadata     human-readable title, description, source, tags
ProvenanceRecord    lineage: origin, input paths, transformation history
ColumnInfo          per-column dtype, role, missingness
VariableRegistry    typed dict of ColumnInfo objects
MissingnessSummary  per-column NaN counts and overall pct
PanelBalance        entity count, period count, balance ratio
ValidationStatus    is_valid flag + error/warning lists
SelectionSummary    typed replacement for legacy .attrs-based summary

Migration utilities
-------------------
from_dataframe(df, ...)     convert DataFrame to PanelDataset
to_dataframe(ds_or_df)      extract DataFrame from Dataset or pass through
rename_entity_col(ds, name) resolve "country" vs "iso3" bifurcation
accepts_dataset             decorator for legacy DataFrame-accepting functions

Quick start
-----------
    from econflow.datasets import PanelDataset, from_dataframe

    # Wrap an existing DataFrame
    ds = from_dataframe(df, entity_col="country", time_col="year")

    # Or construct directly
    ds = PanelDataset(df, entity_col="country", time_col="year")

    # Inspect
    print(ds.panel_balance)
    print(ds.missingness_summary.to_series())
    print(ds.validation_status)

    # Convert back to DataFrame for legacy functions
    raw_df = ds.to_dataframe()

    # Get MultiIndex form for linearmodels
    indexed_df = ds.to_multiindex_dataframe()
"""

from econflow.datasets.base import Dataset
from econflow.datasets.cross_section import CrossSectionDataset
from econflow.datasets.migration import accepts_dataset, from_dataframe, rename_entity_col, to_dataframe
from econflow.datasets.panel import PanelDataset
from econflow.datasets.spatial import SpatialDataset
from econflow.datasets.time_series import TimeSeriesDataset
from econflow.datasets.types import (
    ColumnInfo,
    DatasetMetadata,
    MissingnessSummary,
    PanelBalance,
    ProvenanceRecord,
    SelectionSummary,
    ValidationStatus,
    VariableRegistry,
)

__all__ = [
    # Dataset classes
    "Dataset",
    "PanelDataset",
    "CrossSectionDataset",
    "TimeSeriesDataset",
    "SpatialDataset",
    # Shared types
    "DatasetMetadata",
    "ProvenanceRecord",
    "ColumnInfo",
    "VariableRegistry",
    "MissingnessSummary",
    "PanelBalance",
    "ValidationStatus",
    "SelectionSummary",
    # Migration utilities
    "from_dataframe",
    "to_dataframe",
    "rename_entity_col",
    "accepts_dataset",
]
