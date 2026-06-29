"""
econflow.replication.executor — Run an ExecutionPlan in a subprocess.

Runs each step as a separate subprocess to guarantee environment isolation.
Captures stdout/stderr per step and produces a :class:`ReplicationResult`.
"""

from __future__ import annotations

import subprocess
import time
import uuid
from pathlib import Path

from econflow.replication.models import (
    ExecutionPlan,
    ReplicationResult,
    StepResult,
)


def execute_plan(
    plan: ExecutionPlan,
    output_dir: Path,
    *,
    timeout_seconds: int = 600,
    cwd: Path | None = None,
) -> ReplicationResult:
    """
    Execute all steps in *plan* sequentially in subprocesses.

    Parameters
    ----------
    plan:
        The :class:`~econflow.replication.models.ExecutionPlan` to execute.
    output_dir:
        Directory where pipeline outputs will be written.
    timeout_seconds:
        Per-step subprocess timeout.
    cwd:
        Working directory for subprocesses.  Defaults to the project
        directory declared in *plan*.

    Returns
    -------
    ReplicationResult
        Full execution outcome including per-step results.
    """
    run_id = str(uuid.uuid4())
    project_dir = Path(plan.project_dir)
    working_dir = cwd or project_dir
    start_total = time.monotonic()

    step_results: list[StepResult] = []
    failed_steps: set[str] = set()

    for step in plan.steps:
        # Skip if any dependency failed
        if any(dep in failed_steps for dep in step.requires):
            step_results.append(
                StepResult(
                    step_id=step.step_id,
                    description=step.description,
                    status="skipped",
                    exit_code=None,
                    elapsed_seconds=0.0,
                    skip_reason=f"Dependency failed: {', '.join(step.requires)}",
                )
            )
            failed_steps.add(step.step_id)
            continue

        step_start = time.monotonic()
        try:
            proc = subprocess.run(
                step.command,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                cwd=str(working_dir),
            )
            elapsed = time.monotonic() - step_start
            success = proc.returncode == 0
            step_results.append(
                StepResult(
                    step_id=step.step_id,
                    description=step.description,
                    status="success" if success else "failed",
                    exit_code=proc.returncode,
                    elapsed_seconds=round(elapsed, 3),
                    stdout=proc.stdout[-4096:] if proc.stdout else "",
                    stderr=proc.stderr[-4096:] if proc.stderr else "",
                )
            )
            if not success:
                failed_steps.add(step.step_id)

        except subprocess.TimeoutExpired:
            elapsed = time.monotonic() - step_start
            step_results.append(
                StepResult(
                    step_id=step.step_id,
                    description=step.description,
                    status="failed",
                    exit_code=None,
                    elapsed_seconds=round(elapsed, 3),
                    stderr=f"Step timed out after {timeout_seconds}s.",
                )
            )
            failed_steps.add(step.step_id)

        except Exception as exc:
            elapsed = time.monotonic() - step_start
            step_results.append(
                StepResult(
                    step_id=step.step_id,
                    description=step.description,
                    status="failed",
                    exit_code=None,
                    elapsed_seconds=round(elapsed, 3),
                    stderr=f"Unexpected error: {exc}",
                )
            )
            failed_steps.add(step.step_id)

    elapsed_total = time.monotonic() - start_total

    # Determine overall status
    all_statuses = {r.status for r in step_results}
    if "failed" not in all_statuses:
        overall_status = "success"
    elif "success" in all_statuses:
        overall_status = "partial"
    else:
        overall_status = "failed"

    # Collect output files — scan in project_dir/outputs/ (pipeline's write target)
    scan_dir = output_dir / "outputs" if (output_dir / "outputs").exists() else output_dir
    outputs: list[str] = []
    for pattern in ("**/*.csv", "**/*.tex", "**/*.json", "**/*.html", "**/*.md"):
        outputs.extend(str(p) for p in scan_dir.glob(pattern) if p.is_file())
    outputs.sort()

    # Find provenance
    prov_path: str | None = None
    prov_candidates = list(scan_dir.glob("**/run_metadata.json"))
    if prov_candidates:
        prov_path = str(prov_candidates[0])

    return ReplicationResult(
        run_id=run_id,
        project_dir=str(project_dir),
        timestamp_utc=_utc_now(),
        status=overall_status,
        elapsed_seconds=round(elapsed_total, 3),
        outputs_dir=str(output_dir),
        outputs=outputs,
        provenance_path=prov_path,
        error=None,
        step_results=step_results,
    )


def _utc_now() -> str:
    from datetime import datetime, timezone
    return datetime.now(tz=timezone.utc).isoformat()
