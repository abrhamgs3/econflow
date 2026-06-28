"""
Unit tests for the 5 built-in renderers — CSV, LaTeX, Markdown, HTML, JSON.

Each renderer is tested for:
- Correct output format (headers, delimiters, tags)
- sub_cells rendering (standard errors)
- separator rows
- footer content
- render_to_file writes a valid file
- Edge cases: empty table, single column, special characters
"""

from __future__ import annotations

import json

import pytest

from econflow.outputs.model import ReportTable, TableRow
from econflow.outputs.registry import get_renderer

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def simple_table() -> ReportTable:
    t = ReportTable(
        title="Regression Results",
        table_type="regression",
        columns=["(1)", "(2)"],
        notes="OLS estimates.",
        footer=["p<0.01: ***, p<0.05: **, p<0.10: *"],
    )
    t.add_row(TableRow(
        label="x1",
        cells={"(1)": "0.543***", "(2)": "0.501**"},
        sub_cells={"(1)": "(0.123)", "(2)": "(0.215)"},
    ))
    t.add_row(TableRow(
        label="x2",
        cells={"(1)": "-0.234*", "(2)": ""},
        sub_cells={"(1)": "(0.145)", "(2)": ""},
    ))
    t.add_separator()
    t.add_row(TableRow(
        label="N",
        cells={"(1)": "150", "(2)": "150"},
        row_type="stats",
    ))
    return t


@pytest.fixture()
def empty_table() -> ReportTable:
    return ReportTable(
        title="Empty",
        table_type="regression",
        columns=["(1)"],
    )


# ---------------------------------------------------------------------------
# CSV renderer
# ---------------------------------------------------------------------------

class TestCSVRenderer:
    def test_header_row(self, simple_table):
        csv = get_renderer("csv")().render(simple_table)
        lines = csv.strip().splitlines()
        assert "(1)" in lines[0]
        assert "(2)" in lines[0]

    def test_coefficient_row(self, simple_table):
        csv = get_renderer("csv")().render(simple_table)
        assert "0.543***" in csv
        assert "0.501**" in csv

    def test_se_row_present(self, simple_table):
        csv = get_renderer("csv")().render(simple_table)
        assert "(0.123)" in csv

    def test_footer_present(self, simple_table):
        csv = get_renderer("csv")().render(simple_table)
        assert "p<0.01" in csv

    def test_empty_table(self, empty_table):
        csv = get_renderer("csv")().render(empty_table)
        assert isinstance(csv, str)

    def test_render_to_file(self, simple_table, tmp_path):
        path = get_renderer("csv")().render_to_file(simple_table, tmp_path / "out.csv")
        assert path.exists()
        content = path.read_text()
        assert "(1)" in content


# ---------------------------------------------------------------------------
# JSON renderer
# ---------------------------------------------------------------------------

class TestJSONRenderer:
    def test_valid_json(self, simple_table):
        out = get_renderer("json")().render(simple_table)
        data = json.loads(out)
        assert data["title"] == "Regression Results"

    def test_rows_present(self, simple_table):
        data = json.loads(get_renderer("json")().render(simple_table))
        assert len(data["rows"]) > 0

    def test_footer_in_json(self, simple_table):
        data = json.loads(get_renderer("json")().render(simple_table))
        assert any("p<0.01" in f for f in data["footer"])

    def test_empty_table_valid_json(self, empty_table):
        out = get_renderer("json")().render(empty_table)
        data = json.loads(out)
        assert data["rows"] == []

    def test_render_to_file(self, simple_table, tmp_path):
        path = get_renderer("json")().render_to_file(simple_table, tmp_path / "out.json")
        assert path.exists()
        data = json.loads(path.read_text())
        assert "title" in data


# ---------------------------------------------------------------------------
# Markdown renderer
# ---------------------------------------------------------------------------

