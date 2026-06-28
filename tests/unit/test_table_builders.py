"""
Unit tests for outputs.tables — regression and summary_stats builders.

regression.py (full implementation):
- Correct coefficient / SE / stars formatting
- Column labels, variable ordering, variable labels
- Footer stats (N, R², estimator, FE indicators)
- Empty results raises ValueError
- Mismatched column_labels length raises ValueError

summary_stats.py (full implementation):
- Standard columns (N, Mean, Std Dev, Min, P25, P50, P75, Max)
- Custom percentiles
- Toggle individual stat columns
- Numeric-only columns selected by default
- variable_labels mapping
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from econflow.outputs.model import ReportTable
from econflow.outputs.tables import build_regression_table, build_summary_stats_table

# ---------------------------------------------------------------------------
# Fixtures — minimal EstimationResult-like objects
# ---------------------------------------------------------------------------

def _make_result(
    params: dict,
    pvalues: dict,
    std_err: dict,
    nobs: int = 100,
    rsquared: float = 0.72,
    estimator_id: str = "ols",
    estimator_name: str = "Pooled OLS",
    extra: dict | None = None,
):
    """Create a minimal EstimationResult stand-in using pandas Series."""
    from unittest.mock import MagicMock
    r = MagicMock()
    r.params = pd.Series(params)
    r.pvalues = pd.Series(pvalues)
    r.std_err = pd.Series(std_err)
    r.nobs = nobs
    r.rsquared = rsquared
    r.f_statistic = None
    r.estimator_id = estimator_id
    r.estimator_name = estimator_name
    r.extra = extra or {}
    return r


@pytest.fixture()
def two_results():
    r1 = _make_result(
        params={"x1": 0.543, "x2": -0.234},
        pvalues={"x1": 0.005, "x2": 0.06},
        std_err={"x1": 0.123, "x2": 0.145},
        nobs=150, rsquared=0.72,
        estimator_name="Pooled OLS",
        extra={"entity_effects": False, "time_effects": False},
    )
    r2 = _make_result(
        params={"x1": 0.501, "x2": -0.189},
        pvalues={"x1": 0.02, "x2": 0.15},
        std_err={"x1": 0.215, "x2": 0.133},
        nobs=150, rsquared=0.68,
        estimator_name="Entity FE",
        extra={"entity_effects": True, "time_effects": False},
    )
    return [r1, r2]


# ---------------------------------------------------------------------------
# build_regression_table
# ---------------------------------------------------------------------------

class TestRegressionTableBuilder:
    def test_returns_report_table(self, two_results):
        t = build_regression_table(two_results)
        assert isinstance(t, ReportTable)
        assert t.table_type == "regression"

    def test_default_column_labels(self, two_results):
        t = build_regression_table(two_results)
        assert "(1)" in t.columns
        assert "(2)" in t.columns

    def test_custom_column_labels(self, two_results):
        t = build_regression_table(two_results, column_labels=["OLS", "FE"])
        assert "OLS" in t.columns
        assert "FE" in t.columns

    def test_coefficient_formatted(self, two_results):
        t = build_regression_table(two_results)
        x1_row = next(r for r in t.rows if r.label == "x1")
        assert "0.543" in x1_row.cells["(1)"]

    def test_triple_star_on_p001(self, two_results):
        t = build_regression_table(two_results)
        x1_row = next(r for r in t.rows if r.label == "x1")
        assert "***" in x1_row.cells["(1)"]

    def test_double_star_on_p02(self, two_results):
        t = build_regression_table(two_results)
        x1_row = next(r for r in t.rows if r.label == "x1")
        assert "**" in x1_row.cells["(2)"]

    def test_single_star_on_p06(self, two_results):
        t = build_regression_table(two_results)
        x2_row = next(r for r in t.rows if r.label == "x2")
        assert "*" in x2_row.cells["(1)"]

    def test_se_in_sub_cells(self, two_results):
        t = build_regression_table(two_results)
        x1_row = next(r for r in t.rows if r.label == "x1")
        assert x1_row.sub_cells is not None
        assert "0.123" in x1_row.sub_cells["(1)"]

    def test_nobs_footer_row(self, two_results):
        t = build_regression_table(two_results)
        nobs_row = next((r for r in t.rows if r.label == "Observations"), None)
        assert nobs_row is not None
        assert nobs_row.cells["(1)"] == "150"

    def test_rsquared_footer_row(self, two_results):
        t = build_regression_table(two_results)
        r2_row = next((r for r in t.rows if r.label == "R²"), None)
        assert r2_row is not None
        assert "0.72" in r2_row.cells["(1)"]

    def test_estimator_footer_row(self, two_results):
        t = build_regression_table(two_results)
        est_row = next((r for r in t.rows if r.label == "Estimator"), None)
        assert est_row is not None
        assert est_row.cells["(1)"] == "Pooled OLS"

    def test_entity_fe_row(self, two_results):
        t = build_regression_table(two_results)
        fe_row = next((r for r in t.rows if r.label == "Entity FE"), None)
        assert fe_row is not None
        assert fe_row.cells["(1)"] == "No"
        assert fe_row.cells["(2)"] == "Yes"

    def test_separator_present(self, two_results):
        t = build_regression_table(two_results)
        seps = [r for r in t.rows if r.row_type == "separator"]
        assert len(seps) >= 1

    def test_variable_labels_applied(self, two_results):
        t = build_regression_table(
            two_results,
            variable_labels={"x1": "AI Index", "x2": "Capital"},
        )
        labels = [r.label for r in t.rows if r.row_type == "data"]
        assert "AI Index" in labels
        assert "Capital" in labels

    def test_variable_order(self, two_results):
        t = build_regression_table(two_results, variable_order=["x2", "x1"])
        data_rows = [r for r in t.rows if r.row_type == "data"]
        assert data_rows[0].label == "x2"
        assert data_rows[1].label == "x1"

    def test_footer_note_contains_stars(self, two_results):
        t = build_regression_table(two_results)
        combined = " ".join(t.footer)
        assert "***" in combined or "p<" in combined

    def test_empty_results_raises(self):
        with pytest.raises(ValueError, match="at least one"):
            build_regression_table([])

    def test_mismatched_column_labels_raises(self, two_results):
        with pytest.raises(ValueError, match="column_labels length"):
            build_regression_table(two_results, column_labels=["Only One"])

    def test_custom_title(self, two_results):
        t = build_regression_table(two_results, title="My Table")
        assert t.title == "My Table"

    def test_single_result(self):
        r = _make_result(
            params={"x1": 1.0},
            pvalues={"x1": 0.001},
            std_err={"x1": 0.1},
        )
        t = build_regression_table([r])
        assert len(t.columns) == 1
        assert t.columns[0] == "(1)"

    def test_missing_variable_in_second_model(self):
        r1 = _make_result(
            params={"x1": 0.5, "x2": 0.3},
            pvalues={"x1": 0.01, "x2": 0.05},
            std_err={"x1": 0.1, "x2": 0.1},
        )
        r2 = _make_result(
            params={"x1": 0.4},
            pvalues={"x1": 0.02},
            std_err={"x1": 0.12},
        )
        t = build_regression_table([r1, r2])
        x2_row = next(r for r in t.rows if r.label == "x2")
        assert x2_row.cells["(2)"] == ""


# ---------------------------------------------------------------------------
# build_summary_stats_table
# ---------------------------------------------------------------------------

@pytest.fixture()
def sample_df():
    rng = np.random.default_rng(42)
    return pd.DataFrame({
        "y": rng.normal(3, 1, 100),
        "x1": rng.normal(0, 1, 100),
        "x2": rng.uniform(0, 10, 100),
        "group": rng.integers(0, 2, 100),   # integer but numeric
        "label": ["a"] * 100,               # non-numeric → should be excluded
    })


class TestSummaryStatsBuilder:
    def test_returns_report_table(self, sample_df):
        t = build_summary_stats_table(sample_df)
        assert isinstance(t, ReportTable)
        assert t.table_type == "summary_stats"

    def test_excludes_non_numeric(self, sample_df):
        t = build_summary_stats_table(sample_df)
        labels = [r.label for r in t.rows]
        assert "label" not in labels

    def test_includes_numeric_columns(self, sample_df):
        t = build_summary_stats_table(sample_df)
        labels = [r.label for r in t.rows]
        assert "y" in labels
        assert "x1" in labels

    def test_default_stat_columns(self, sample_df):
        t = build_summary_stats_table(sample_df)
        assert "N" in t.columns
        assert "Mean" in t.columns
        assert "Std Dev" in t.columns
        assert "Min" in t.columns
        assert "Max" in t.columns

    def test_default_percentiles(self, sample_df):
        t = build_summary_stats_table(sample_df)
        assert "P25" in t.columns
        assert "P50" in t.columns
        assert "P75" in t.columns

    def test_nobs_is_100(self, sample_df):
        t = build_summary_stats_table(sample_df)
        y_row = next(r for r in t.rows if r.label == "y")
        assert y_row.cells["N"] == "100"

    def test_custom_percentiles(self, sample_df):
        t = build_summary_stats_table(sample_df, percentiles=(0.10, 0.90))
        assert "P10" in t.columns
        assert "P90" in t.columns
        assert "P25" not in t.columns

    def test_variable_subset(self, sample_df):
        t = build_summary_stats_table(sample_df, variables=["y", "x1"])
        labels = [r.label for r in t.rows]
        assert labels == ["y", "x1"]

    def test_variable_labels(self, sample_df):
        t = build_summary_stats_table(
            sample_df,
            variables=["y"],
            variable_labels={"y": "Output"},
        )
        assert t.rows[0].label == "Output"

    def test_toggle_nobs_off(self, sample_df):
        t = build_summary_stats_table(sample_df, include_nobs=False)
        assert "N" not in t.columns

    def test_toggle_std_off(self, sample_df):
        t = build_summary_stats_table(sample_df, include_std=False)
        assert "Std Dev" not in t.columns

    def test_custom_title(self, sample_df):
        t = build_summary_stats_table(sample_df, title="Panel A")
        assert t.title == "Panel A"

    def test_mean_value_reasonable(self, sample_df):
        t = build_summary_stats_table(sample_df, variables=["y"])
        y_row = next(r for r in t.rows if r.label == "y")
        mean_val = float(y_row.cells["Mean"])
        # RNG seed 42 → mean close to 3
        assert 2.5 < mean_val < 3.5
