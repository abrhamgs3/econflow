"""
econflow.replication.planner — Build an :class:`ExecutionPlan` for a project.

Reads the project's configuration files and constructs a deterministic, ordered
list of steps required to reproduce its outputs.
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

from econflow.replication.models import ExecutionPlan, ExecutionStep

# Candidate relative paths for each config file
_CONFIG_CANDIDATES = [Path("config") / "config.yaml", Path("config.yaml")]
_MODELS_CANDIDATES = [Path("config") / "models.yaml", Path("models.yaml")]
_OUTPUTS_CANDIDATES = [Path("config") / "outputs.yaml", Path("outputs.yaml")]


def _econflow_cmd() -> list[str]:
    """
    Return a command prefix that reliably invokes the EconFlow CLI.

    Uses ``sys.executable -m econflow.cli`` rather than the bare ``econflow``
    entry-point script so that replication works correctly even when the
    caller activates a virtualenv's executable directly (e.g. in CI or when
    the venv Scripts/ directory is not on PATH).  This avoids the
    ``WinError 2 [FileNotFoundError]`` that occurs on Windows when ``econflow``
    is not on the system PATH but the venv executable is invoked directly.
    """
    return [sys.executable, "-m", "econflow.cli"]


def _find_file(project_dir: Path, candidates: list[Path]) -> Path | None:
    for rel in candidates:
        p = project_dir / rel
        if p.exists():
            return p
    return None


def _load_yaml(path: Path) -> dict:
    with path.open() as f:
        return yaml.safe_load(f) or {}


def build_plan(project_dir: Path, output_dir: Path) -> ExecutionPlan:
    """
    Build a deterministic :class:`ExecutionPlan` for *project_dir*.

    Parameters
    ----------
    project_dir:
        Root of the EconFlow project to reproduce.
    output_dir:
        Destination for replication outputs (must not be the project's
        own ``outputs/`` directory to avoid overwriting originals).

    Returns
    -------
    ExecutionPlan
        Ordered steps to reproduce the project.
    """
    project_dir = project_dir.resolve()
    output_dir = output_dir.resolve()

    config_path = _find_file(project_dir, _CONFIG_CANDIDATES)
    models_path = _find_file(project_dir, _MODELS_CANDIDATES)
    outputs_path = _find_file(project_dir, _OUTPUTS_CANDIDATES)

    cmd = _econflow_cmd()
    steps: list[ExecutionStep] = []
    estimated_outputs: list[str] = []

    # ---- Step 1: Validate -----------------------------------------------
    steps.append(
        ExecutionStep(
            step_id="validate",
            description="Validate project configuration",
            command=cmd + [
                "validate",
                "--config", str(config_path or project_dir / "config" / "config.yaml"),
            ],
            requires=[],
        )
    )

    # ---- Step 2: Run pipeline -------------------------------------------
    if config_path and models_path and outputs_path:
        steps.append(
            ExecutionStep(
                step_id="run",
                description="Execute analysis pipeline",
                command=cmd + [
                    "run",
                    "--config", str(config_path),
                    "--models", str(models_path),
                    "--outputs", str(outputs_path),
                ],
                requires=["validate"],
            )
        )
    else:
        # Fallback: attempt to run with whatever config exists
        steps.append(
            ExecutionStep(
                step_id="run",
                description="Execute analysis pipeline (partial config)",
                command=cmd + [
                    "run",
                    "--config", str(config_path or project_dir / "config" / "config.yaml"),
                ],
                requires=["validate"],
            )
        )

    # ---- Estimate outputs -----------------------------------------------
    if outputs_path:
        try:
            out_cfg = _load_yaml(outputs_path)
            tables_dir = out_cfg.get("outputs", {}).get("tables", {}).get("dir", "tables")
            filename = (
                out_cfg
                .get("outputs", {})
                .get("tables", {})
                .get("comparison_table", {})
                .get("filename", "comparison_table.csv")
            )
            estimated_outputs.append(str(output_dir / tables_dir / filename))
        except Exception:
            pass

    return ExecutionPlan(
        project_dir=str(project_dir),
        steps=steps,
        estimated_outputs=estimated_outputs,
    )
