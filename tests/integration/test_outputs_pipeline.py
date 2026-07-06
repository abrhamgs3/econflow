"""
Integration tests for the full Sprint 6 outputs pipeline.

Tests verify the end-to-end flow:
  EstimationResult → TableBuilder → Renderer → file

And:
  DiagnosticResult → DiagnosticsReport → Renderer → file

And:
  PublicationBundle → write() → directory structure + manifest.json

All tests use real EstimationResult objects produced by running actual
estimators on synthetic panel data.
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest

from econflow.estimation import EntityFE, PooledOLS, TwoWayFE
from econflow.outputs import (
    CoefficientPlot,
    PublicationBundle,
    build_diagnostics_report,
    build_regression_table,
    build_summary_stats_table,
    get_renderer,
)
from econflow.outputs.model import ReportTable

# ---------------------------------------------------------------------------
# Fixtures — synthetic panel data
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def panel_data() -> pd.DataFrame:
    rng = np.random.default_rng(0)
    n_entities, n_periods = 30, 5
    entities = np.repeat(np.arange(n_entities), n_periods)
    times = np.tile(np.arange(n_periods), n_entities)
    x1 = rng.normal(0, 1, n_entities * n_periods)
    x2 = rng.normal(1, 0.5, n_entities * n_periods)
    fe = np.repeat(rng.normal(0, 1, n_entities), n_periods)
    y = 0.5 * x1 - 0.3 * x2 + fe + rng.normal(0, 0.3, n_entities * n_periods)
    return pd.DataFrame({"entity": entities, "time": times, "y": y, "x1": x1, "x2": x2})


_PARAMS = {
    "dependent": "y",
    "regressors": ["x1", "x2"],
    "entity_col": "entity",
    "time_col": "time",
}


@pytest.fixture(scope="module")
def ols_result(panel_data):
    return PooledOLS(_PARAMS).fit(panel_data)


@pytest.fixture(scope="module")
def fe_result(panel_data):
    return EntityFE(_PARAMS).fit(panel_data)


@pytest.fixture(scope="module")
def twfe_result(panel_data):
    return TwoWayFE(_PARAMS).fit(panel_data)


# ---------------------------------------------------------------------------
# Regression table — full pipeline
# ---------------------------------------------------------------------------

class TestRegressionTablePipeline:
    def test_build_from_real_results(self, ols_result, fe_result):
        t = build_regression_table([ols_result, fe_result])
        assert isinstance(t, ReportTable)
        assert len(t.columns) == 2

    def test_x1_coefficient_present(self, ols_result, fe_result):
        t = build_regression_table([ols_result, fe_result])
        data_labels = [r.label for r in t.rows if r.row_type == "data"]
        assert "x1" in data_labels

    def test_coefficient_value_positive(self, ols_result):
        """OLS estimate for x1 should be close to 0.5 (true DGP value)."""
        t = build_regression_table([ols_result])
        x1_row = next(r for r in t.rows if r.label == "x1")
        coef_str = x1_row.cells["(1)"].replace("*", "").strip()
        assert float(coef_str) > 0

    def test_rendered_to_latex(self, ols_result, fe_result):
        t = build_regression_table([ols_result, fe_result])
        tex = get_renderer("latex")().render(t)
        assert r"\toprule" in tex
        assert "x1" in tex

    def test_rendered_to_markdown(self, ols_result, fe_result):
        t = build_regression_table([ols_result, fe_result])
        md = get_renderer("markdown")().render(t)
        assert "|" in md
        assert "x1" in md

    def test_rendered_to_html(self, ols_result, fe_result):
        t = build_regression_table([ols_result, fe_result])
        html = get_renderer("html")().render(t)
        assert "<table" in html.lower()

    def test_three_columns(self, ols_result, fe_result, twfe_result):
        t = build_regression_table([ols_result, fe_result, twfe_result])
        assert len(t.columns) == 3


# ---------------------------------------------------------------------------
# Summary stats — full pipeline
# ---------------------------------------------------------------------------

class TestSummaryStatsPipeline:
    def test_build_from_panel_data(self, panel_data):
        t = build_summary_stats_table(panel_data, variables=["y", "x1", "x2"])
        assert isinstance(t, ReportTable)
        assert len(t.rows) == 3

    def test_n_equals_150(self, panel_data):
        t = build_summary_stats_table(panel_data, variables=["y"])
        assert t.rows[0].cells["N"] == "150"

    def test_rendered_to_csv(self, panel_data):
        t = build_summary_stats_table(panel_data, variables=["y", "x1"])
        csv = get_renderer("csv")().render(t)
        assert "Mean" in csv
        assert "y" in csv


# ---------------------------------------------------------------------------
# Diagnostics report — full pipeline
# ---------------------------------------------------------------------------

class TestDiagnosticsReportPipeline:
    def test_build_empty(self):
        t = build_diagnostics_report([])
        assert isinstance(t, ReportTable)
        assert t.rows == []

    def test_build_from_diagnostic_results(self, ols_result):
        import econflow.diagnostics.plugins  # noqa: F401
        from econflow.diagnostics import get_diagnostic
        bp = get_diagnostic("breusch_pagan")()
        diag_results = [bp.run(ols_result)]
        t = build_diagnostics_report(diag_results)
        assert isinstance(t, ReportTable)
        assert len(t.rows) >= 1

    def test_columns_correct(self, ols_result):
        import econflow.diagnostics.plugins  # noqa: F401
        from econflow.diagnostics import get_diagnostic
        bp = get_diagnostic("breusch_pagan")()
        dr = bp.run(ols_result)
        t = build_diagnostics_report([dr])
        assert "Estimator" in t.columns
        assert "p-value" in t.columns
        assert "Conclusion" in t.columns

    def test_rendered_to_markdown(self, ols_result):
        import econflow.diagnostics.plugins  # noqa: F401
        from econflow.diagnostics import get_diagnostic
        bp = get_diagnostic("breusch_pagan")()
        dr = bp.run(ols_result)
        t = build_diagnostics_report([dr])
        md = get_renderer("markdown")().render(t)
        assert "|" in md


# ---------------------------------------------------------------------------
# CoefficientPlot — integration
# ---------------------------------------------------------------------------

class TestCoefficientPlotIntegration:
    def test_build_from_real_result(self, fe_result):
        from econflow.outputs.model import ReportFigure
        fig = CoefficientPlot().build(result=fe_result)
        assert isinstance(fig, ReportFigure)
        assert "x1" in fig.data["variables"]

    def test_ci_width_positive(self, fe_result):
        fig = CoefficientPlot().build(result=fe_result)
        for lo, hi in zip(fig.data["ci_lower"], fig.data["ci_upper"]):
            if lo is not None and hi is not None:
                assert hi > lo

    def test_to_json_valid(self, fe_result):
        fig = CoefficientPlot().build(result=fe_result)
        data = json.loads(fig.to_json())
        assert "coefficients" in data["data"]


# ---------------------------------------------------------------------------
# PublicationBundle — integration
# ---------------------------------------------------------------------------

class TestPublicationBundleIntegration:
    def test_write_empty_bundle(self, tmp_path):
        bundle = PublicationBundle(tmp_path / "bundle")
        manifest = bundle.write()
        assert manifest["tables"] == []
        assert manifest["figures"] == []
        assert (tmp_path / "bundle" / "manifest.json").exists()

    def test_manifest_json_valid(self, tmp_path):
        bundle = PublicationBundle(tmp_path / "bundle2")
        bundle.write()
        data = json.loads((tmp_path / "bundle2" / "manifest.json").read_text())
        assert data["econflow_bundle"] is True
        assert "created_utc" in data

    def test_table_written_all_formats(self, tmp_path, ols_result):
        t = build_regression_table([ols_result], title="OLS Results")
        bundle = PublicationBundle(
            tmp_path / "bundle3",
            table_formats=["csv", "latex", "markdown", "html"],
        )
        bundle.add_table(t)
        manifest = bundle.write()
        assert len(manifest["tables"]) == 1
        files = manifest["tables"][0]["files"]
        assert "csv" in files
        assert "latex" in files
        (tmp_path / "bundle3" / files["csv"]).exists()

    def test_table_csv_readable(self, tmp_path, ols_result):
        t = build_regression_table([ols_result])
        bundle = PublicationBundle(tmp_path / "bundle4", table_formats=["csv"])
        bundle.add_table(t, slug="regression")
        bundle.write()
        csv_path = tmp_path / "bundle4" / "tables" / "regression.csv"
        assert csv_path.exists()
        content = csv_path.read_text()
        assert "x1" in content

    def test_figure_written_as_json(self, tmp_path, fe_result):
        fig = CoefficientPlot().build(result=fe_result)
        bundle = PublicationBundle(tmp_path / "bundle5", table_formats=["csv"])
        bundle.add_figure(fig, slug="coef_plot")
        bundle.write()
        fig_path = tmp_path / "bundle5" / "figures" / "coef_plot.json"
        assert fig_path.exists()
        data = json.loads(fig_path.read_text())
        assert "coefficients" in data["data"]

    def test_diagnostics_written(self, tmp_path, ols_result):
        import econflow.diagnostics.plugins  # noqa: F401
        from econflow.diagnostics import get_diagnostic
        bp = get_diagnostic("breusch_pagan")()
        diag_table = build_diagnostics_report([bp.run(ols_result)])
        bundle = PublicationBundle(tmp_path / "bundle6", table_formats=["csv"])
        bundle.set_diagnostics(diag_table)
        manifest = bundle.write()
        assert manifest["diagnostics"] is not None
        assert "markdown" in manifest["diagnostics"]["files"]

    def test_chaining_api(self, tmp_path, ols_result, fe_result):
        t = build_regression_table([ols_result, fe_result])
        fig = CoefficientPlot().build(result=fe_result)
        bundle = (
            PublicationBundle(tmp_path / "bundle7", table_formats=["csv"])
            .add_table(t)
            .add_figure(fig)
        )
        manifest = bundle.write()
        assert len(manifest["tables"]) == 1
        assert len(manifest["figures"]) == 1

    def test_no_overwrite_raises(self, tmp_path):
        bundle = PublicationBundle(tmp_path / "bundle8", overwrite=False)
        bundle.write()  # first write OK
        with pytest.raises(FileExistsError):
            bundle2 = PublicationBundle(tmp_path / "bundle8", overwrite=False)
            bundle2.write()

    def test_manifest_table_slug(self, tmp_path, ols_result):
        t = build_regression_table([ols_result], title="Main Results")
        bundle = PublicationBundle(tmp_path / "bundle9", table_formats=["csv"])
        bundle.add_table(t, slug="main_results")
        manifest = bundle.write()
        assert manifest["tables"][0]["slug"] == "main_results"
