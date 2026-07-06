"""
tests/integration/test_workspace_lifecycle.py
=============================================

Integration tests for the `econflow init → validate → info` workflow.

These tests use real file I/O (via a tmp_path fixture) and invoke the
`run_*` functions directly without mocking filesystem operations.  They
are intentionally coarser than unit tests — they verify that the four
lifecycle commands compose correctly rather than testing every branch.
"""

from __future__ import annotations

import io
from pathlib import Path

import pytest
import yaml
from rich.console import Console

from econflow.commands.info import run_info
from econflow.commands.init import run_init
from econflow.commands.validate import run_validate

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _silent_console() -> Console:
    """Console that writes to a StringIO buffer (captured by tests)."""
    return Console(file=io.StringIO(), highlight=False)


def _output(console: Console) -> str:
    """Return everything written to the console buffer."""
    f = console.file
    assert hasattr(f, "getvalue"), "Console must use StringIO"
    return f.getvalue()


# ---------------------------------------------------------------------------
# Fixture: initialise a fresh project in a temp directory
# ---------------------------------------------------------------------------

@pytest.fixture()
def project_dir(tmp_path: Path) -> Path:
    """Run `econflow init` and return the created project directory."""
    console = _silent_console()
    exit_code = run_init(
        directory=tmp_path / "my_project",
        name="test_project",
        force=False,
        console=console,
    )
    assert exit_code == 0, f"run_init failed:\n{_output(console)}"
    return tmp_path / "my_project"


# ---------------------------------------------------------------------------
# init tests
# ---------------------------------------------------------------------------

class TestInitScaffold:
    def test_creates_project_directory(self, project_dir: Path) -> None:
        assert project_dir.is_dir()

    def test_creates_all_required_directories(self, project_dir: Path) -> None:
        required = [
            "config", "data/raw", "data/processed",
            "outputs/tables", "outputs/figures", "outputs/provenance",
            "paper/sections", "scripts", "tests", "docs", "notebooks",
        ]
        for rel in required:
            assert (project_dir / rel).is_dir(), f"Missing directory: {rel}"

    def test_creates_config_yaml(self, project_dir: Path) -> None:
        cfg_path = project_dir / "config" / "config.yaml"
        assert cfg_path.exists()
        cfg = yaml.safe_load(cfg_path.read_text())
        assert cfg["project"]["name"] == "test_project"

    def test_creates_models_yaml(self, project_dir: Path) -> None:
        path = project_dir / "config" / "models.yaml"
        assert path.exists()
        data = yaml.safe_load(path.read_text())
        assert "models" in data
        assert len(data["models"]) >= 3

    def test_creates_outputs_yaml(self, project_dir: Path) -> None:
        path = project_dir / "config" / "outputs.yaml"
        assert path.exists()
        data = yaml.safe_load(path.read_text())
        assert "outputs" in data

    def test_creates_tests_package(self, project_dir: Path) -> None:
        assert (project_dir / "tests" / "__init__.py").exists()

    def test_creates_starter_test(self, project_dir: Path) -> None:
        test_file = project_dir / "tests" / "test_pipeline.py"
        assert test_file.exists()
        content = test_file.read_text()
        assert "test_config_files_exist" in content

    def test_creates_scripts(self, project_dir: Path) -> None:
        assert (project_dir / "scripts" / "01_download_data.py").exists()
        assert (project_dir / "scripts" / "02_clean_data.py").exists()

    def test_creates_readme(self, project_dir: Path) -> None:
        readme = project_dir / "README.md"
        assert readme.exists()
        assert "test_project" in readme.read_text()

    def test_creates_gitignore(self, project_dir: Path) -> None:
        assert (project_dir / ".gitignore").exists()

    def test_creates_gitkeep_in_empty_dirs(self, project_dir: Path) -> None:
        # data/processed has no CSV yet — .gitkeep should be present
        assert (project_dir / "data" / "processed" / ".gitkeep").exists()

    def test_force_overwrites_existing_file(self, tmp_path: Path) -> None:
        dest = tmp_path / "overwrite_test"
        console = _silent_console()
        run_init(directory=dest, name="first", force=False, console=console)

        # Second init without --force should refuse
        console2 = _silent_console()
        code = run_init(directory=dest, name="second", force=False, console=console2)
        assert code == 1

        # With --force it should succeed
        console3 = _silent_console()
        code = run_init(directory=dest, name="second", force=True, console=console3)
        assert code == 0

    def test_name_defaults_to_directory_basename(self, tmp_path: Path) -> None:
        dest = tmp_path / "my_study"
        console = _silent_console()
        run_init(directory=dest, name="", force=False, console=console)
        cfg = yaml.safe_load((dest / "config" / "config.yaml").read_text())
        assert cfg["project"]["name"] == "my_study"


