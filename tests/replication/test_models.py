"""
Tests for econflow.replication.models — dataclass correctness and serialisation.
"""

from __future__ import annotations

import json
from pathlib import Path

from econflow.replication.models import (
    ComparisonReport,
    ExecutionPlan,
    ExecutionStep,
    InspectionReport,
    OutputComparison,
    ProjectCheck,
    ReplicationResult,
    StepResult,
)


class TestProjectCheck:
    def test_to_dict_fields(self) -> None:
        c = ProjectCheck("id1", "Name", "pass", "all good", "extra detail")
        d = c.to_dict()
        assert d["check_id"] == "id1"
        assert d["status"] == "pass"
        assert d["detail"] == "extra detail"


class TestInspectionReport:
    def _make_report(self, statuses: list[str]) -> InspectionReport:
        checks = [
            ProjectCheck(f"c{i}", f"Check {i}", s, "msg")
            for i, s in enumerate(statuses)
        ]
        return InspectionReport.build(project_dir=Path("/tmp/proj"), checks=checks)

    def test_overall_fail_if_any_fail(self) -> None:
        r = self._make_report(["pass", "fail", "warn"])
        assert r.overall_status == "fail"

    def test_overall_warn_if_warn_no_fail(self) -> None:
        r = self._make_report(["pass", "warn"])
        assert r.overall_status == "warn"

    def test_overall_pass_if_all_pass(self) -> None:
        r = self._make_report(["pass", "pass"])
        assert r.overall_status == "pass"

    def test_pass_count(self) -> None:
        r = self._make_report(["pass", "pass", "fail"])
        assert r.pass_count == 2

    def test_fail_count(self) -> None:
        r = self._make_report(["fail", "warn"])
        assert r.fail_count == 1

    def test_warn_count(self) -> None:
        r = self._make_report(["warn", "warn", "pass"])
        assert r.warn_count == 2

    def test_json_roundtrip(self) -> None:
        r = self._make_report(["pass", "warn", "fail"])
        restored = InspectionReport.from_dict(json.loads(r.to_json()))
        assert restored.overall_status == r.overall_status
        assert len(restored.checks) == len(r.checks)


class TestExecutionPlan:
    def test_to_json(self) -> None:
        plan = ExecutionPlan(
            project_dir="/tmp",
            steps=[
                ExecutionStep("s1", "Step 1", ["echo", "hi"], []),
                ExecutionStep("s2", "Step 2", ["echo", "bye"], ["s1"]),
            ],
        )
        data = json.loads(plan.to_json())
        assert len(data["steps"]) == 2
        assert data["steps"][1]["requires"] == ["s1"]


class TestReplicationResult:
    def test_to_dict_status(self) -> None:
        r = ReplicationResult(
            run_id="abc",
            project_dir="/tmp",
            timestamp_utc="2026-01-01T00:00:00+00:00",
            status="success",
            elapsed_seconds=5.0,
            outputs_dir="/tmp/out",
        )
        d = r.to_dict()
        assert d["status"] == "success"
        assert d["elapsed_seconds"] == 5.0

    def test_from_dict_roundtrip(self) -> None:
        r = ReplicationResult(
            run_id="xyz",
            project_dir="/tmp",
            timestamp_utc="2026-01-01T00:00:00+00:00",
            status="partial",
            elapsed_seconds=12.3,
            outputs_dir="/tmp/out",
            step_results=[
                StepResult("s1", "Step 1", "success", 0, 5.0),
                StepResult("s2", "Step 2", "failed", 1, 7.0),
            ],
        )
        restored = ReplicationResult.from_dict(json.loads(r.to_json()))
        assert restored.status == "partial"
        assert len(restored.step_results) == 2
        assert restored.step_results[0].status == "success"


class TestComparisonReport:
    def _make_report(self, statuses: list[str]) -> ComparisonReport:
        comps = [
            OutputComparison(f"file{i}.csv", s, message="msg")
            for i, s in enumerate(statuses)
        ]
        return ComparisonReport.build(Path("/baseline"), Path("/replica"), comps)

    def test_overall_fail_on_mismatch(self) -> None:
        r = self._make_report(["match", "mismatch"])
        assert r.overall_status == "fail"

    def test_overall_warn_on_missing(self) -> None:
        r = self._make_report(["match", "missing_replica"])
        assert r.overall_status == "warn"

    def test_overall_pass_all_match(self) -> None:
        r = self._make_report(["match", "match"])
        assert r.overall_status == "pass"

    def test_match_count(self) -> None:
        r = self._make_report(["match", "match", "mismatch"])
        assert r.match_count == 2

    def test_mismatch_count(self) -> None:
        r = self._make_report(["mismatch", "mismatch"])
        assert r.mismatch_count == 2

    def test_missing_count(self) -> None:
        r = self._make_report(["missing_replica", "missing_baseline"])
        assert r.missing_count == 2

    def test_json_roundtrip(self) -> None:
        r = self._make_report(["match", "mismatch"])
        restored = ComparisonReport.from_dict(json.loads(r.to_json()))
        assert restored.overall_status == r.overall_status
        assert len(restored.comparisons) == 2
