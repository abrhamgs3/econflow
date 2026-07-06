# Dataset Abstraction — Architecture Reference

**Milestone:** Architecture Stabilization Milestone 2  
**Status:** Implemented  
**Module:** `econflow.datasets`

---

## Overview

Before this milestone, EconFlow passed raw `pd.DataFrame` objects between every layer — loaders, cleaners, estimators, and outputs. DataFrames carry no semantic information about panel structure, entity/time column names, or data provenance. This caused three categories of bugs:

1. **Column name bifurcation** — ingestion used `"iso3"` while econometrics used `"country"`, with no systematic resolution point.
2. **`.attrs` fragility** — `data/cleaning.py` stored sample-selection counts in `df.attrs`; pandas silently drops `.attrs` on most transformations, causing `narrative.py` to silently read `"NA"` instead of real counts.
3. **`dropna()` sample sensitivity** — the exact in-sample rows are determined by `dropna()` inside `_fit_model()`. Any upstream reindex or sort that changes row order or adds rows would alter econometric results.

The Dataset abstraction resolves all three risks while preserving full backward compatibility.

---

## Type Hierarchy

```
Dataset (abstract base)                      econflow.datasets.base
├── PanelDataset                             econflow.datasets.panel
│     entity × time panel — primary type
├── CrossSectionDataset                      econflow.datasets.cross_section
│     one row per entity, no time dimension
├── TimeSeriesDataset                        econflow.datasets.time_series
│     one entity over multiple time periods
└── SpatialDataset (stub)                    econflow.datasets.spatial
      entities with lat/lon coordinates
      all spatial methods: NotImplementedError
```

---

## Dataset Contract

Every `Dataset` exposes:

| Property | Type | Notes |
|---|---|---|
| `dataframe` | `pd.DataFrame` | Defensive copy — mutations never propagate back |
| `metadata` | `DatasetMetadata` | Title, description, source, tags |
| `provenance` | `ProvenanceRecord` | Origin, input paths, transformation history |
| `entity_identifier` | `str \| None` | Column name for the entity dimension |
| `time_identifier` | `str \| None` | Column name for the time dimension |
| `variable_registry` | `VariableRegistry` | Per-column dtype, role, missingness (cached) |
| `missingness_summary` | `MissingnessSummary` | Column NaN counts, overall pct (cached) |
| `panel_balance` | `PanelBalance \| None` | Entity/period counts, balance ratio (cached) |
| `validation_status` | `ValidationStatus` | is_valid flag + error/warning lists (cached) |

Lazy properties (`variable_registry`, `missingness_summary`, `validation_status`, `panel_balance`) are computed on first access via `functools.cached_property`.

### Pandas pass-through operators

`Dataset` implements `__getitem__`, `__contains__`, `__len__`, `groupby()`, and `reset_index()` as pass-throughs to the underlying DataFrame. This allows legacy code that accesses `df[col]`, `col in df`, and `df.groupby(...)` to work unchanged when passed a Dataset.

`Dataset.columns` returns `list[str]` (not `pd.Index`). The `in` operator works identically.

---

## PanelDataset — Primary Type

`PanelDataset` is the type used by all estimators and the pipeline. Key methods:

### `to_dataframe() → pd.DataFrame`
Returns the flat (non-MultiIndex) DataFrame. Byte-for-byte equivalent to the constructor input. **P0 safe** — never reorders rows or adds/removes any data.

### `to_multiindex_dataframe(entity_col, time_col) → pd.DataFrame`
Sets `(entity, time)` MultiIndex and sorts. Equivalent to the legacy `_to_panel()` helper that existed in multiple places. Produces identical output.

### `rename_entity_col(new_name) → PanelDataset`
Returns a new `PanelDataset` with the entity column renamed. Used to resolve the `"country"` / `"iso3"` bifurcation at dataset boundaries rather than deep inside estimation logic.

---

## Value Types

All shared types live in `econflow.datasets.types` and have no dependency on pandas in their dataclass definitions.

| Type | Purpose |
|---|---|
| `DatasetMetadata` | Human-readable title, description, source, tags, created_at |
| `ProvenanceRecord` | origin, input_paths, transformations; `add_transformation()` returns new copy |
| `ColumnInfo` | name, dtype, role, description, n_missing, pct_missing |
| `VariableRegistry` | `dict[str, ColumnInfo]`; `names()`, `by_role()`, `assign_role()` |
| `MissingnessSummary` | by_column dict, total_cells, pct_missing, complete/incomplete_columns, to_series() |
| `PanelBalance` | n_entities, n_periods, total_obs, expected_obs, balance_ratio, is_balanced |
| `ValidationStatus` | is_valid, errors, warnings, checked_at |
| `SelectionSummary` | Typed replacement for `.attrs`-based sample-count transport |