# ---------------------------------------------------------------------------
# validate tests (on freshly init'd project)
# ---------------------------------------------------------------------------

class TestValidateAfterInit:
    def test_validate_passes_on_fresh_project(self, project_dir: Path) -> None:
        console = _silent_console()
        code = run_validate(
            config_path=project_dir / "config" / "config.yaml",
            models_path=project_dir / "config" / "models.yaml",
            outputs_path=project_dir / "config" / "outputs.yaml",
            check_data=False,
            console=console,
        )
        assert code == 0, f"validate failed on fresh project:\n{_output(console)}"

    def test_validate_with_data_flag_warns_when_no_csv(self, project_dir: Path) -> None:
        """--data should warn/fail about missing panel CSV on fresh project."""
        console = _silent_console()
        code = run_validate(
            config_path=project_dir / "config" / "config.yaml",
            models_path=project_dir / "config" / "models.yaml",
            outputs_path=project_dir / "config" / "outputs.yaml",
            check_data=True,
            console=console,
        )
        # Data file doesn't exist — should fail (non-zero)
        assert code != 0

    def test_validate_fails_when_config_missing_required_key(
        self, project_dir: Path
    ) -> None:
        cfg_path = project_dir / "config" / "config.yaml"
        # Remove the dependent variable key
        cfg = yaml.safe_load(cfg_path.read_text())
        del cfg["variables"]["dependent"]
        cfg_path.write_text(yaml.dump(cfg))

        console = _silent_console()
        code = run_validate(
            config_path=cfg_path,
            models_path=project_dir / "config" / "models.yaml",
            outputs_path=project_dir / "config" / "outputs.yaml",
            check_data=False,
            console=console,
        )
        assert code != 0

    def test_validate_fails_when_models_yaml_is_empty(
        self, project_dir: Path
    ) -> None:
        models_path = project_dir / "config" / "models.yaml"
        models_path.write_text("models: []\n")

        console = _silent_console()
        code = run_validate(
            config_path=project_dir / "config" / "config.yaml",
            models_path=models_path,
            outputs_path=project_dir / "config" / "outputs.yaml",
            check_data=False,
            console=console,
        )
        assert code != 0


# ---------------------------------------------------------------------------
# info tests (on freshly init'd project)
# ---------------------------------------------------------------------------

class TestInfoAfterInit:
    def test_info_exits_zero_with_config(self, project_dir: Path) -> None:
        console = _silent_console()
        code = run_info(
            config_path=project_dir / "config" / "config.yaml",
            models_path=project_dir / "config" / "models.yaml",
            outputs_path=project_dir / "config" / "outputs.yaml",
            console=console,
        )
        assert code == 0

    def test_info_shows_project_name(self, project_dir: Path) -> None:
        console = _silent_console()
        run_info(
            config_path=project_dir / "config" / "config.yaml",
            models_path=project_dir / "config" / "models.yaml",
            outputs_path=project_dir / "config" / "outputs.yaml",
            console=console,
        )
        out = _output(console)
        assert "test_project" in out

    def test_info_shows_estimator_registry(self, project_dir: Path) -> None:
        console = _silent_console()
        run_info(
            config_path=project_dir / "config" / "config.yaml",
            models_path=project_dir / "config" / "models.yaml",
            outputs_path=project_dir / "config" / "outputs.yaml",
            console=console,
        )
        out = _output(console)
        assert "OLS" in out
        assert "FE" in out

    def test_info_shows_platform_section(self, project_dir: Path) -> None:
        console = _silent_console()
        run_info(
            config_path=project_dir / "config" / "config.yaml",
            models_path=project_dir / "config" / "models.yaml",
            outputs_path=project_dir / "config" / "outputs.yaml",
            console=console,
        )
        out = _output(console)
        assert "Python" in out

    def test_info_shows_no_provenance_on_fresh_project(
        self, project_dir: Path
    ) -> None:
        console = _silent_console()
        run_info(
            config_path=project_dir / "config" / "config.yaml",
            models_path=project_dir / "config" / "models.yaml",
            outputs_path=project_dir / "config" / "outputs.yaml",
            console=console,
        )
        out = _output(console)
        assert "No provenance" in out or "no record" in out.lower()
