"""
econflow.datasets.base — Abstract Dataset base class.

All EconFlow Dataset types inherit from :class:`Dataset`.  The base class
provides:

* Defensive DataFrame storage (always copies the input).
* Lazy-computed properties (``variable_registry``, ``missingness_summary``,
  ``validation_status``) that are cached on first access via
  ``functools.cached_property``.
* Pandas-compatible pass-through operators (``__getitem__``, ``__len__``,
  ``__contains__``) so that code written for raw DataFrames continues to
  work without modification during the migration period.
* A ``dataframe`` property that always returns a defensive copy, preventing
  callers from accidentally mutating the stored data.
"""

from __future__ import annotations

import abc
import functools

import pandas as pd

from econflow.datasets.types import (
    ColumnInfo,
    DatasetMetadata,
    MissingnessSummary,
    PanelBalance,
    ProvenanceRecord,
    ValidationStatus,
    VariableRegistry,
)


class Dataset(abc.ABC):
    """
    Abstract base class for all EconFlow Dataset types.

    Parameters
    ----------
    df:
        The underlying data.  A defensive copy is stored internally; the
        caller's original DataFrame is never mutated.
    metadata:
        Human-readable metadata.  A blank :class:`DatasetMetadata` is used
        if not provided.
    provenance:
        Lineage record.  A blank :class:`ProvenanceRecord` is used if not
        provided.
    """

    def __init__(
        self,
        df: pd.DataFrame,
        metadata: DatasetMetadata | None = None,
        provenance: ProvenanceRecord | None = None,
    ) -> None:
        if not isinstance(df, pd.DataFrame):
            raise TypeError(
                f"Dataset requires a pd.DataFrame; got {type(df).__name__!r}. "
                "Use econflow.datasets.migration.from_dataframe() to convert."
            )
        self._df = df.copy()
        self._metadata = metadata or DatasetMetadata()
        self._provenance = provenance or ProvenanceRecord()

    # ------------------------------------------------------------------
    # Core properties (all Dataset subtypes)
    # ------------------------------------------------------------------

    @property
    def dataframe(self) -> pd.DataFrame:
        """Return a defensive copy of the underlying DataFrame.

        Always returns a copy — mutations by the caller do not affect the
        Dataset's internal state.
        """
        return self._df.copy()

    @property
    def metadata(self) -> DatasetMetadata:
        """Human-readable title, description, source, and tags."""
        return self._metadata

    @property
    def provenance(self) -> ProvenanceRecord:
        """Lineage record describing how this Dataset was created."""
        return self._provenance

    @property
    def entity_identifier(self) -> str | None:
        """
        Name of the entity/cross-section column (e.g. ``"country"``), or
        ``None`` if this Dataset type does not have an entity dimension.
        """
        return None

    @property
    def time_identifier(self) -> str | None:
        """
        Name of the time column (e.g. ``"year"``), or ``None`` if this
        Dataset type does not have a time dimension.
        """
        return None

    @functools.cached_property
    def variable_registry(self) -> VariableRegistry:
        """
        Registry of all columns with their inferred roles and missing-value
        counts.  Computed lazily on first access and then cached.
        """
        return self._build_variable_registry()

    @functools.cached_property
    def missingness_summary(self) -> MissingnessSummary:
        """
        Per-column missing-value counts and overall missingness statistics.
        Computed lazily on first access and then cached.
        """
        return self._build_missingness_summary()

    @property
    def panel_balance(self) -> PanelBalance | None:
        """
        Panel balance diagnostics.  Returns ``None`` for Dataset types that
        are not panels (e.g., :class:`CrossSectionDataset`).
        :class:`PanelDataset` overrides this with a ``cached_property``.
        """
        return None

    @functools.cached_property
    def validation_status(self) -> ValidationStatus:
        """
        Result of running domain-specific validation checks.  Computed lazily
        on first access and then cached.
        """
        return self._validate()

    # ------------------------------------------------------------------
    # Shape and column access
    # ------------------------------------------------------------------

    @property
    def columns(self) -> list[str]:
        """Names of all columns in the underlying DataFrame."""
        return list(self._df.columns)

    @property
    def shape(self) -> tuple[int, int]:
        """``(n_rows, n_columns)`` shape of the underlying DataFrame."""
        return self._df.shape

    def __len__(self) -> int:
        return len(self._df)

    def __repr__(self) -> str:
        return (
            f"<{self.__class__.__name__} "
            f"rows={len(self._df)} cols={len(self._df.columns)}"
            f"{' title=' + repr(self._metadata.title) if self._metadata.title else ''}>"
        )

    # ------------------------------------------------------------------
    # Pandas-compatible pass-through operators
    # ------------------------------------------------------------------

    def __getitem__(self, key: str | list[str]) -> pd.Series | pd.DataFrame:
        """Column access — identical to ``df[key]``."""
        return self._df[key]

    def __contains__(self, key: str) -> bool:
        """``col in dataset`` check — identical to ``col in df.columns``."""
        return key in self._df.columns

    def groupby(self, *args, **kwargs):
        """Delegate ``groupby`` to the underlying DataFrame."""
        return self._df.groupby(*args, **kwargs)

    def reset_index(self, *args, **kwargs) -> pd.DataFrame:
        """Delegate ``reset_index`` to the underlying DataFrame."""
        return self._df.reset_index(*args, **kwargs)

    # ------------------------------------------------------------------
    # Internal builders (override in subclasses for domain logic)
    # ------------------------------------------------------------------

    def _build_variable_registry(self) -> VariableRegistry:
        n = len(self._df)
        cols: dict[str, ColumnInfo] = {}
        for col in self._df.columns:
            n_missing = int(self._df[col].isna().sum())
            cols[col] = ColumnInfo(
                name=col,
                dtype=str(self._df[col].dtype),
                role=self._infer_role(col),
                n_missing=n_missing,
                pct_missing=n_missing / n if n > 0 else 0.0,
            )
        return VariableRegistry(columns=cols)

    def _build_missingness_summary(self) -> MissingnessSummary:
        n_rows, n_cols = self._df.shape
        by_col = {col: int(self._df[col].isna().sum()) for col in self._df.columns}
        total_missing = sum(by_col.values())
        return MissingnessSummary(
            by_column=by_col,
            total_cells=n_rows * n_cols,
            total_missing=total_missing,
        )

    def _infer_role(self, col: str) -> str:
        """Heuristic role inference from column name. Override in subclasses."""
        return "unknown"

    def _validate(self) -> ValidationStatus:
        """Base validation: empty DataFrame is an error. Override for more."""
        errors: list[str] = []
        warnings: list[str] = []
        if len(self._df) == 0:
            errors.append("Dataset is empty (0 rows)")
        return ValidationStatus(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )
