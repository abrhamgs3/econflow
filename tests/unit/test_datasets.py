"""
tests/unit/test_datasets.py — Unit tests for the Dataset abstraction layer.

Covers:
- Value types (DatasetMetadata, ProvenanceRecord, VariableRegistry, etc.)
- Dataset abstract base (pandas pass-through, column access)
- PanelDataset (balance, validation, to_multiindex_dataframe, rename_entity_col)
- CrossSectionDataset, TimeSeriesDataset, SpatialDataset
- Migration utilities (from_dataframe, to_dataframe, accepts_dataset, rename_entity_col)
- BaseEstimator._resolve_dataframe
- Data layer additions (load_panel_dataset signature, sample_selection_summary_typed)
"""

from __future__ import annotations

import pandas as pd
import pytest

from econflow.datasets import (
    CrossSectionDataset,
    Dataset,
    PanelDataset,
    SpatialDataset,
    TimeSeriesDataset,
    accepts_dataset,
    from_dataframe,
    rename_entity_col,
    to_dataframe,
)
from econflow.datasets.types import (
    ColumnInfo,
    DatasetMetadata,
    MissingnessSummary,
    PanelBalance,
    ProvenanceRecord,
    SelectionSummary,
    ValidationStatus,
    VariableRegistry,
    VALID_ROLES,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def panel_df() -> pd.DataFrame:
    return pd.DataFrame({
        "country": ["A", "A", "A", "B", "B", "B"],
        "year":    [2000, 2001, 2002, 2000, 2001, 2002],
        "gdp":     [1.0, 1.1, 1.2, 2.0, 2.1, None],
        "ai":      [0.1, 0.2, 0.3, 0.4, None, 0.6],
    })


@pytest.fixture()
def panel_ds(panel_df) -> PanelDataset:
    return PanelDataset(panel_df, entity_col="country", time_col="year")


@pytest.fixture()
def cross_df() -> pd.DataFrame:
    return pd.DataFrame({
        "country": ["A", "B", "C"],
        "gdp":     [1.0, 2.0, 3.0],
    })


@pytest.fixture()
def ts_df() -> pd.DataFrame:
    return pd.DataFrame({
        "year": [2000, 2001, 2002],
        "index": [0.1, 0.2, 0.3],
    })


# ===========================================================================
# Value types
# ===========================================================================

class TestDatasetMetadata:
    def test_defaults(self):
        m = DatasetMetadata()
        assert m.title == ""
        assert m.description == ""
        assert m.source == ""
        assert isinstance(m.tags, list)

    def test_fields(self):
        m = DatasetMetadata(title="Test", source="WB", tags=["panel"])
        assert m.title == "Test"
        assert "panel" in m.tags


class TestProvenanceRecord:
    def test_add_transformation_returns_new(self):
        pr = ProvenanceRecord(origin="csv")
        pr2 = pr.add_transformation("merge with WB data")
        assert pr is not pr2
        assert "merge with WB data" in pr2.transformations
        assert len(pr.transformations) == 0  # original unchanged

    def test_defaults(self):
        pr = ProvenanceRecord()
        assert pr.origin == "unknown"
        assert pr.input_paths == []
        assert pr.transformations == []


class TestVariableRegistry:
    def test_names_and_by_role(self):
        reg = VariableRegistry(columns={
            "country": ColumnInfo(name="country", dtype="object", role="entity"),
            "year":    ColumnInfo(name="year",    dtype="int64",  role="time"),
            "gdp":     ColumnInfo(name="gdp",     dtype="float64", role="outcome"),
        })
        assert "country" in reg.names()
        entities = reg.by_role("entity")
        assert len(entities) == 1
        assert entities[0].name == "country"

    def test_assign_role(self):
        reg = VariableRegistry(columns={
            "x": ColumnInfo(name="x", dtype="float64", role="unknown"),
        })
        reg.assign_role("x", "regressor")
        assert reg.columns["x"].role == "regressor"

    def test_assign_invalid_role(self):
        reg = VariableRegistry(columns={
            "x": ColumnInfo(name="x", dtype="float64"),
        })
        with pytest.raises(ValueError, match="Invalid role"):
            reg.assign_role("x", "nonsense")


class TestMissingnessSummary:
    def test_pct_missing(self):
        ms = MissingnessSummary(by_column={"a": 1, "b": 0}, total_cells=20, total_missing=1)
        assert ms.pct_missing == pytest.approx(0.05)

    def test_complete_and_incomplete(self):
        ms = MissingnessSummary(by_column={"a": 0, "b": 2}, total_cells=10, total_missing=2)
        assert "a" in ms.complete_columns
        assert "b" in ms.incomplete_columns

    def test_to_series(self):
        ms = MissingnessSummary(by_column={"a": 3}, total_cells=10, total_missing=3)
        s = ms.to_series()
        assert isinstance(s, pd.Series)
        assert s["a"] == 3


class TestSelectionSummary:
    def test_from_legacy_dataframe(self):
        df = pd.DataFrame({"variable": ["x"]})
        df.attrs["in_sample_rows"] = 100
        df.attrs["out_of_sample_rows"] = 50
        df.attrs["in_sample_countries"] = 20
        df.attrs["out_of_sample_countries"] = 10
        sel = SelectionSummary.from_legacy_dataframe(df)
        assert sel.in_sample_rows == 100
        assert sel.out_of_sample_rows == 50
        assert sel.in_sample_countries == 20

    def test_defaults(self):
        sel = SelectionSummary(
            in_sample_rows=5, out_of_sample_rows=3,
            in_sample_countries=2, out_of_sample_countries=1,
        )
        assert isinstance(sel.comparison_frame, pd.DataFrame)


# ===========================================================================
# Dataset abstract base (via PanelDataset)
# ===========================================================================

class TestDatasetBase:
    def test_copy_on_init(self, panel_df, panel_ds):
        """Internal DataFrame is a copy — mutations don't propagate."""
        original_len = len(panel_df)
        panel_df.drop(panel_df.index[0], inplace=True)
        assert len(panel_ds) == original_len  # unaffected

    def test_dataframe_returns_copy(self, panel_ds):
        df1 = panel_ds.dataframe
        df1["__junk__"] = 99
        df2 = panel_ds.dataframe
        assert "__junk__" not in df2.columns

    def test_columns_property(self, panel_ds):
        cols = panel_ds.columns
        assert isinstance(cols, list)
        assert "country" in cols

    def test_shape(self, panel_ds):
        r, c = panel_ds.shape
        assert r == 6
        assert c == 4

    def test_len(self, panel_ds):
        assert len(panel_ds) == 6

    def test_contains(self, panel_ds):
        assert "gdp" in panel_ds
        assert "__missing__" not in panel_ds

    def test_getitem_series(self, panel_ds):
        s = panel_ds["gdp"]
        assert isinstance(s, pd.Series)

    def test_getitem_frame(self, panel_ds):
        sub = panel_ds[["gdp", "ai"]]
        assert isinstance(sub, pd.DataFrame)

    def test_groupby(self, panel_ds):
        g = panel_ds.groupby("country")
        assert len(g) == 2

    def test_requires_dataframe(self):
        with pytest.raises(TypeError):
            PanelDataset("not a dataframe")

    def test_metadata_default(self, panel_ds):
        assert isinstance(panel_ds.metadata, DatasetMetadata)

    def test_provenance_default(self, panel_ds):
        assert isinstance(panel_ds.provenance, ProvenanceRecord)


# ===========================================================================
# PanelDataset
# ===========================================================================

class TestPanelDataset:
    def test_entity_time_identifiers(self, panel_ds):
        assert panel_ds.entity_identifier == "country"
        assert panel_ds.time_identifier == "year"

    def test_to_dataframe_flat(self, panel_ds):
        df = panel_ds.to_dataframe()
        assert isinstance(df, pd.DataFrame)
        assert "country" in df.columns
        assert "year" in df.columns

    def test_to_multiindex_dataframe(self, panel_ds):
        mi = panel_ds.to_multiindex_dataframe()
        assert mi.index.names == ["country", "year"]
        assert mi.index.is_monotonic_increasing

    def test_to_multiindex_custom_cols(self, panel_df):
        df = panel_df.rename(columns={"country": "iso3"})
        ds = PanelDataset(df, entity_col="iso3", time_col="year")
        mi = ds.to_multiindex_dataframe(entity_col="iso3", time_col="year")
        assert mi.index.names == ["iso3", "year"]

    def test_accepts_multiindex_input(self, panel_df):
        """PanelDataset must accept a MultiIndex DataFrame and flatten it."""
        mi_df = panel_df.set_index(["country", "year"])
        ds = PanelDataset(mi_df, entity_col="country", time_col="year")
        assert "country" in ds.columns

    def test_panel_balance(self, panel_ds):
        bal = panel_ds.panel_balance
        assert isinstance(bal, PanelBalance)
        assert bal.n_entities == 2
        assert bal.n_periods == 3
        assert bal.total_obs == 6
        assert bal.expected_obs == 6  # 2 × 3
        assert bal.balance_ratio == pytest.approx(1.0)
        assert bal.is_balanced is True

    def test_panel_balance_unbalanced(self):
        df = pd.DataFrame({
            "country": ["A", "A", "B"],
            "year":    [2000, 2001, 2000],
            "y":       [1.0, 2.0, 3.0],
        })
        ds = PanelDataset(df, entity_col="country", time_col="year")
        bal = ds.panel_balance
        assert bal.is_balanced is False
        assert bal.balance_ratio < 1.0

    def test_missingness_summary(self, panel_ds):
        ms = panel_ds.missingness_summary
        assert isinstance(ms, MissingnessSummary)
        assert ms.by_column["gdp"] == 1
        assert ms.by_column["ai"] == 1

    def test_validation_status_valid(self, panel_ds):
        vs = panel_ds.validation_status
        assert isinstance(vs, ValidationStatus)
        assert vs.is_valid

    def test_validation_status_missing_entity_col(self):
        df = pd.DataFrame({"year": [2000, 2001], "y": [1.0, 2.0]})
        ds = PanelDataset(df, entity_col="country", time_col="year")
        vs = ds.validation_status
        assert not vs.is_valid
        assert any("country" in e for e in vs.errors)

    def test_validation_duplicate_entity_time(self):
        df = pd.DataFrame({
            "country": ["A", "A"],
            "year":    [2000, 2000],
            "y":       [1.0, 2.0],
        })
        ds = PanelDataset(df, entity_col="country", time_col="year")
        vs = ds.validation_status
        assert not vs.is_valid

    def test_rename_entity_col(self, panel_ds):
        ds2 = panel_ds.rename_entity_col("iso3")
        assert ds2.entity_identifier == "iso3"
        assert "iso3" in ds2.columns
        assert "country" not in ds2.columns
        # Original unaffected
        assert panel_ds.entity_identifier == "country"

    def test_copy(self, panel_ds):
        ds2 = panel_ds.copy()
        assert isinstance(ds2, PanelDataset)
        assert ds2 is not panel_ds

    def test_variable_registry_roles(self, panel_ds):
        reg = panel_ds.variable_registry
        assert reg.columns["country"].role == "entity"
        assert reg.columns["year"].role == "time"

    def test_repr(self, panel_ds):
        r = repr(panel_ds)
        assert "PanelDataset" in r


# ===========================================================================
# CrossSectionDataset
# ===========================================================================

class TestCrossSectionDataset:
    def test_basic(self, cross_df):
        ds = CrossSectionDataset(cross_df, entity_col="country")
        assert ds.entity_identifier == "country"
        assert ds.time_identifier is None
        assert ds.panel_balance is None

    def test_validation_valid(self, cross_df):
        ds = CrossSectionDataset(cross_df, entity_col="country")
        assert ds.validation_status.is_valid

    def test_validation_duplicate_entity(self):
        df = pd.DataFrame({"country": ["A", "A"], "y": [1.0, 2.0]})
        ds = CrossSectionDataset(df, entity_col="country")
        assert not ds.validation_status.is_valid

    def test_validation_missing_entity_col(self, cross_df):
        ds = CrossSectionDataset(cross_df, entity_col="iso3")
        assert not ds.validation_status.is_valid

    def test_repr(self, cross_df):
        ds = CrossSectionDataset(cross_df, entity_col="country")
        assert "CrossSectionDataset" in repr(ds)


# ===========================================================================
# TimeSeriesDataset
# ===========================================================================

class TestTimeSeriesDataset:
    def test_basic(self, ts_df):
        ds = TimeSeriesDataset(ts_df, time_col="year")
        assert ds.entity_identifier is None
        assert ds.time_identifier == "year"
        assert ds.panel_balance is None

    def test_validation_valid(self, ts_df):
        ds = TimeSeriesDataset(ts_df, time_col="year")
        assert ds.validation_status.is_valid

    def test_validation_duplicate_time(self):
        df = pd.DataFrame({"year": [2000, 2000], "x": [1.0, 2.0]})
        ds = TimeSeriesDataset(df, time_col="year")
        assert not ds.validation_status.is_valid

    def test_repr(self, ts_df):
        ds = TimeSeriesDataset(ts_df, time_col="year")
        assert "TimeSeriesDataset" in repr(ds)


# ===========================================================================
# SpatialDataset
# ===========================================================================

class TestSpatialDataset:
    @pytest.fixture()
    def spatial_df(self):
        return pd.DataFrame({
            "country": ["A", "B"],
            "lat":     [10.0, 20.0],
            "lon":     [30.0, 40.0],
        })

    def test_basic(self, spatial_df):
        ds = SpatialDataset(spatial_df, entity_col="country")
        assert ds.entity_identifier == "country"
        assert ds.latitude_col == "lat"
        assert ds.longitude_col == "lon"

    def test_spatial_methods_raise(self, spatial_df):
        ds = SpatialDataset(spatial_df)
        with pytest.raises(NotImplementedError):
            ds.distance_matrix()
        with pytest.raises(NotImplementedError):
            ds.spatial_weights()
        with pytest.raises(NotImplementedError):
            ds.morans_i("lat")

    def test_validation_missing_lat(self, spatial_df):
        ds = SpatialDataset(spatial_df.drop(columns=["lat"]))
        assert not ds.validation_status.is_valid

    def test_repr(self, spatial_df):
        ds = SpatialDataset(spatial_df)
        assert "SpatialDataset" in repr(ds)


# ===========================================================================
# Migration utilities
# ===========================================================================

class TestMigrationFromDataframe:
    def test_returns_panel_dataset(self, panel_df):
        ds = from_dataframe(panel_df, entity_col="country", time_col="year")
        assert isinstance(ds, PanelDataset)

    def test_metadata_stored(self, panel_df):
        ds = from_dataframe(panel_df, title="My Panel", source="WB")
        assert ds.metadata.title == "My Panel"
        assert ds.metadata.source == "WB"

    def test_provenance_origin(self, panel_df):
        ds = from_dataframe(panel_df, origin="test_origin")
        assert ds.provenance.origin == "test_origin"


class TestMigrationToDataframe:
    def test_passthrough_dataframe(self, panel_df):
        result = to_dataframe(panel_df)
        assert isinstance(result, pd.DataFrame)
        assert result.equals(panel_df)
        assert result is not panel_df  # always a copy

    def test_from_panel_dataset(self, panel_ds):
        df = to_dataframe(panel_ds)
        assert isinstance(df, pd.DataFrame)
        assert "country" in df.columns

    def test_from_cross_section(self, cross_df):
        ds = CrossSectionDataset(cross_df)
        df = to_dataframe(ds)
        assert isinstance(df, pd.DataFrame)

    def test_raises_on_invalid_type(self):
        with pytest.raises(TypeError):
            to_dataframe("not a dataframe")


class TestMigrationRenameEntityCol:
    def test_renames(self, panel_ds):
        ds2 = rename_entity_col(panel_ds, "iso3")
        assert ds2.entity_identifier == "iso3"
        assert "iso3" in ds2.dataframe.columns


class TestAcceptsDatasetDecorator:
    def test_passthrough_dataframe(self, panel_df):
        @accepts_dataset
        def fn(df):
            return df

        result = fn(panel_df)
        assert isinstance(result, pd.DataFrame)

    def test_unwraps_panel_dataset(self, panel_ds):
        @accepts_dataset
        def fn(df):
            assert isinstance(df, pd.DataFrame), f"expected DataFrame got {type(df)}"
            return df

        result = fn(panel_ds)
        assert isinstance(result, pd.DataFrame)

    def test_kwargs_forwarded(self, panel_df):
        @accepts_dataset
        def fn(df, multiplier=2):
            return len(df) * multiplier

        assert fn(panel_df, multiplier=3) == len(panel_df) * 3


# ===========================================================================
# BaseEstimator._resolve_dataframe
# ===========================================================================

class TestResolveDataframe:
    @pytest.fixture()
    def estimator(self):
        from econflow.estimation.base import BaseEstimator, EstimationResult
        from econflow.estimation.result import DiagnosticResult

        class _Stub(BaseEstimator):
            estimator_id = "stub"
            def validate(self, d): pass
            def fit(self, d): return None
            def diagnostics(self, r): return []

        return _Stub()

    def test_resolves_panel_dataset(self, estimator, panel_ds):
        result = estimator._resolve_dataframe(panel_ds)
        assert isinstance(result, pd.DataFrame)
        assert "country" in result.columns

    def test_passthrough_dataframe(self, estimator, panel_df):
        result = estimator._resolve_dataframe(panel_df)
        assert isinstance(result, pd.DataFrame)
        assert result is panel_df  # plain DataFrame is returned as-is

    def test_resolves_cross_section(self, estimator, cross_df):
        ds = CrossSectionDataset(cross_df, entity_col="country")
        result = estimator._resolve_dataframe(ds)
        assert isinstance(result, pd.DataFrame)


# ===========================================================================
# Data layer additions
# ===========================================================================

class TestLoadPanelDataset:
    def test_function_exists(self):
        from econflow.data.loaders import load_panel_dataset
        import inspect
        sig = inspect.signature(load_panel_dataset)
        assert "path" in sig.parameters
        assert "entity_col" in sig.parameters
        assert "time_col" in sig.parameters

    def test_raises_on_missing_file(self, tmp_path):
        from econflow.data.loaders import load_panel_dataset
        from econflow.exceptions import DataValidationError
        with pytest.raises(DataValidationError):
            load_panel_dataset(tmp_path / "nonexistent.csv")

    def test_returns_panel_dataset(self, tmp_path):
        from econflow.data.loaders import load_panel_dataset
        csv = tmp_path / "panel.csv"
        df = pd.DataFrame({"country": ["A", "B"], "year": [2000, 2000], "y": [1.0, 2.0]})
        df.to_csv(csv, index=False)
        ds = load_panel_dataset(csv)
        assert isinstance(ds, PanelDataset)
        assert ds.entity_identifier == "country"
        assert ds.time_identifier == "year"


class TestSampleSelectionSummaryTyped:
    @pytest.fixture()
    def selection_df(self):
        return pd.DataFrame({
            "country": ["A", "A", "B", "B", "C", "C"],
            "year":    [2000, 2001, 2000, 2001, 2000, 2001],
            "ln_ai":   [1.0,  None, 2.0,  2.1,  None, None],
            "ln_gdp":  [10.0, 10.1, 9.0,  9.1,  8.0,  8.1],
        })

    def test_returns_tuple(self, selection_df):
        from econflow.data.cleaning import sample_selection_summary_typed
        result = sample_selection_summary_typed(selection_df, indicator_col="ln_ai", compare_cols=["ln_gdp"])
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_dataframe_matches_legacy(self, selection_df):
        from econflow.data.cleaning import sample_selection_summary, sample_selection_summary_typed
        legacy_df = sample_selection_summary(selection_df, indicator_col="ln_ai", compare_cols=["ln_gdp"])
        typed_df, sel = sample_selection_summary_typed(selection_df, indicator_col="ln_ai", compare_cols=["ln_gdp"])
        assert typed_df.equals(legacy_df)

    def test_selection_summary_counts(self, selection_df):
        from econflow.data.cleaning import sample_selection_summary_typed
        _, sel = sample_selection_summary_typed(selection_df, indicator_col="ln_ai")
        assert isinstance(sel, SelectionSummary)
        assert sel.in_sample_rows == 3    # A/2000, B/2000, B/2001
        assert sel.out_of_sample_rows == 3
        assert sel.in_sample_countries == 2   # A, B
        assert sel.out_of_sample_countries == 2  # A (2001), C


class TestNarrativeGetSel:
    def test_with_legacy_df(self):
        from econflow.reporting.narrative import _get_sel
        df = pd.DataFrame({"x": [1]})
        df.attrs["in_sample_rows"] = 42
        assert _get_sel(df, "in_sample_rows") == 42
        assert _get_sel(df, "missing_key") == "NA"

    def test_with_selection_summary(self):
        from econflow.reporting.narrative import _get_sel
        sel = SelectionSummary(in_sample_rows=99, out_of_sample_rows=10,
                               in_sample_countries=5, out_of_sample_countries=2)
        assert _get_sel(sel, "in_sample_rows") == 99
        assert _get_sel(sel, "in_sample_countries") == 5

    def test_default_on_missing(self):
        from econflow.reporting.narrative import _get_sel
        sel = SelectionSummary(in_sample_rows=1, out_of_sample_rows=1,
                               in_sample_countries=1, out_of_sample_countries=1)
        assert _get_sel(sel, "nonexistent_field") == "NA"
