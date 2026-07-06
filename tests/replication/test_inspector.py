"""
Tests for econflow.replication.inspector.

Covers all ProjectCheck types:
  python_version, config_found, models_found, outputs_cfg_found,
  data_found, data_checksum, estimators_registered, dependencies
"""

from __future__ import annotations

from pathlib import Path

from econflow.replication.inspector import inspect_project
from econflow.replication.models import InspectionReport, ProjectCheck


def _check(report: InspectionReport, check_id: str) -> ProjectCheck:
    for c in report.checks:
        if c.check_id == check_id:
            return c
    raise KeyError(f"Check '{check_id}' not in report")


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

class TestInspectValidProject:
    def test_returns_inspection_report(self, project_dir: Path) -> None:
        report = inspect_project(project_dir)
        assert isinstance(report, InspectionReport)

    def test_overall_pass_or_warn(self, project_dir: Path) -> None:
        report = inspect_project(project_dir)
        assert report.overall_status in ("pass", "warn"), (
            f"Expected pass/warn, got {report.overall_status}\n"
            + "\n".join(f"  {c.check_id}: {c.status} — {c.message}" for c in report.checks)
        )

    def test_config_found(self, project_dir: Path) -> None:
        report = inspect_project(project_dir)
        c = _check(report, "config_found")
        assert c.status == "pass"

    def test_models_found(self, project_dir: Path) -> None:
        report = inspect_project(project_dir)
        c = _check(report, "models_found")
        assert c.status == "pass"

    def test_outputs_cfg_found(self, project_dir: Path) -> None:
        report = inspect_project(project_dir)
        c = _check(report, "outputs_cfg_found")
        assert c.status == "pass"

    def test_data_found(self, project_dir: Path) -> None:
        report = inspect_project(project_dir)
        c = _check(report, "data_found")
        assert c.status == "pass"
        assert "panel.csv" in c.message

    def test_estimators_registered(self, project_dir: Path) -> None:
        report = inspect_project(project_dir)
        c = _check(report, "estimators_registered")
        assert c.status == "pass"
        assert "ols" in c.message
        assert "fe" in c.message

    def test_dependencies_pass(self, project_dir: Path) -> None:
        report = inspect_project(project_dir)
        c = _check(report, "dependencies")
        assert c.status == "pass"
        assert "econflow" in c.message

    def test_python_version_pass(self, project_dir: Path) -> None:
        report = inspect_project(project_dir)
        c = _check(report, "python_version")
        assert c.status == "pass"

    def test_project_dir_in_report(self, project_dir: Path) -> None:
        report = inspect_project(project_dir)
        assert str(project_dir) in report.project_dir

    def test_timestamp_present(self, project_dir: Path) -> None:
        report = inspect_project(project_dir)
        assert report.timestamp_utc
        assert "T" in report.timestamp_utc


# ---------------------------------------------------------------------------
# Missing data
# ---------------------------------------------------------------------------

class TestInspectMissingData:
    def test_overall_fail(self, project_dir_missing_data: Path) -> None:
        report = inspect_project(project_dir_missing_data)
        assert report.overall_status == "fail"

    def test_data_found_fail(self, project_dir_missing_data: Path) -> None:
        report = inspect_project(project_dir_missing_data)
        c = _check(report, "data_found")
        assert c.status == "fail"
        assert "nonexistent.csv" in c.message or "not found" in c.message.lower()

    def test_data_checksum_skip(self, project_dir_missing_data: Path) -> None:
        report = inspect_project(project_dir_missing_data)
        c = _check(report, "data_checksum")
        assert c.status in ("skip", "warn")

    def test_fail_count_nonzero(self, project_dir_missing_data: Path) -> None:
        report = inspect_project(project_dir_missing_data)
        assert report.fail_count > 0


# ---------------------------------------------------------------------------
# Bad estimator
# ---------------------------------------------------------------------------

class TestInspectBadEstimator:
    def test_overall_fail(self, project_dir_bad_estimator: Path) -> None:
        report = inspect_project(project_dir_bad_estimator)
        assert report.overall_status == "fail"

    def test_estimator_check_fail(self, project_dir_bad_estimator: Path) -> None:
        report = inspect_project(project_dir_bad_estimator)
        c = _check(report, "estimators_registered")
        assert c.status == "fail"
        assert "does_not_exist_42" in c.message

    def test_detail_lists_available(self, project_dir_bad_estimator: Path) -> None:
        report = inspect_project(project_dir_bad_estimator)
        c = _check(report, "estimators_registered")
        assert "ols" in c.detail.lower() or "Available" in c.detail


# ---------------------------------------------------------------------------
# Nonexistent directory
# ---------------------------------------------------------------------------

class TestInspectNonexistentDir:
    def test_returns_report_not_raises(self, tmp_path: Path) -> None:
        nonexistent = tmp_path / "does_not_exist"
        # inspect_project should handle missing dirs gracefully
        report = inspect_project(nonexistent)
        assert isinstance(report, InspectionReport)

    def test_overall_fail(self, tmp_path: Path) -> None:
        report = inspect_project(tmp_path / "does_not_exist")
        assert report.overall_status == "fail"


# ---------------------------------------------------------------------------
# Serialisation round-trip
# ---------------------------------------------------------------------------

class TestInspectionReportSerialisation:
    def test_to_json_parses(self, project_dir: Path) -> None:
        import json
        report = inspect_project(project_dir)
        data = json.loads(report.to_json())
        assert data["overall_status"] == report.overall_status
        assert len(data["checks"]) == len(report.checks)

    def test_from_dict_roundtrip(self, project_dir: Path) -> None:
        report = inspect_project(project_dir)
        restored = InspectionReport.from_dict(report.to_dict())
        assert restored.overall_status == report.overall_status
        assert len(restored.checks) == len(report.checks)
        for orig, rest in zip(report.checks, restored.checks):
            assert orig.check_id == rest.check_id
            assert orig.status == rest.status

    def test_counts_correct(self, project_dir: Path) -> None:
        report = inspect_project(project_dir)
        total = report.pass_count + report.warn_count + report.fail_count
        skip_count = sum(1 for c in report.checks if c.status == "skip")
        assert total + skip_count == len(report.checks)
