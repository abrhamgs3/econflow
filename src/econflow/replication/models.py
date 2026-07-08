"""
econflow.replication.models — Shared data structures for the Replication Engine.

All dataclasses are JSON-serialisable.  Use :meth:`to_dict` / :meth:`to_json`
for serialisation and :meth:`from_dict` for deserialisation.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _utc_now() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Inspection
# ---------------------------------------------------------------------------

@dataclass
class ProjectCheck:
    """Result of a single pre-flight check run by ``econflow inspect``.

    Attributes
    ----------
    check_id : str
        Short unique identifier, e.g. ``"cfg-01"``, ``"data-02"``.
    name : str
        Human-readable check name.
    status : {"pass", "warn", "fail", "skip"}
        Outcome of the check.
    message : str
        Summary sentence shown in the inspect report.
    detail : str
        Optional extended detail or file path to display.
    """

    check_id: str
    name: str
    status: Literal["pass", "warn", "fail", "skip"]
    message: str
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class InspectionReport:
    """
    Aggregated result of all pre-flight checks for a project directory.

    Produced by :func:`~econflow.replication.inspector.inspect_project`.
    """

    project_dir: str
    timestamp_utc: str
    overall_status: Literal["pass", "warn", "fail"]
    checks: list[ProjectCheck] = field(default_factory=list)

    # ---- factories -------------------------------------------------------

    @classmethod
    def build(
        cls,
        project_dir: Path,
        checks: list[ProjectCheck],
    ) -> InspectionReport:
        if any(c.status == "fail" for c in checks):
            overall = "fail"
        elif any(c.status == "warn" for c in checks):
            overall = "warn"
        else:
            overall = "pass"
        return cls(
            project_dir=str(project_dir),
            timestamp_utc=_utc_now(),
            overall_status=overall,
            checks=checks,
        )

    # ---- serialisation ---------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_dir": self.project_dir,
            "timestamp_utc": self.timestamp_utc,
            "overall_status": self.overall_status,
            "checks": [c.to_dict() for c in self.checks],
        }

    def to_json(self, *, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> InspectionReport:
        checks = [
            ProjectCheck(**c) for c in data.get("checks", [])
        ]
        return cls(
            project_dir=data["project_dir"],
            timestamp_utc=data["timestamp_utc"],
            overall_status=data["overall_status"],
            checks=checks,
        )

    # ---- derived ---------------------------------------------------------

    @property
    def pass_count(self) -> int:
        return sum(1 for c in self.checks if c.status == "pass")

    @property
    def warn_count(self) -> int:
        return sum(1 for c in self.checks if c.status == "warn")

    @property
    def fail_count(self) -> int:
        return sum(1 for c in self.checks if c.status == "fail")


# ---------------------------------------------------------------------------
# Execution planning
# ---------------------------------------------------------------------------

@dataclass
class ExecutionStep:
    """A single ordered step in the replication execution plan."""

    step_id: str
    description: str
    command: list[str]
    requires: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ExecutionPlan:
    """
    Ordered sequence of steps required to reproduce a project.

    Produced by :func:`~econflow.replication.planner.build_plan`.
    """

    project_dir: str
    steps: list[ExecutionStep] = field(default_factory=list)
    estimated_outputs: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_dir": self.project_dir,
            "steps": [s.to_dict() for s in self.steps],
            "estimated_outputs": self.estimated_outputs,
        }

    def to_json(self, *, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Execution results
# ---------------------------------------------------------------------------

@dataclass
class StepResult:
    """Outcome of executing a single :class:`ExecutionStep`."""

    step_id: str
    description: str
    status: Literal["success", "failed", "skipped"]
    exit_code: int | None
    elapsed_seconds: float
    stdout: str = ""
    stderr: str = ""
    skip_reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ReplicationResult:
    """
    Full outcome of an ``econflow reproduce`` run.

    Produced by :func:`~econflow.replication.executor.execute_plan`.
    """

    run_id: str
    project_dir: str
    timestamp_utc: str
    status: Literal["success", "partial", "failed"]
    elapsed_seconds: float
    outputs_dir: str
    outputs: list[str] = field(default_factory=list)
    provenance_path: str | None = None
    error: str | None = None
    step_results: list[StepResult] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "project_dir": self.project_dir,
            "timestamp_utc": self.timestamp_utc,
            "status": self.status,
            "elapsed_seconds": round(self.elapsed_seconds, 3),
            "outputs_dir": self.outputs_dir,
            "outputs": self.outputs,
            "provenance_path": self.provenance_path,
            "error": self.error,
            "step_results": [s.to_dict() for s in self.step_results],
        }

    def to_json(self, *, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ReplicationResult:
        step_results = [StepResult(**s) for s in data.get("step_results", [])]
        return cls(
            run_id=data["run_id"],
            project_dir=data["project_dir"],
            timestamp_utc=data["timestamp_utc"],
            status=data["status"],
            elapsed_seconds=data["elapsed_seconds"],
            outputs_dir=data["outputs_dir"],
            outputs=data.get("outputs", []),
            provenance_path=data.get("provenance_path"),
            error=data.get("error"),
            step_results=step_results,
        )


# ---------------------------------------------------------------------------
# Comparison
# ---------------------------------------------------------------------------

@dataclass
class OutputComparison:
    """Comparison result for a single file pair."""

    filename: str
    status: Literal["match", "mismatch", "missing_baseline", "missing_replica", "skip"]
    max_abs_diff: float | None = None
    rows_differ: int | None = None
    columns_differ: list[str] = field(default_factory=list)
    message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ComparisonReport:
    """
    Aggregated comparison of two output directories.

    Produced by :func:`~econflow.replication.comparator.compare_outputs`.
    """

    baseline_dir: str
    replica_dir: str
    timestamp_utc: str
    overall_status: Literal["pass", "warn", "fail"]
    numeric_tolerance: float
    comparisons: list[OutputComparison] = field(default_factory=list)

    @classmethod
    def build(
        cls,
        baseline_dir: Path,
        replica_dir: Path,
        comparisons: list[OutputComparison],
        numeric_tolerance: float = 1e-6,
    ) -> ComparisonReport:
        if any(c.status == "mismatch" for c in comparisons):
            overall = "fail"
        elif any(c.status in ("missing_replica", "missing_baseline") for c in comparisons):
            overall = "warn"
        else:
            overall = "pass"
        return cls(
            baseline_dir=str(baseline_dir),
            replica_dir=str(replica_dir),
            timestamp_utc=_utc_now(),
            overall_status=overall,
            numeric_tolerance=numeric_tolerance,
            comparisons=comparisons,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "baseline_dir": self.baseline_dir,
            "replica_dir": self.replica_dir,
            "timestamp_utc": self.timestamp_utc,
            "overall_status": self.overall_status,
            "numeric_tolerance": self.numeric_tolerance,
            "comparisons": [c.to_dict() for c in self.comparisons],
        }

    def to_json(self, *, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ComparisonReport:
        comparisons = [OutputComparison(**c) for c in data.get("comparisons", [])]
        return cls(
            baseline_dir=data["baseline_dir"],
            replica_dir=data["replica_dir"],
            timestamp_utc=data["timestamp_utc"],
            overall_status=data["overall_status"],
            numeric_tolerance=data.get("numeric_tolerance", 1e-6),
            comparisons=comparisons,
        )

    @property
    def match_count(self) -> int:
        return sum(1 for c in self.comparisons if c.status == "match")

    @property
    def mismatch_count(self) -> int:
        return sum(1 for c in self.comparisons if c.status == "mismatch")

    @property
    def missing_count(self) -> int:
        return sum(
            1 for c in self.comparisons
            if c.status in ("missing_replica", "missing_baseline")
        )
