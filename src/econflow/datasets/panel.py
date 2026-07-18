"""
econflow.datasets.panel — PanelDataset: the primary Dataset type for EconFlow.

A ``PanelDataset`` wraps a wide-format panel DataFrame (one row per
entity-year observation) and exposes the full Dataset property contract
plus panel-specific diagnostics:

* ``entity_identifier`` / ``time_identifier`` — the column names used to
  identify entities and time periods.
* ``panel_balance``     — counts of entities, periods, observations, and the
  balance ratio.
* ``to_multiindex_dataframe()`` — returns a copy indexed by
  (entity_col, time_col), equivalent to the legacy ``_to_panel()`` function.
* ``to_dataframe()``    — returns a flat copy (RangeIndex) suitable for
  passing to legacy functions that still expect a plain DataFrame.
* ``rename_entity_col()`` — returns a new ``PanelDataset`` with the entity
  column renamed, resolving the ``"country"`` vs ``"iso3"`` bifurcation.

P0 safety note
--------------
The ``to_dataframe()`` method returns an exact copy of the internal
flat DataFrame.  If the ``PanelDataset`` was constructed from a flat
DataFrame ``df``, then ``panel_ds.to_dataframe()`` is byte-for-byte
equivalent to ``df.copy()``.  This guarantee means that substituting
``PanelDataset`` for ``pd.DataFrame`` in ``econometrics/panel.py`` does
NOT change any downstream ``dropna()`` or ``groupby`` behavior.
"""

from __future__ import annotations

import functools

import pandas as pd

from econflow.datasets.base import Dataset
from econflow.datasets.types import (
    DatasetMetadata,
    PanelBalance,
    ProvenanceRecord,
    ValidationStatus,
)


