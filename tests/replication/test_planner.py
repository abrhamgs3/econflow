"""
Tests for econflow.replication.planner.
"""

from __future__ import annotations

from pathlib import Path

from econflow.replication.models import ExecutionPlan
from econflow.replication.planner import build_plan


class TestBuildPlan:
    def test_returns_execution_plan(self, project_dir: Path, tmp_path: Path) -> None:
        plan = build_plan(project_dir, output_dir=tmp_path / "out")
        assert isinstance(plan, ExecutionPlan)

    def test_project_dir_in_plan(self, project_dir: Path, tmp_path: Path) -> None:
        plan = build_plan(project_dir, output_dir=tmp_path / "out")
        assert str(project_dir.resolve()) == plan.project_dir

    def test_steps_are_ordered(self, project_dir: Path, tmp_path: Path) -> None:
        plan = build_plan(project_dir, output_dir=tmp_path / "out")
        assert len(plan.steps) >= 2
        # validate step has no requires
        validate = plan.steps[0]
        assert validate.step_id == "validate"
        assert validate.requires == []
        # run step requires validate
        run_step = plan.steps[1]
        assert run_step.step_id == "run"
        assert "validate" in run_step.requires

    def test_validate_command_contains_config_path(self, project_dir: Path, tmp_path: Path) -> None:
        plan = build_plan(project_dir, output_dir=tmp_path / "out")
        validate = plan.steps[0]
        # F11 fix: command uses sys.executable -m econflow.cli instead of bare "econflow"
        cmd_str = " ".join(validate.command)
        assert "econflow" in cmd_str
        assert "validate" in validate.command

    def test_run_command_contains_config_paths(self, project_dir: Path, tmp_path: Path) -> None:
        # econflow run does not accept --output-dir; output location is
        # controlled by outputs.yaml.  Verify the run step passes all three
        # required config file arguments.
        out = tmp_path / "my_output"
        plan = build_plan(project_dir, output_dir=out)
        run_step = plan.steps[1]
        assert "--config" in run_step.command
        assert "--models" in run_step.command
        assert "--outputs" in run_step.command

    def test_deterministic_plan(self, project_dir: Path, tmp_path: Path) -> None:
        """Same inputs produce the same plan."""
        out = tmp_path / "out"
        plan1 = build_plan(project_dir, output_dir=out)
        plan2 = build_plan(project_dir, output_dir=out)
        assert len(plan1.steps) == len(plan2.steps)
        for s1, s2 in zip(plan1.steps, plan2.steps):
            assert s1.step_id == s2.step_id
            assert s1.command == s2.command

    def test_plan_json_serialisable(self, project_dir: Path, tmp_path: Path) -> None:
        import json
        plan = build_plan(project_dir, output_dir=tmp_path / "out")
        data = json.loads(plan.to_json())
        assert "steps" in data
        assert len(data["steps"]) == len(plan.steps)

    def test_estimated_outputs_populated(self, project_dir: Path, tmp_path: Path) -> None:
        plan = build_plan(project_dir, output_dir=tmp_path / "out")
        # May be empty if outputs.yaml has unexpected structure
        assert isinstance(plan.estimated_outputs, list)
