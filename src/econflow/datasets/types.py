"""
econflow.datasets.types — Shared value-object types for the Dataset layer.

All types here are plain dataclasses or enums with no pandas dependency in
their definition.  This keeps the type layer importable without triggering a
heavy pandas import chain.

Classes
-------
DatasetMetadata      Human-readable provenance metadata.
ProvenanceRecord     Lineage record (how was this Dataset created?).
ColumnInfo           Per-column metadata entry in the variable registry.
VariableRegistry     Typed dict of column name → ColumnInfo.
MissingnessSummary   Per-column missing-value counts and aggregates.
PanelBalance         Panel structure diagnostics (balance ratio, entity/time counts).
ValidationStatus     Result of running domain validation checks.
SelectionSummary     Typed replacement for the legacy .attrs-based summary
                     returned by data.cleaning.sample_selection_summary().
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field

import pandas as pd

# ---------------------------------------------------------------------------
# Metadata and provenance
# ---------------------------------------------------------------------------


@dataclass
class DatasetMetadata:
    """Human-readable metadata attached to every Dataset instance."""

    title: str = ""
    description: str = ""
    source: str = ""
    created_at: datetime.datetime = field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc)
    )
    tags: list[str] = field(default_factory=list)

    def __repr__(self) -> str:
        return f"DatasetMetadata(title={self.title!r}, source={self.source!r})"


@dataclass
class ProvenanceRecord:
    """Lineage record describing how a Dataset was produced or transformed."""

    origin: str = "unknown"
    input_paths: list[str] = field(default_factory=list)
    transformations: list[str] = field(default_factory=list)
    created_at: datetime.datetime = field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc)
    )

    def add_transformation(self, description: str) -> ProvenanceRecord:
        """Return a new ProvenanceRecord with *description* appended."""
        return ProvenanceRecord(
            origin=self.origin,
            input_paths=list(self.input_paths),
            transformations=[*self.transformations, description],
            created_at=datetime.datetime.now(datetime.timezone.utc),
        )


# ---------------------------------------------------------------------------
# Variable registry
# ---------------------------------------------------------------------------

#: Known column roles within the panel data.
VALID_ROLES = frozenset(
    {
        "entity",       # cross-sectional identifier (e.g. country)
        "time",         # time period identifier (e.g. year)
        "outcome",      # dependent variable
        "regressor",    # explanatory variable
        "control",      # control variable
        "instrument",   # excluded instrument
        "identifier",   # administrative identifier (not used in models)
        "flag",         # binary flag column
        "unknown",      # role not yet assigned
    }
)


@dataclass
class ColumnInfo:
    """Metadata for a single column in the variable registry."""

    name: str
    dtype: str
    role: str = "unknown"
    description: str = ""
    n_missing: int = 0
    pct_missing: float = 0.0

    def __post_init__(self) -> None:
        if self.role not in VALID_ROLES:
            raise ValueError(
                f"Unknown column role '{self.role}'. "
                f"Valid roles: {sorted(VALID_ROLES)}"
            )


@dataclass
class VariableRegistry:
    """Typed registry of all columns in a Dataset with their metadata."""

    columns: dict[str, ColumnInfo] = field(default_factory=dict)

    def __len__(self) -> int:
        return len(self.columns)

    def __contains__(self, name: str) -> bool:
        return name in self.columns

    def __getitem__(self, name: str) -> ColumnInfo:
        return self.columns[name]

    def __repr__(self) -> str:
        return f"VariableRegistry({len(self)} columns)"

    def names(self) -> list[str]:
        """Return all registered column names."""
        return list(self.columns.keys())

    def by_role(self, role: str) -> list[ColumnInfo]:
        """Return all ColumnInfo entries with the given *role*."""
        return [c for c in self.columns.values() if c.role == role]

    def assign_role(self, name: str, role: str) -> None:
        """Set the role for column *name* in place.

        Raises
        ------
        KeyError
            If *name* is not in the registry.
        ValueError
            If *role* is not a member of :data:`VALID_ROLES`.
        """
        if name not in self.columns:
            raise KeyError(f"Column '{name}' not in registry")
        if role not in VALID_ROLES:
            raise ValueError(
                f"Invalid role {role!r}. Valid roles: {sorted(VALID_ROLES)}"
            )
        self.columns[name].role = role


# ---------------------------------------------------------------------------
# Missingness
# ---------------------------------------------------------------------------


@dataclass
class MissingnessSummary:
    """Per-column missing-value counts for a Dataset."""

    by_column: dict[str, int]   # column name → count of NaN values
    total_cells: int
    total_missing: int

    @property
    def pct_missing(self) -> float:
        """Fraction of cells that are missing across the entire DataFrame."""
        return self.total_missing / self.total_cells if self.total_cells > 0 else 0.0

    @property
    def complete_columns(self) -> list[str]:
        """Columns with zero missing values."""
        return [col for col, n in self.by_column.items() if n == 0]

    @property
    def incomplete_columns(self) -> list[str]:
        """Columns with at least one missing value."""
        return [col for col, n in self.by_column.items() if n > 0]

    def to_series(self) -> pd.Series:
        """Return missing counts as a named Series."""
        return pd.Series(self.by_column, name="n_missing").sort_values(ascending=False)


# ---------------------------------------------------------------------------
# Panel balance
# ---------------------------------------------------------------------------


@dataclass
class PanelBalance:
    """
    Structural diagnostics for a balanced/unbalanced panel.

    A perfectly balanced panel has ``balance_ratio == 1.0``.
    """

    n_entities: int
    n_periods: int
    total_obs: int
    expected_obs: int           # n_entities × n_periods (perfectly balanced)
    balance_ratio: float        # total_obs / expected_obs
    is_balanced: bool
    min_obs_per_entity: int
    max_obs_per_entity: int
    entity_col: str
    time_col: str

    def __repr__(self) -> str:
        status = "balanced" if self.is_balanced else f"unbalanced ({self.balance_ratio:.1%})"
        return (
            f"PanelBalance(entities={self.n_entities}, "
            f"periods={self.n_periods}, "
            f"obs={self.total_obs}/{self.expected_obs}, "
            f"{status})"
        )


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


@dataclass
class ValidationStatus:
    """Result of running domain validation checks on a Dataset."""

    is_valid: bool = True
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    checked_at: datetime.datetime | None = None

    def __repr__(self) -> str:
        status = "valid" if self.is_valid else f"INVALID ({len(self.errors)} errors)"
        return f"ValidationStatus({status}, {len(self.warnings)} warnings)"


# ---------------------------------------------------------------------------
# Selection summary (replaces .attrs-based transport)
# ---------------------------------------------------------------------------


@dataclass
class SelectionSummary:
    """
    Typed replacement for ``cleaning.sample_selection_summary().attrs``.

    Previously, aggregate sample-size counts were stored in ``df.attrs``, a
    pandas dict that is silently dropped by many operations (merge, concat,
    copy in older pandas versions).  This dataclass makes those counts
    first-class typed fields, eliminating the silent ``"NA"`` regression that
    occurred when ``.attrs`` was lost.

    Usage
    -----
    Build from the legacy DataFrame::

        summary_df = sample_selection_summary(df)
        sel = SelectionSummary.from_legacy_dataframe(summary_df)

    Or build directly::

        sel = SelectionSummary(
            in_sample_rows=1420,
            out_of_sample_rows=8901,
            in_sample_countries=95,
            out_of_sample_countries=98,
            comparison_frame=summary_df,
        )
    """

    in_sample_rows: int
    out_of_sample_rows: int
    in_sample_countries: int
    out_of_sample_countries: int
    comparison_frame: pd.DataFrame = field(default_factory=pd.DataFrame)

    @classmethod
    def from_legacy_dataframe(cls, df: pd.DataFrame) -> SelectionSummary:
        """
        Build a ``SelectionSummary`` from a legacy ``.attrs``-bearing DataFrame
        returned by :func:`~econflow.data.cleaning.sample_selection_summary`.

        Defaults to ``0`` for any missing ``.attrs`` key — the same as the
        previous ``attrs.get(..., 'NA')`` behavior, but type-safe.
        """
        return cls(
            in_sample_rows=int(df.attrs.get("in_sample_rows", 0)),
            out_of_sample_rows=int(df.attrs.get("out_of_sample_rows", 0)),
            in_sample_countries=int(df.attrs.get("in_sample_countries", 0)),
            out_of_sample_countries=int(df.attrs.get("out_of_sample_countries", 0)),
            comparison_frame=df.copy(),
        )
