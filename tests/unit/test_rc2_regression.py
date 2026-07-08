"""
RC2 regression tests — verifies all pre-release fixes are in place.

Each test class maps to one finding from the RC1 review:

C1 — LaTeX tablenotes replaced with flushleft block
C2 — estimator_id field on DiagnosticResult + run_with_context()
H1 — _conclusion() emits Reject H0 / Fail to reject H0
H2 — PublicationBundle.write() pre-validates renderer IDs
H3 — PublicationBundle.add_table() raises ValueError on duplicate slug
M3 — RendererError exported from econflow.outputs
M4 — ReportTable.from_dict() uses explicit field mapping
"""

from __future__ import annotations

import pandas as pd
import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _diag_result(**kwargs):
    from econflow.estimation.result import DiagnosticResult
    defaults = dict(
        diagnostic_id="test",
        diagnostic_name="Test Diagnostic",
        statistic=5.0,
        pvalue=0.03,
        conclusion="Reject H0: test detected",
        level="warning",
    )
    defaults.update(kwargs)
    return DiagnosticResult(**defaults)


def _estimation_result(estimator_id: str = "fe"):
    from econflow.estimation.result import EstimationResult
    idx = pd.Index(["x1"])
    return EstimationResult(
        estimator_id=estimator_id,
        estimator_name="Fixed Effects",
        params=pd.Series([0.5], index=idx),
        std_err=pd.Series([0.1], index=idx),
        conf_int=pd.DataFrame({"lower": [0.3], "upper": [0.7]}, index=idx),
        pvalues=pd.Series([0.001], index=idx),
        nobs=100,
        ngroups=20,
        df_resid=78,
        rsquared=0.60,
        rsquared_adj=0.58,
    )


def _simple_table(title="Test Table"):
    from econflow.outputs.model import ReportTable, TableRow
    t = ReportTable(
        title=title,
        table_type="regression",
        columns=["(1)"],
        footer=["*** p<0.01"],
        notes="OLS estimates.",
    )
    t.add_row(TableRow(label="x1", cells={"(1)": "0.5***"}))
    return t


# ---------------------------------------------------------------------------
# C1 — LaTeX footer uses threeparttable + tablenotes (Sprint 11B upgrade)
# ---------------------------------------------------------------------------

class TestC1LaTeXFooter:
    def test_tablenotes_in_output(self):
        """Sprint 11B: footer must use threeparttable/tablenotes for journal compliance."""
        from econflow.outputs.registry import get_renderer
        tex = get_renderer("latex")().render(_simple_table())
        assert "tablenotes" in tex

    def test_threeparttable_wraps_footer(self):
        from econflow.outputs.registry import get_renderer
        tex = get_renderer("latex")().render(_simple_table())
        assert r"\begin{threeparttable}" in tex
        assert r"\end{threeparttable}" in tex

    def test_footnotesize_inside_flushleft(self):
        from econflow.outputs.registry import get_renderer
        tex = get_renderer("latex")().render(_simple_table())
        assert r"\footnotesize" in tex

    def test_footer_content_appears(self):
        from econflow.outputs.registry import get_renderer
        tex = get_renderer("latex")().render(_simple_table())
        assert "p<0.01" in tex

    def test_notes_appear_with_textit(self):
        from econflow.outputs.registry import get_renderer
        tex = get_renderer("latex")().render(_simple_table())
        assert r"\textit{Note:}" in tex
        assert "OLS estimates" in tex

    def test_table_without_footer_no_flushleft(self):
        """If no footer or notes, flushleft block must not be emitted."""
        from econflow.outputs.model import ReportTable, TableRow
        from econflow.outputs.registry import get_renderer
        t = ReportTable(title="T", table_type="regression", columns=["(1)"])
        t.add_row(TableRow(label="x", cells={"(1)": "1.0"}))
        tex = get_renderer("latex")().render(t)
        assert r"\begin{flushleft}" not in tex


# ---------------------------------------------------------------------------
# C2 — estimator_id field on DiagnosticResult + run_with_context()
# ---------------------------------------------------------------------------

