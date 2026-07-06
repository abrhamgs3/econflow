"""
Unit tests for econflow.outputs.model — ReportTable and ReportFigure.

Covers:
- TableRow construction and to_dict()
- ReportTable.add_row / add_separator / n_data_rows
- ReportTable.to_dict / to_json / from_dict round-trip
- ReportFigure.to_dict / to_json
"""

from __future__ import annotations

import json

from econflow.outputs.model import ReportFigure, ReportTable, TableRow

# ---------------------------------------------------------------------------
# TableRow
# ---------------------------------------------------------------------------

class TestTableRow:
    def test_defaults(self):
        row = TableRow(label="x1")
        assert row.label == "x1"
        assert row.cells == {}
        assert row.sub_cells is None
        assert row.row_type == "data"
        assert row.bold is False
        assert row.italic is False

    def test_to_dict_round_trip(self):
        row = TableRow(
            label="x1",
            cells={"(1)": "0.543***"},
            sub_cells={"(1)": "(0.123)"},
            row_type="data",
            bold=True,
        )
        d = row.to_dict()
        assert d["label"] == "x1"
        assert d["cells"]["(1)"] == "0.543***"
        assert d["sub_cells"]["(1)"] == "(0.123)"
        assert d["bold"] is True

    def test_to_dict_no_sub_cells(self):
        row = TableRow(label="N", cells={"(1)": "150"}, row_type="stats")
        d = row.to_dict()
        assert d["sub_cells"] is None
        assert d["row_type"] == "stats"


# ---------------------------------------------------------------------------
# ReportTable construction
# ---------------------------------------------------------------------------

class TestReportTableConstruction:
    def _make_table(self) -> ReportTable:
        t = ReportTable(
            title="Regression Results",
            table_type="regression",
            columns=["(1)", "(2)"],
        )
        t.add_row(TableRow(label="x1", cells={"(1)": "0.5***", "(2)": "0.4**"}))
        t.add_row(TableRow(label="x2", cells={"(1)": "0.1", "(2)": ""}))
        t.add_separator()
        t.add_row(TableRow(label="N", cells={"(1)": "100", "(2)": "100"}, row_type="stats"))
        return t

    def test_n_data_rows(self):
        t = self._make_table()
        assert t.n_data_rows() == 2

    def test_add_separator(self):
        t = self._make_table()
        sep_rows = [r for r in t.rows if r.row_type == "separator"]
        assert len(sep_rows) == 1
        assert sep_rows[0].label == ""

    def test_total_rows(self):
        t = self._make_table()
        # 2 data + 1 separator + 1 stats
        assert len(t.rows) == 4

    def test_footer_mutable(self):
        t = self._make_table()
        t.footer.append("* p<0.10")
        assert "* p<0.10" in t.footer

    def test_subtitle_default(self):
        t = ReportTable(title="T", table_type="regression", columns=["(1)"])
        assert t.subtitle == ""

    def test_notes_default(self):
        t = ReportTable(title="T", table_type="regression", columns=["(1)"])
        assert t.notes == ""


# ---------------------------------------------------------------------------
# ReportTable serialisation
# ---------------------------------------------------------------------------

class TestReportTableSerialisation:
    def _table(self) -> ReportTable:
        t = ReportTable(
            title="Stats",
            table_type="summary_stats",
            columns=["N", "Mean"],
            subtitle="Panel A",
            notes="OLS standard errors.",
            footer=["* p<0.10"],
        )
        t.add_row(TableRow(label="y", cells={"N": "100", "Mean": "3.14"}))
        return t

    def test_to_dict_keys(self):
        d = self._table().to_dict()
        expected_keys = (
            "title", "table_type", "columns", "rows",
            "footer", "subtitle", "notes", "metadata",
        )
        for key in expected_keys:
            assert key in d, f"Missing key: {key}"

    def test_to_json_valid(self):
        j = self._table().to_json()
        data = json.loads(j)
        assert data["title"] == "Stats"

    def test_to_json_indent(self):
        j = self._table().to_json(indent=4)
        assert "\n" in j

    def test_from_dict_round_trip(self):
        t = self._table()
        d = t.to_dict()
        t2 = ReportTable.from_dict(d)
        assert t2.title == t.title
        assert t2.table_type == t.table_type
        assert len(t2.rows) == len(t.rows)
        assert t2.rows[0].label == "y"
        assert t2.rows[0].cells["Mean"] == "3.14"
        assert t2.footer == ["* p<0.10"]
        assert t2.subtitle == "Panel A"

    def test_from_dict_preserves_row_type(self):
        t = self._table()
        t.add_separator()
        d = t.to_dict()
        t2 = ReportTable.from_dict(d)
        sep = [r for r in t2.rows if r.row_type == "separator"]
        assert len(sep) == 1

    def test_from_dict_preserves_sub_cells(self):
        t = ReportTable(title="R", table_type="regression", columns=["(1)"])
        t.add_row(TableRow(
            label="x",
            cells={"(1)": "0.5***"},
            sub_cells={"(1)": "(0.1)"},
        ))
        t2 = ReportTable.from_dict(t.to_dict())
        assert t2.rows[0].sub_cells == {"(1)": "(0.1)"}


# ---------------------------------------------------------------------------
# ReportFigure
# ---------------------------------------------------------------------------

class TestReportFigure:
    def _fig(self) -> ReportFigure:
        return ReportFigure(
            title="Coefficient Plot",
            figure_type="coefficient_plot",
            data={"variables": ["x1", "x2"], "coefficients": [0.5, -0.2]},
            config={"confidence_level": 0.95},
            metadata={"estimator": "fe"},
        )

    def test_construction(self):
        f = self._fig()
        assert f.title == "Coefficient Plot"
        assert f.figure_type == "coefficient_plot"
        assert f.data["variables"] == ["x1", "x2"]

    def test_to_dict(self):
        d = self._fig().to_dict()
        assert d["title"] == "Coefficient Plot"
        assert "data" in d
        assert "config" in d
        assert "metadata" in d

    def test_to_json_valid(self):
        j = self._fig().to_json()
        parsed = json.loads(j)
        assert parsed["figure_type"] == "coefficient_plot"

    def test_defaults(self):
        f = ReportFigure(title="T", figure_type="generic")
        assert f.data == {}
        assert f.config == {}
        assert f.metadata == {}
