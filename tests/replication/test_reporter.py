"""
Tests for econflow.replication.reporter — Markdown and JSON generation.
"""

from __future__ import annotations

from pathlib import Path

from econflow.replication.models import (
    ComparisonReport,
    InspectionReport,
    OutputComparison,
    ProjectCheck,
    ReplicationResult,
    StepResult,
)
from econflow.replication.reporter import ReproducibilityReport


def _sample_inspection() -> InspectionReport:
    return InspectionReport.build(
        project_dir=Path("/tmp/proj"),
        checks=[
            ProjectCheck("config_found", "Config", "pass", "config.yaml"),
            ProjectCheck("data_found", "Data", "warn", "No provenance"),
        ],
    )


def _sample_result() -> ReplicationResult:
    return ReplicationResult(
        run_id="test-run-123",
        project_dir="/tmp/proj",
        timestamp_utc="2026-01-01T00:00:00+00:00",
        status="success",
        elapsed_seconds=10.5,
        outputs_dir="/tmp/out",
        outputs=["/tmp/out/tables/comparison.csv"],
        step_results=[
            StepResult("validate", "Validate", "success", 0, 1.0),
            StepResult("run", "Run pipeline", "success", 0, 9.5),
        ],
    )


def _sample_comparison() -> ComparisonReport:
    return ComparisonReport.build(
        baseline_dir=Path("/tmp/baseline"),
        replica_dir=Path("/tmp/replica"),
        comparisons=[
            OutputComparison("out.csv", "match", max_abs_diff=0.0, rows_differ=0,
                             message="All 50 rows match"),
        ],
    )


class TestReproducibilityReport:
    def test_overall_status_pass(self) -> None:
        r = ReproducibilityReport(
            inspection=_sample_inspection(),
            execution=_sample_result(),
            comparison=_sample_comparison(),
        )
        # inspection is warn, comparison is pass, execution is success
        assert r.overall_status == "warn"

    def test_overall_status_fail_on_failed_execution(self) -> None:
        result = ReplicationResult(
            run_id="x",
            project_dir="/tmp",
            timestamp_utc="2026-01-01T00:00:00+00:00",
            status="failed",
            elapsed_seconds=1.0,
            outputs_dir="/tmp",
        )
        r = ReproducibilityReport(execution=result)
        assert r.overall_status == "fail"

    def test_to_markdown_contains_headers(self) -> None:
        r = ReproducibilityReport(
            inspection=_sample_inspection(),
            execution=_sample_result(),
        )
        md = r.to_markdown()
        assert "# EconFlow Reproducibility Report" in md
        assert "## Pre-flight Inspection" in md
        assert "## Replication Execution" in md

    def test_to_markdown_contains_status(self) -> None:
        r = ReproducibilityReport(inspection=_sample_inspection())
        md = r.to_markdown()
        assert "WARN" in md or "PASS" in md

    def test_to_json_roundtrip(self) -> None:
        import json
        r = ReproducibilityReport(
            inspection=_sample_inspection(),
            execution=_sample_result(),
            comparison=_sample_comparison(),
        )
        data = json.loads(r.to_json())
        assert "inspection" in data
        assert "execution" in data
        assert "comparison" in data

    def test_to_markdown_includes_file_list(self) -> None:
        r = ReproducibilityReport(execution=_sample_result())
        md = r.to_markdown()
        assert "comparison.csv" in md or "1 file" in md

    def test_to_markdown_includes_check_table(self) -> None:
        r = ReproducibilityReport(inspection=_sample_inspection())
        md = r.to_markdown()
        assert "Config" in md
        assert "config.yaml" in md

    def test_save_writes_both_files(self, tmp_path: Path) -> None:
        r = ReproducibilityReport(inspection=_sample_inspection())
        md_path, json_path = r.save(tmp_path)
        assert md_path.exists()
        assert json_path.exists()
        assert md_path.suffix == ".md"
        assert json_path.suffix == ".json"

    def test_save_creates_output_dir(self, tmp_path: Path) -> None:
        out = tmp_path / "nested" / "reports"
        r = ReproducibilityReport(inspection=_sample_inspection())
        md_path, json_path = r.save(out)
        assert out.exists()

    def test_report_without_inspection_or_execution(self) -> None:
        r = ReproducibilityReport()
        # Should not crash
        md = r.to_markdown()
        assert "EconFlow" in md

    def test_comparison_section_in_markdown(self) -> None:
        r = ReproducibilityReport(comparison=_sample_comparison())
        md = r.to_markdown()
        assert "## Output Comparison" in md
        assert "out.csv" in md