class TestC2EstimatorId:
    def test_estimator_id_default_is_empty_string(self):
        dr = _diag_result()
        assert dr.estimator_id == ""

    def test_estimator_id_can_be_set(self):
        dr = _diag_result(estimator_id="fe")
        assert dr.estimator_id == "fe"

    def test_to_dict_includes_estimator_id(self):
        dr = _diag_result(estimator_id="ols")
        d = dr.to_dict()
        assert "estimator_id" in d
        assert d["estimator_id"] == "ols"

    def test_from_dict_round_trips_estimator_id(self):
        from econflow.estimation.result import DiagnosticResult
        dr = _diag_result(estimator_id="twfe")
        restored = DiagnosticResult.from_dict(dr.to_dict())
        assert restored.estimator_id == "twfe"

    def test_from_dict_missing_estimator_id_defaults_empty(self):
        from econflow.estimation.result import DiagnosticResult
        d = {"diagnostic_id": "x", "diagnostic_name": "X"}  # no estimator_id key
        restored = DiagnosticResult.from_dict(d)
        assert restored.estimator_id == ""

    def test_run_with_context_stamps_estimator_id(self):
        """run_with_context() must copy estimator_id from EstimationResult."""
        import econflow.diagnostics.plugins  # noqa: F401 — register plugins
        from econflow.diagnostics import get_diagnostic

        er = _estimation_result(estimator_id="entity_fe")
        bp = get_diagnostic("breusch_pagan")()
        dr = bp.run_with_context(er)
        assert dr.estimator_id == "entity_fe"

    def test_run_with_context_kwargs_forwarded(self):
        """run_with_context() must forward **kwargs to run()."""
        import econflow.diagnostics.plugins  # noqa: F401
        from econflow.diagnostics import get_diagnostic

        er = _estimation_result("ols")
        hausman = get_diagnostic("hausman")()
        # Hausman needs an alternative result; pass via kwargs
        er2 = _estimation_result("fe")
        dr = hausman.run_with_context(er, alternative=er2)
        assert dr.estimator_id == "ols"

    def test_diagnostics_report_estimator_column_populated(self):
        """Estimator column in built table must not be empty when estimator_id is set."""
        from econflow.outputs.diagnostics_report import build_diagnostics_report
        dr = _diag_result(estimator_id="fe")
        t = build_diagnostics_report([dr])
        # First data row
        row = next(r for r in t.rows if r.row_type == "data")
        assert row.cells["Estimator"] == "fe"

    def test_diagnostics_report_groups_by_estimator_id(self):
        """With group_by_estimator=True, rows with different estimator_ids get a separator."""
        from econflow.outputs.diagnostics_report import build_diagnostics_report
        dr_fe = _diag_result(estimator_id="fe")
        dr_ols = _diag_result(estimator_id="ols")
        t = build_diagnostics_report([dr_fe, dr_ols], group_by_estimator=True)
        sep_rows = [r for r in t.rows if r.row_type == "separator"]
        assert len(sep_rows) == 1  # one separator between the two groups


# ---------------------------------------------------------------------------
# H1 — _conclusion() uses plugin conclusion, not level-derived Pass/Fail
# ---------------------------------------------------------------------------