`VALID_ROLES` is a `frozenset` of allowed column roles: `entity`, `time`, `outcome`, `regressor`, `control`, `instrument`, `identifier`, `flag`, `unknown`. `VariableRegistry.assign_role()` raises `ValueError` for any role not in this set.

---

## Migration Utilities

`econflow.datasets.migration` provides compatibility tools for the transition period.

```python
# Wrap an existing DataFrame
ds = from_dataframe(df, entity_col="country", time_col="year", title="My panel")

# Extract DataFrame from Dataset or pass through a plain DataFrame
df = to_dataframe(ds_or_df)

# Resolve column name bifurcation
ds = rename_entity_col(ds, "country")

# Decorate legacy functions to accept Dataset without changes
@accepts_dataset
def run_robustness_suite(df: pd.DataFrame) -> dict:
    ...   # unchanged — receives a plain DataFrame
```

The `@accepts_dataset` decorator inspects the **first positional argument** only. If it is a `Dataset` subclass, `to_dataframe()` is called and the result is passed instead. All other arguments are forwarded unchanged.

---

## Estimation Layer Integration

`BaseEstimator._resolve_dataframe(data)` is the single Dataset→DataFrame conversion point in the estimation layer:

```python
def _resolve_dataframe(self, data):
    if isinstance(data, PanelDataset):
        return data.to_dataframe()
    if isinstance(data, Dataset):
        return data.dataframe
    return data          # plain DataFrame — pass through
```

Every concrete estimator's `fit()` method calls `data = self._resolve_dataframe(data)` as its first statement. `validate()` methods work without this call because `Dataset` exposes `.columns` and `__getitem__` as pass-throughs, and `_require_columns()` only accesses `data.columns`.

**P0 guarantee:** `to_dataframe()` returns a flat copy identical to the original input. The `dropna()` call inside each estimator's `fit()` therefore sees exactly the same rows it would have seen with a raw DataFrame.

---

## Econometrics Layer Integration

`econflow.econometrics.panel` contains legacy paper-specific estimation functions. Each public function (`run_tfp_model`, `run_growth_model`, `run_robustness_suite`, `run_sensitivity_suite`, `run_falsification_suite`, `run_heterogeneity_suite`) calls `df = _resolve_df(df)` as its first statement.

`_resolve_df` is a module-level shim that wraps the same PanelDataset / Dataset isinstance logic. All internal logic is byte-for-byte unchanged.

---

## Data Layer Integration

### `load_panel_dataset(path, entity_col, time_col)`
New loader in `econflow.data.loaders`. Calls `load_panel()` (unchanged) then wraps the result in `from_dataframe()`. Existing callers of `load_panel()` are unaffected.

### `sample_selection_summary_typed(df, indicator_col, compare_cols)`
New function in `econflow.data.cleaning`. Calls `sample_selection_summary()` (unchanged) and returns `tuple[pd.DataFrame, SelectionSummary]`. The `SelectionSummary` carries the same aggregate counts as the legacy `.attrs` dict, but in a typed dataclass that survives pandas transforms.

### `_get_sel(summary, key)` in `reporting/narrative.py`
Helper that extracts a count from either a legacy `pd.DataFrame` with `.attrs` or a `SelectionSummary`. Enables `write_falsification_results()` to accept either type.

---

## Safety Properties

| Risk | Resolution |
|---|---|
| `.attrs` silently dropped | `SelectionSummary` carries counts in typed fields; `.attrs` still set for legacy callers |
| `dropna()` sample changes | `to_dataframe()` returns flat copy before `dropna()` — no row reordering |
| Column name bifurcation | `rename_entity_col()` is the explicit resolution point; column names in Dataset metadata |
| Circular import | `_resolve_dataframe` uses lazy imports inside the method body |

---

## Files Changed

| File | Change |
|---|---|
| `src/econflow/datasets/` | New package (7 files) |
| `src/econflow/estimation/base.py` | Added `_resolve_dataframe()` |
| `src/econflow/estimation/{ols,fe,re,fd,iv,gmm,quantile}.py` | Added `data = self._resolve_dataframe(data)` in `fit()` |
| `src/econflow/econometrics/panel.py` | Added `_resolve_df()` shim; injected at 6 public function entry points |
| `src/econflow/data/loaders.py` | Added `load_panel_dataset()` |
| `src/econflow/data/cleaning.py` | Added `sample_selection_summary_typed()` |
| `src/econflow/reporting/narrative.py` | Added `_get_sel()`; updated `write_falsification_results()` signature |
| `tests/unit/test_datasets.py` | 75 new tests |
