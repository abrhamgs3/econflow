"""
Tests for econflow.replication.comparator.

Covers CSV, LaTeX, and JSON comparison; tolerance handling;
missing files on either side.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from econflow.replication.comparator import compare_outputs
from econflow.replication.models import ComparisonReport


def _write_csv(path: Path, df: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)


# ---------------------------------------------------------------------------
# CSV comparison
# ---------------------------------------------------------------------------

class TestCsvComparison:
    def test_identical_files_match(self, tmp_path: Path) -> None:
        df = pd.DataFrame({"a": [1.0, 2.0], "b": [3.0, 4.0]})
        _write_csv(tmp_path / "baseline" / "out.csv", df)
        _write_csv(tmp_path / "replica" / "out.csv", df)
        report = compare_outputs(tmp_path / "baseline", tmp_path / "replica")
        assert report.overall_status == "pass"
        assert report.match_count == 1

    def test_numeric_within_tolerance_match(self, tmp_path: Path) -> None:
        df_b = pd.DataFrame({"coef": [1.000000000]})
        df_r = pd.DataFrame({"coef": [1.000000001]})
        _write_csv(tmp_path / "b" / "t.csv", df_b)
        _write_csv(tmp_path / "r" / "t.csv", df_r)
        report = compare_outputs(tmp_path / "b", tmp_path / "r", tolerance=1e-6)
        assert report.overall_status == "pass"

    def test_numeric_outside_tolerance_mismatch(self, tmp_path: Path) -> None:
        df_b = pd.DataFrame({"coef": [1.0]})
        df_r = pd.DataFrame({"coef": [2.0]})
        _write_csv(tmp_path / "b" / "t.csv", df_b)
        _write_csv(tmp_path / "r" / "t.csv", df_r)
        report = compare_outputs(tmp_path / "b", tmp_path / "r", tolerance=1e-6)
        assert report.overall_status == "fail"
        assert report.mismatch_count == 1

    def test_max_abs_diff_reported(self, tmp_path: Path) -> None:
        df_b = pd.DataFrame({"x": [0.0, 1.0]})
        df_r = pd.DataFrame({"x": [0.0, 1.5]})
        _write_csv(tmp_path / "b" / "t.csv", df_b)
        _write_csv(tmp_path / "r" / "t.csv", df_r)
        report = compare_outputs(tmp_path / "b", tmp_path / "r")
        c = report.comparisons[0]
        assert c.max_abs_diff is not None
        assert abs(c.max_abs_diff - 0.5) < 1e-9

    def test_shape_mismatch_is_fail(self, tmp_path: Path) -> None:
        df_b = pd.DataFrame({"a": [1, 2, 3]})
        df_r = pd.DataFrame({"a": [1, 2]})
        _write_csv(tmp_path / "b" / "t.csv", df_b)
        _write_csv(tmp_path / "r" / "t.csv", df_r)
        report = compare_outputs(tmp_path / "b", tmp_path / "r")
        assert report.overall_status == "fail"

    def test_column_mismatch_is_fail(self, tmp_path: Path) -> None:
        df_b = pd.DataFrame({"a": [1], "b": [2]})
        df_r = pd.DataFrame({"a": [1], "c": [2]})
        _write_csv(tmp_path / "b" / "t.csv", df_b)
        _write_csv(tmp_path / "r" / "t.csv", df_r)
        report = compare_outputs(tmp_path / "b", tmp_path / "r")
        assert report.overall_status == "fail"
        c = report.comparisons[0]
        assert "b" in c.columns_differ or "c" in c.columns_differ

    def test_string_column_exact_match(self, tmp_path: Path) -> None:
        df = pd.DataFrame({"model": ["OLS", "FE"], "coef": [1.0, 2.0]})
        _write_csv(tmp_path / "b" / "t.csv", df)
        _write_csv(tmp_path / "r" / "t.csv", df)
        report = compare_outputs(tmp_path / "b", tmp_path / "r")
        assert report.overall_status == "pass"

    def test_string_column_mismatch(self, tmp_path: Path) -> None:
        df_b = pd.DataFrame({"model": ["OLS"]})
        df_r = pd.DataFrame({"model": ["FE"]})
        _write_csv(tmp_path / "b" / "t.csv", df_b)
        _write_csv(tmp_path / "r" / "t.csv", df_r)
        report = compare_outputs(tmp_path / "b", tmp_path / "r")
        assert report.overall_status == "fail"


# ---------------------------------------------------------------------------
# Missing files
# ---------------------------------------------------------------------------

class TestMissingFiles:
    def test_file_missing_in_replica(self, tmp_path: Path) -> None:
        _write_csv(tmp_path / "b" / "only_in_b.csv", pd.DataFrame({"x": [1]}))
        (tmp_path / "r").mkdir()
        report = compare_outputs(tmp_path / "b", tmp_path / "r")
        assert report.overall_status in ("warn", "fail")
        assert report.missing_count >= 1

    def test_file_missing_in_baseline(self, tmp_path: Path) -> None:
        (tmp_path / "b").mkdir()
        _write_csv(tmp_path / "r" / "only_in_r.csv", pd.DataFrame({"x": [1]}))
        report = compare_outputs(tmp_path / "b", tmp_path / "r")
        # Extra file in replica is a warning, not a failure
        assert report.overall_status in ("warn", "pass")

    def test_empty_dirs_produce_skip(self, tmp_path: Path) -> None:
        (tmp_path / "b").mkdir()
        (tmp_path / "r").mkdir()
        report = compare_outputs(tmp_path / "b", tmp_path / "r")
        assert isinstance(report, ComparisonReport)
        # No files → skip entry
        assert any(c.status == "skip" for c in report.comparisons)


# ---------------------------------------------------------------------------
# LaTeX comparison
# ---------------------------------------------------------------------------

class TestTexComparison:
    def test_identical_tex_match(self, tmp_path: Path) -> None:
        tex = r"\begin{tabular}{ll} \hline a & b \\ \hline \end{tabular}"
        (tmp_path / "b").mkdir()
        (tmp_path / "r").mkdir()
        (tmp_path / "b" / "table.tex").write_text(tex, encoding="utf-8")
        (tmp_path / "r" / "table.tex").write_text(tex, encoding="utf-8")
        report = compare_outputs(tmp_path / "b", tmp_path / "r")
        assert report.comparisons[0].status == "match"

    def test_comment_stripped_before_compare(self, tmp_path: Path) -> None:
        tex_b = r"\begin{table} % generated on Monday" + "\n" + r"\end{table}"
        tex_r = r"\begin{table} % generated on Tuesday" + "\n" + r"\end{table}"
        (tmp_path / "b").mkdir()
        (tmp_path / "r").mkdir()
        (tmp_path / "b" / "t.tex").write_text(tex_b, encoding="utf-8")
        (tmp_path / "r" / "t.tex").write_text(tex_r, encoding="utf-8")
        report = compare_outputs(tmp_path / "b", tmp_path / "r")
        assert report.comparisons[0].status == "match"


# ---------------------------------------------------------------------------
# JSON comparison
# ---------------------------------------------------------------------------

class TestJsonComparison:
    def test_identical_json_match(self, tmp_path: Path) -> None:
        import json
        data = {"a": 1, "b": [1.0, 2.0]}
        (tmp_path / "b").mkdir()
        (tmp_path / "r").mkdir()
        (tmp_path / "b" / "meta.json").write_text(json.dumps(data), encoding="utf-8")
        (tmp_path / "r" / "meta.json").write_text(json.dumps(data), encoding="utf-8")
        report = compare_outputs(tmp_path / "b", tmp_path / "r")
        assert report.comparisons[0].status == "match"

    def test_numeric_json_diff_within_tolerance_match(self, tmp_path: Path) -> None:
        import json
        (tmp_path / "b").mkdir()
        (tmp_path / "r").mkdir()
        (tmp_path / "b" / "m.json").write_text(json.dumps({"v": 1.0}), encoding="utf-8")
        (tmp_path / "r" / "m.json").write_text(json.dumps({"v": 1.0000000005}), encoding="utf-8")
        report = compare_outputs(tmp_path / "b", tmp_path / "r", tolerance=1e-6)
        assert report.comparisons[0].status == "match"

    def test_key_missing_in_replica_mismatch(self, tmp_path: Path) -> None:
        import json
        (tmp_path / "b").mkdir()
        (tmp_path / "r").mkdir()
        (tmp_path / "b" / "m.json").write_text(json.dumps({"a": 1, "b": 2}), encoding="utf-8")
        (tmp_path / "r" / "m.json").write_text(json.dumps({"a": 1}), encoding="utf-8")
        report = compare_outputs(tmp_path / "b", tmp_path / "r")
        assert report.comparisons[0].status == "mismatch"


# ---------------------------------------------------------------------------
# Multiple files
# ---------------------------------------------------------------------------

class TestMultipleFiles:
    def test_all_match(self, tmp_path: Path) -> None:
        for name in ["a.csv", "b.csv", "c.csv"]:
            df = pd.DataFrame({"x": [1.0, 2.0]})
            _write_csv(tmp_path / "b" / name, df)
            _write_csv(tmp_path / "r" / name, df)
        report = compare_outputs(tmp_path / "b", tmp_path / "r")
        assert report.overall_status == "pass"
        assert report.match_count == 3

    def test_one_mismatch_fails_overall(self, tmp_path: Path) -> None:
        for name in ["good.csv", "bad.csv"]:
            df_b = pd.DataFrame({"x": [1.0]})
            df_r = pd.DataFrame({"x": [1.0 if name == "good.csv" else 99.0]})
            _write_csv(tmp_path / "b" / name, df_b)
            _write_csv(tmp_path / "r" / name, df_r)
        report = compare_outputs(tmp_path / "b", tmp_path / "r")
        assert report.overall_status == "fail"
        assert report.match_count == 1
        assert report.mismatch_count == 1
