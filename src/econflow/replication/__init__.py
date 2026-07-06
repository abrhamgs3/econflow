"""
econflow.replication — Automatic replication engine for EconFlow projects.

The replication engine provides three capabilities:

1. **Inspection** — pre-flight checks that verify a project directory can
   be reproduced before execution begins.
2. **Execution** — subprocess-isolated replication of a project's analysis
   pipeline.
3. **Comparison** — toleranced, file-type-aware comparison of original and
   reproduced outputs.

Public API
----------
::

    from econflow.replication import (
        # Inspection
        inspect_project,
        InspectionReport,
        ProjectCheck,
        # Planning
        build_plan,
        ExecutionPlan,
        ExecutionStep,
        # Execution
        execute_plan,
        ReplicationResult,
        StepResult,
        # Comparison
        compare_outputs,
        ComparisonReport,
        OutputComparison,
        # Reporting
        ReproducibilityReport,
        DEFAULT_TOLERANCE,
    )

CLI
---
    econflow inspect <project_dir>
    econflow reproduce <project_dir>
    econflow compare <baseline_dir> <replica_dir>
"""

from __future__ import annotations

from econflow.replication.comparator import DEFAULT_TOLERANCE, compare_outputs
from econflow.replication.executor import execute_plan
from econflow.replication.inspector import inspect_project
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
from econflow.replication.planner import build_plan
from econflow.replication.reporter import ReproducibilityReport

__all__ = [
    # Inspection
    "inspect_project",
    "InspectionReport",
    "ProjectCheck",
    # Planning
    "build_plan",
    "ExecutionPlan",
    "ExecutionStep",
    # Execution
    "execute_plan",
    "ReplicationResult",
    "StepResult",
    # Comparison
    "compare_outputs",
    "ComparisonReport",
    "OutputComparison",
    "DEFAULT_TOLERANCE",
    # Reporting
    "ReproducibilityReport",
]