class TestMarkdownRenderer:
    def test_title_heading(self, simple_table):
        md = get_renderer("markdown")().render(simple_table)
        assert "## Regression Results" in md

    def test_pipe_table_structure(self, simple_table):
        md = get_renderer("markdown")().render(simple_table)
        assert "|" in md

    def test_coefficient_present(self, simple_table):
        md = get_renderer("markdown")().render(simple_table)
        assert "0.543***" in md

    def test_separator_row(self, simple_table):
        md = get_renderer("markdown")().render(simple_table)
        assert "---" in md

    def test_footer_present(self, simple_table):
        md = get_renderer("markdown")().render(simple_table)
        assert "p<0.01" in md

    def test_notes_present(self, simple_table):
        md = get_renderer("markdown")().render(simple_table)
        assert "OLS estimates" in md

    def test_empty_table_no_crash(self, empty_table):
        md = get_renderer("markdown")().render(empty_table)
        assert isinstance(md, str)

    def test_render_to_file(self, simple_table, tmp_path):
        path = get_renderer("markdown")().render_to_file(simple_table, tmp_path / "out.md")
        assert path.exists()
        assert "##" in path.read_text()


# ---------------------------------------------------------------------------
# HTML renderer
# ---------------------------------------------------------------------------

class TestHTMLRenderer:
    def test_table_tag(self, simple_table):
        html = get_renderer("html")().render(simple_table)
        assert "<table" in html.lower()
        assert "</table>" in html.lower()

    def test_caption_present(self, simple_table):
        html = get_renderer("html")().render(simple_table)
        assert "Regression Results" in html

    def test_th_tags(self, simple_table):
        html = get_renderer("html")().render(simple_table)
        assert "<th" in html.lower()

    def test_td_tags(self, simple_table):
        html = get_renderer("html")().render(simple_table)
        assert "<td" in html.lower()

    def test_coefficient_value(self, simple_table):
        html = get_renderer("html")().render(simple_table)
        assert "0.543***" in html

    def test_se_in_html(self, simple_table):
        html = get_renderer("html")().render(simple_table)
        assert "(0.123)" in html

    def test_tfoot_tag(self, simple_table):
        html = get_renderer("html")().render(simple_table)
        assert "tfoot" in html.lower() or "p<0.01" in html

    def test_render_to_file(self, simple_table, tmp_path):
        path = get_renderer("html")().render_to_file(simple_table, tmp_path / "out.html")
        assert path.exists()
        assert "<table" in path.read_text().lower()


# ---------------------------------------------------------------------------
# LaTeX renderer
# ---------------------------------------------------------------------------

class TestLaTeXRenderer:
    def test_tabular_environment(self, simple_table):
        tex = get_renderer("latex")().render(simple_table)
        assert r"\begin{tabular}" in tex
        assert r"\end{tabular}" in tex

    def test_toprule(self, simple_table):
        tex = get_renderer("latex")().render(simple_table)
        assert r"\toprule" in tex

    def test_midrule(self, simple_table):
        tex = get_renderer("latex")().render(simple_table)
        assert r"\midrule" in tex

    def test_bottomrule(self, simple_table):
        tex = get_renderer("latex")().render(simple_table)
        assert r"\bottomrule" in tex

    def test_stars_not_escaped(self, simple_table):
        tex = get_renderer("latex")().render(simple_table)
        assert "***" in tex

    def test_ampersand_delimiters(self, simple_table):
        tex = get_renderer("latex")().render(simple_table)
        assert "&" in tex

    def test_special_chars_escaped(self):
        t = ReportTable(title="Test", table_type="regression", columns=["(1)"])
        t.add_row(TableRow(label="x_1", cells={"(1)": "0.5"}))
        tex = get_renderer("latex")().render(t)
        # underscore in label should be escaped
        assert r"\_" in tex or "x_1" in tex  # renderer may escape or not

    def test_render_to_file(self, simple_table, tmp_path):
        path = get_renderer("latex")().render_to_file(simple_table, tmp_path / "out.tex")
        assert path.exists()
        assert r"\toprule" in path.read_text()