class TestH1Conclusion:
    def test_conclusion_from_plugin_preferred(self):
        from econflow.outputs.diagnostics_report import build_diagnostics_report
        dr = _diag_result(
            conclusion="Reject H0: heteroskedasticity detected",
            level="warning",
        )
        t = build_diagnostics_report([dr])
        row = next(r for r in t.rows if r.row_type == "data")
        assert "Reject H0" in row.cells["Conclusion"]
        assert "Pass" not in row.cells["Conclusion"]
        assert "Fail" not in row.cells["Conclusion"]

    def test_conclusion_fallback_warning_level(self):
        """When conclusion is empty and level=warning, emit 'Reject H0'."""
        from econflow.outputs.diagnostics_report import build_diagnostics_report
        dr = _diag_result(conclusion="", level="warning")
        t = build_diagnostics_report([dr])
        row = next(r for r in t.rows if r.row_type == "data")
        assert row.cells["Conclusion"] == "Reject H0"

    def test_conclusion_fallback_info_level(self):
        """When conclusion is empty and level=info, emit 'Fail to reject H0'."""
        from econflow.outputs.diagnostics_report import build_diagnostics_report
        dr = _diag_result(conclusion="", level="info")
        t = build_diagnostics_report([dr])
        row = next(r for r in t.rows if r.row_type == "data")
        assert row.cells["Conclusion"] == "Fail to reject H0"

    def test_skip_level_returns_na(self):
        from econflow.outputs.diagnostics_report import build_diagnostics_report
        dr = _diag_result(conclusion="", level="skip")
        t = build_diagnostics_report([dr])
        row = next(r for r in t.rows if r.row_type == "data")
        assert row.cells["Conclusion"] == "N/A"

    def test_error_level_returns_error(self):
        from econflow.outputs.diagnostics_report import build_diagnostics_report
        dr = _diag_result(conclusion="", level="error")
        t = build_diagnostics_report([dr])
        row = next(r for r in t.rows if r.row_type == "data")
        assert row.cells["Conclusion"] == "Error"

    def test_long_conclusion_truncated(self):
        from econflow.outputs.diagnostics_report import build_diagnostics_report
        long_msg = "A" * 100
        dr = _diag_result(conclusion=long_msg, level="info")
        t = build_diagnostics_report([dr])
        row = next(r for r in t.rows if r.row_type == "data")
        assert len(row.cells["Conclusion"]) <= 60


# ---------------------------------------------------------------------------
# H2 — PublicationBundle.write() pre-validates renderer IDs
# ---------------------------------------------------------------------------

class TestH2PreValidation:
    def test_unknown_renderer_raises_value_error(self, tmp_path):
        """write() must raise ValueError before creating any files."""
        from econflow.outputs.bundle import PublicationBundle
        bundle = PublicationBundle(
            tmp_path / "out",
            table_formats=["csv", "nonexistent_format"],
        )
        bundle.add_table(_simple_table(), slug="t1")
        with pytest.raises(ValueError, match="nonexistent_format"):
            bundle.write()

    def test_no_files_written_on_bad_renderer(self, tmp_path):
        """When validation fails, the output directory must not exist."""
        from econflow.outputs.bundle import PublicationBundle
        out_dir = tmp_path / "out"
        bundle = PublicationBundle(out_dir, table_formats=["bad_renderer"])
        bundle.add_table(_simple_table(), slug="t1")
        with pytest.raises(ValueError):
            bundle.write()
        # Directories must not have been created
        assert not out_dir.exists(), "output_dir must not be created on validation failure"

    def test_valid_formats_write_successfully(self, tmp_path):
        """Known renderer IDs must not raise."""
        from econflow.outputs.bundle import PublicationBundle
        bundle = PublicationBundle(tmp_path / "out", table_formats=["csv"])
        bundle.add_table(_simple_table(), slug="t1")
        manifest = bundle.write()
        assert len(manifest["tables"]) == 1

    def test_multiple_unknown_formats_all_reported(self, tmp_path):
        """All unknown IDs must be included in the error message."""
        from econflow.outputs.bundle import PublicationBundle
        bundle = PublicationBundle(
            tmp_path / "out",
            table_formats=["bad1", "bad2"],
        )
        bundle.add_table(_simple_table(), slug="t1")
        with pytest.raises(ValueError) as exc_info:
            bundle.write()
        msg = str(exc_info.value)
        assert "bad1" in msg
        assert "bad2" in msg


# ---------------------------------------------------------------------------
# H3 — Duplicate slug raises ValueError in add_table() / add_figure()
# ---------------------------------------------------------------------------