class PanelDataset(Dataset):
    """
    Panel Dataset: entity × time observations in wide format.

    Parameters
    ----------
    df:
        Wide-format panel DataFrame.  May have a flat ``RangeIndex`` or a
        ``(entity_col, time_col)`` ``MultiIndex``; the constructor normalises
        both to a flat ``RangeIndex`` internally.
    entity_col:
        Name of the cross-sectional identifier column (e.g. ``"country"``).
    time_col:
        Name of the time period column (e.g. ``"year"``).
    metadata:
        Optional human-readable metadata.
    provenance:
        Optional lineage record.
    """

    def __init__(
        self,
        df: pd.DataFrame,
        entity_col: str = "country",
        time_col: str = "year",
        metadata: DatasetMetadata | None = None,
        provenance: ProvenanceRecord | None = None,
    ) -> None:
        if not isinstance(df, pd.DataFrame):
            raise TypeError(
                f"PanelDataset requires a pd.DataFrame; got {type(df).__name__!r}. "
                "Use econflow.datasets.migration.from_dataframe() to convert."
            )
        # Normalise: if the DataFrame has a (entity, time) MultiIndex, flatten it
        work = df.copy()
        if set(work.index.names) == {entity_col, time_col}:
            work = work.reset_index()

        super().__init__(work, metadata=metadata, provenance=provenance)
        self._entity_col = entity_col
        self._time_col = time_col

    # ------------------------------------------------------------------
    # Required Dataset properties
    # ------------------------------------------------------------------

    @property
    def entity_identifier(self) -> str:
        """Name of the entity column (e.g. ``"country"`` or ``"iso3"``)."""
        return self._entity_col

    @property
    def time_identifier(self) -> str:
        """Name of the time column (e.g. ``"year"``)."""
        return self._time_col

    # ------------------------------------------------------------------
    # Panel-specific properties
    # ------------------------------------------------------------------

    @functools.cached_property
    def panel_balance(self) -> PanelBalance:
        """
        Panel structure diagnostics: entity count, period count, balance ratio.

        Computed lazily on first access and then cached.
        """
        return self._compute_panel_balance()

    # ------------------------------------------------------------------
    # Conversion helpers
    # ------------------------------------------------------------------

    def to_dataframe(self) -> pd.DataFrame:
        """
        Return a flat copy of the underlying DataFrame (RangeIndex).

        This is the primary method for handing data back to legacy functions
        that expect a plain ``pd.DataFrame``.  The returned DataFrame is
        byte-for-byte equivalent to the one passed to the constructor
        (after MultiIndex normalisation).

        P0 note: no sorting, reindexing, or column manipulation is performed.
        The result is identical to what ``load_panel()`` would have returned.
        """
        df = self._df.copy()
        # Ensure any lingering MultiIndex is flattened
        if set(df.index.names) == {self._entity_col, self._time_col}:
            df = df.reset_index()
        return df

    def to_multiindex_dataframe(
        self,
        entity_col: str | None = None,
        time_col: str | None = None,
    ) -> pd.DataFrame:
        """
        Return a copy indexed by ``(entity_col, time_col)``.

        This method is the functional equivalent of ``econometrics.panel._to_panel()``.
        The output is sorted by the MultiIndex, matching the legacy behaviour.

        Parameters
        ----------
        entity_col:
            Override the entity column name.  Defaults to ``self.entity_identifier``.
        time_col:
            Override the time column name.  Defaults to ``self.time_identifier``.

        Raises
        ------
        ValueError
            If the required columns are not present.
        """
        ec = entity_col or self._entity_col
        tc = time_col or self._time_col
        work = self._df.copy()
        # Already indexed
        if list(work.index.names) == [ec, tc]:
            return work.sort_index()
        if not {ec, tc}.issubset(work.columns):
            raise ValueError(
                f"Data must include '{ec}' and '{tc}' columns "
                f"or a ({ec}, {tc}) MultiIndex."
            )
        return work.set_index([ec, tc]).sort_index()

    def rename_entity_col(self, new_name: str) -> PanelDataset:
        """
        Return a new ``PanelDataset`` with the entity column renamed.

        This is the adapter for resolving the ``"country"`` vs ``"iso3"``
        bifurcation: call this before passing a Dataset produced by the
        ingestion layer (``"iso3"``) to the econometrics layer (``"country"``).

        Parameters
        ----------
        new_name:
            The new entity column name.

        Returns
        -------
        PanelDataset
            New dataset with the entity column renamed and ``entity_identifier``
            updated accordingly.  All other columns and metadata are preserved.
        """
        if self._entity_col == new_name:
            return self.copy()
        renamed_df = self._df.rename(columns={self._entity_col: new_name})
        return PanelDataset(
            df=renamed_df,
            entity_col=new_name,
            time_col=self._time_col,
            metadata=self._metadata,
            provenance=self._provenance.add_transformation(
                f"rename_entity_col('{self._entity_col}' → '{new_name}')"
            ),
        )

    def copy(self) -> PanelDataset:
        """Return a deep copy of this ``PanelDataset``."""
        return PanelDataset(
            df=self._df.copy(),
            entity_col=self._entity_col,
            time_col=self._time_col,
            metadata=self._metadata,
            provenance=self._provenance,
        )

    # ------------------------------------------------------------------
    # Repr
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Internal builders (override from Dataset base)
    # ------------------------------------------------------------------

    def _infer_role(self, col: str) -> str:
        """Infer column role from name heuristics."""
        if col == self._entity_col:
            return "entity"
        if col == self._time_col:
            return "time"
        if col.startswith("ln_"):
            return "regressor"
        if col.endswith("_flag") or col.endswith("_dummy"):
            return "flag"
        if col.endswith("_index") and col not in ("AI_index",):
            return "regressor"
        return "unknown"

    def _compute_panel_balance(self) -> PanelBalance:
        df = self._df
        entity_col = self._entity_col
        time_col = self._time_col

        if entity_col not in df.columns or time_col not in df.columns:
            return PanelBalance(
                n_entities=0,
                n_periods=0,
                total_obs=len(df),
                expected_obs=0,
                balance_ratio=0.0,
                is_balanced=False,
                min_obs_per_entity=0,
                max_obs_per_entity=0,
                entity_col=entity_col,
                time_col=time_col,
            )

        obs_per_entity = df.groupby(entity_col)[time_col].count()
        n_entities = len(obs_per_entity)
        n_periods = int(df[time_col].nunique())
        total_obs = len(df)
        expected_obs = n_entities * n_periods

        return PanelBalance(
            n_entities=n_entities,
            n_periods=n_periods,
            total_obs=total_obs,
            expected_obs=expected_obs,
            balance_ratio=total_obs / expected_obs if expected_obs > 0 else 0.0,
            is_balanced=(total_obs == expected_obs),
            min_obs_per_entity=int(obs_per_entity.min()) if n_entities > 0 else 0,
            max_obs_per_entity=int(obs_per_entity.max()) if n_entities > 0 else 0,
            entity_col=entity_col,
            time_col=time_col,
        )

    def _validate(self) -> ValidationStatus:
        errors: list[str] = []
        warnings: list[str] = []

        if len(self._df) == 0:
            errors.append("Dataset is empty (0 rows)")
            return ValidationStatus(is_valid=False, errors=errors)

        # Entity column present?
        if (
            self._entity_col not in self._df.columns
            and self._entity_col not in (self._df.index.names or [])
        ):
            errors.append(
                f"Entity column '{self._entity_col}' not found in DataFrame columns "
                f"or index.  Available columns: {list(self._df.columns)}"
            )

        # Time column present?
        if (
            self._time_col not in self._df.columns
            and self._time_col not in (self._df.index.names or [])
        ):
            errors.append(
                f"Time column '{self._time_col}' not found in DataFrame columns "
                f"or index.  Available columns: {list(self._df.columns)}"
            )

        # Duplicate (entity, time) pairs?
        if (
            self._entity_col in self._df.columns
            and self._time_col in self._df.columns
        ):
            n_dupes = int(
                self._df.duplicated(subset=[self._entity_col, self._time_col]).sum()
            )
            if n_dupes > 0:
                errors.append(
                    f"{n_dupes} duplicate ({self._entity_col}, {self._time_col}) "
                    "pairs found.  Each entity-time combination must be unique."
                )

            # Warn if highly unbalanced
            bal = self._compute_panel_balance()
            if bal.balance_ratio < 0.5:
                warnings.append(
                    f"Panel is severely unbalanced (balance_ratio={bal.balance_ratio:.2f}). "
                    "This may affect estimator performance."
                )

        return ValidationStatus(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )

    def __repr__(self) -> str:
        return (
            f"<PanelDataset "
            f"rows={len(self._df)} "
            f"entities={self.panel_balance.n_entities if self.panel_balance else '?'} "
            f"periods={self.panel_balance.n_periods if self.panel_balance else '?'} "
            f"entity_col='{self._entity_col}' "
            f"time_col='{self._time_col}'>"
        )
