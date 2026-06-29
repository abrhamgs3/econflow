"""
Integration tests for econflow inspect, reproduce, and compare CLI commands.

Uses Typer's test runner to avoid subprocess overhead while still exercising
the full CLI dispatch path.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from typer.testing import CliRunner

from econflow.cli import app

runner = CliRunner()


# ---------------------------------------------------------------------------
# econflow inspect
# ---------------------------------------------------------------------------

class TestInspectCli:
    def test_inspect_valid_project_exit_zero(self, project_dir: Path) -> None:
        result = runner.invoke(app, ["inspect", str(project_dir)])
        assert result.exit_code == 0, result.output

    def test_inspect_shows_pass_checks(self, project_dir: Path) -> None:
        result = runner.invoke(app, ["inspect", str(project_dir)])
        assert "Config" in result.output or "pass" in result.output

    def test_inspect_missing_dir_exits_nonzero(self, tmp_path: Path) -> None:
        result = runner.invoke(app, ["inspect", str(tmp_path / "nonexistent")])
        assert result.exit_code != 0 or "fail" in result.output.lower()

    def test_inspect_bad_estimator_exits_nonzero(
        self, project_dir_bad_estimator: Path
    ) -> None:
        result = runner.invoke(app, ["inspect", str(project_dir_bad_estimator)])
        assert result.exit_code != 0

    def test_inspect_writes_json_output(
        self, project_dir: Path, tmp_path: Path
    ) -> None:
        import json

        out = tmp_path / "inspection.json"
        result = runner.invoke(
            app, ["inspect", str(project_dir), "--output", str(out)]
        )
        assert out.exists(), (
            f"JSON not written. Exit: {result.exit_code}\n{result.output}"
        )
        data = json.loads(out.read_text())
        assert "overall_status" in data
        assert "checks" in data

    def test_inspect_strict_warns_as_failure(
        self, project_dir_missing_data: Path
    ) -> None:
        result = runner.invoke(
            app, ["inspect", str(project_dir_missing_data), "--strict"]
        )
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# econflow compare
# ---------------------------------------------------------------------------

class TestCompareCli:
    def _make_csv_dir(self, path: Path, value: float) -> Path:
        path.mkdir(parents=True)
        df = pd.DataFrame({"coef": [value], "se": [0.01]})
        df.to_csv(path / "results.csv", index=False)
        return path

    def test_compare_identical_dirs_exit_zero(self, tmp_path: Path) -> None:
        df = pd.DataFrame({"x": [1.0, 2.0], "y": [3.0, 4.0]})
        b = tmp_path / "baseline"
        r = tmp_path / "replica"
        b.mkdir()
        r.mkdir()
        df.to_csv(b / "out.csv", index=False)
        df.to_csv(r / "out.csv", index=False)
        result = runner.invoke(app, ["compare", str(b), str(r)])
        assert result.exit_code == 0, result.output
        assert "match" in result.output.lower()

    def test_compare_different_dirs_exit_nonzero(self, tmp_path: Path) -> None:
        b = self._make_csv_dir(tmp_path / "b", 1.0)
        r = self._make_csv_dir(tmp_path / "r", 99.0)
        result = runner.invoke(app, ["compare", str(b), str(r)])
        assert result.exit_code != 0
        assert "mismatch" in result.output.lower()

    def test_compare_missing_baseline_exits_nonzero(self, tmp_path: Path) -> None:
        r = self._make_csv_dir(tmp_path / "r", 1.0)
        result = runner.invoke(app, ["compare", str(tmp_path / "nope"), str(r)])
        assert result.exit_code != 0

    def test_compare_writes_json(self, tmp_path: Path) -> None:
        import json

        df = pd.DataFrame({"x": [1.0]})
        b = tmp_path / "b"
        r = tmp_path / "r"
        b.mkdir()
        r.mkdir()
        df.to_csv(b / "out.csv", index=False)
        df.to_csv(r / "out.csv", index=False)
        out = tmp_path / "cmp.json"
        runner.invoke(app, ["compare", str(b), str(r), "--output", str(out)])
        assert out.exists()
        data = json.loads(out.read_text())
        assert "overall_status" in data
        assert "comparisons" in data

    def test_compare_shows_file_names(self, tmp_path: Path) -> None:
        df = pd.DataFrame({"coef": [1.234]})
        b = tmp_path / "b"
        r = tmp_path / "r"
        b.mkdir()
        r.mkdir()
        df.to_csv(b / "result_table.csv", index=False)
        df.to_csv(r / "result_table.csv", index=False)
        result = runner.invoke(app, ["compare", str(b), str(r)])
        assert "result_table.csv" in result.output

    def test_compare_tolerance_option(self, tmp_path: Path) -> None:
        b = tmp_path / "b"
        r = tmp_path / "r"
        b.mkdir()
        r.mkdir()
        pd.DataFrame({"x": [1.0]}).to_csv(b / "t.csv", index=False)
        pd.DataFrame({"x": [1.01]}).to_csv(r / "t.csv", index=False)
        # default tolerance 1e-6 → mismatch
        result_strict = runner.invoke(
            app, ["compare", str(b), str(r), "--tolerance", "1e-6"]
        )
        assert result_strict.exit_code != 0
        # loose tolerance → match
        result_loose = runner.invoke(
            app, ["compare", str(b), str(r), "--tolerance", "0.1"]
        )
        assert result_loose.exit_code == 0


# ---------------------------------------------------------------------------
# econflow reproduce (light integration — subprocess-free path tests)
# ---------------------------------------------------------------------------

class TestReproduceCli:
    def test_reproduce_help_exits_zero(self) -> None:
        result = runner.invoke(app, ["reproduce", "--help"])
        assert result.exit_code == 0

    def test_reproduce_missing_dir_exits_nonzero(self, tmp_path: Path) -> None:
        result = runner.invoke(app, ["reproduce", str(tmp_path / "nonexistent")])
        assert result.exit_code != 0

    def test_reproduce_shows_rule_header(
        self, project_dir: Path, tmp_path: Path
    ) -> None:
        result = runner.invoke(
            app,
            [
                "reproduce",
                str(project_dir),
                "--output-dir",
                str(tmp_path / "out"),
                "--timeout",
                "30",
            ],
        )
        assert "reproduce" in result.output.lower() or "EconFlow" in result.output