class TestH3DuplicateSlug:
    def test_duplicate_table_slug_raises(self):
        from econflow.outputs.bundle import PublicationBundle
        bundle = PublicationBundle("/tmp/unused")
        bundle.add_table(_simple_table(), slug="same_slug")
        with pytest.raises(ValueError, match="same_slug"):
            bundle.add_table(_simple_table(), slug="same_slug")

    def test_duplicate_slug_from_title_raises(self):
        """Same title produces same slug — must raise on second add."""
        from econflow.outputs.bundle import PublicationBundle
        bundle = PublicationBundle("/tmp/unused")
        bundle.add_table(_simple_table(title="My Results"))
        with pytest.raises(ValueError):
            bundle.add_table(_simple_table(title="My Results"))

    def test_different_explicit_slugs_ok(self):
        from econflow.outputs.bundle import PublicationBundle
        bundle = PublicationBundle("/tmp/unused")
        bundle.add_table(_simple_table(), slug="slug_a")
        bundle.add_table(_simple_table(), slug="slug_b")  # should not raise
        assert len(bundle._tables) == 2

    def test_duplicate_figure_slug_raises(self):
        from econflow.outputs.bundle import PublicationBundle
        from econflow.outputs.model import ReportFigure
        bundle = PublicationBundle("/tmp/unused")
        fig = ReportFigure(title="Fig", figure_type="coefficient_plot")
        bundle.add_figure(fig, slug="fig1")
        with pytest.raises(ValueError, match="fig1"):
            bundle.add_figure(fig, slug="fig1")

    def test_error_message_contains_slug(self):
        from econflow.outputs.bundle import PublicationBundle
        bundle = PublicationBundle("/tmp/unused")
        bundle.add_table(_simple_table(), slug="my_table")
        with pytest.raises(ValueError) as exc_info:
            bundle.add_table(_simple_table(), slug="my_table")
        assert "my_table" in str(exc_info.value)


# ---------------------------------------------------------------------------
# M3 — RendererError exported from econflow.outputs
# ---------------------------------------------------------------------------

class TestM3RendererErrorExport:
    def test_import_from_outputs(self):
        from econflow.outputs import RendererError  # must not raise
        assert RendererError is not None

    def test_is_in_all(self):
        import econflow.outputs as outputs_mod
        assert "RendererError" in outputs_mod.__all__

    def test_is_exception(self):
        from econflow.outputs import RendererError
        assert issubclass(RendererError, Exception)


# ---------------------------------------------------------------------------
# M4 — ReportTable.from_dict() uses explicit field mapping
# ---------------------------------------------------------------------------

class TestM4FromDictExplicit:
    def test_basic_round_trip(self):
        from econflow.outputs.model import ReportTable, TableRow
        t = ReportTable(title="T", table_type="regression", columns=["(1)"])
        t.add_row(TableRow(label="x1", cells={"(1)": "0.5***"},
                           sub_cells={"(1)": "(0.1)"}, bold=True))
        t.add_separator()
        d = t.to_dict()
        t2 = ReportTable.from_dict(d)
        assert t2.rows[0].label == "x1"
        assert t2.rows[0].cells == {"(1)": "0.5***"}
        assert t2.rows[0].sub_cells == {"(1)": "(0.1)"}
        assert t2.rows[0].bold is True
        assert t2.rows[1].row_type == "separator"

    def test_extra_key_in_row_dict_is_ignored(self):
        """Explicit mapping ignores unknown keys rather than raising TypeError."""
        from econflow.outputs.model import ReportTable
        d = {
            "title": "T",
            "table_type": "regression",
            "columns": ["(1)"],
            "rows": [
                {
                    "label": "x1",
                    "cells": {"(1)": "0.5"},
                    "sub_cells": None,
                    "row_type": "data",
                    "bold": False,
                    "italic": False,
                    "unknown_future_field": "ignored",  # forward-compat
                }
            ],
        }
        t = ReportTable.from_dict(d)  # must not raise
        assert t.rows[0].label == "x1"

    def test_missing_optional_key_uses_default(self):
        """from_dict must handle rows that omit optional fields."""
        from econflow.outputs.model import ReportTable
        d = {
            "title": "T",
            "table_type": "regression",
            "columns": ["(1)"],
            "rows": [{"label": "x1", "cells": {"(1)": "0.5"}}],
        }
        t = ReportTable.from_dict(d)
        assert t.rows[0].sub_cells is None
        assert t.rows[0].row_type == "data"
        assert t.rows[0].bold is False

    def test_sub_cells_none_becomes_none(self):
        """sub_cells: null in JSON must round-trip as None, not empty dict."""
        from econflow.outputs.model import ReportTable, TableRow
        t = ReportTable(title="T", table_type="regression", columns=["(1)"])
        t.add_row(TableRow(label="N", cells={"(1)": "100"}, sub_cells=None))
        t2 = ReportTable.from_dict(t.to_dict())
 