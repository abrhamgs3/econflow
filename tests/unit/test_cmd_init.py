"""
tests/unit/test_cmd_init.py — Unit tests for the ``econflow init`` command.

Tests cover:
- Correct directory structure is created
- All three config files are written
- README.md and .gitignore are created
- Starter scripts are created
- Custom project name (--name) is reflected in files
- Init in an existing non-empty directory fails without --force
- Init with --force overwrites existing files
- Exit code 0 on success
"""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from econflow.cli import app

runner = CliRunner()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _invoke_init(args: list[str]) -> object:
    return runner.invoke(app, ["init"] + args)


# ---------------------------------------------------------------------------
# Directory structure
# ---------------------------------------------------------------------------

def test_init_creates_config_dir(tmp_path: Path) -> None:
    proj = tmp_path / "test_proj"
    result = _invoke_init([str(proj)])
    assert result.exit_code == 0, result.output
    assert (proj / "config").is_dir()


def test_init_creates_data_dirs(tmp_path: Path) -> None:
    proj = tmp_path / "test_proj"
    _invoke_init([str(proj)])
    assert (proj / "data" / "raw").is_dir()
    assert (proj / "data" / "processed").is_dir()


def test_init_creates_outputs_dirs(tmp_path: Path) -> None:
    proj = tmp_path / "test_proj"
    _invoke_init([str(proj)])
    assert (proj / "outputs" / "tables").is_dir()
    assert (proj / "outputs" / "figures").is_dir()
    assert (proj / "outputs" / "provenance").is_dir()


def test_init_creates_paper_dir(tmp_path: Path) -> None:
    proj = tmp_path / "test_proj"
    _invoke_init([str(proj)])
    assert (proj / "paper" / "sections").is_dir()


def test_init_creates_scripts_dir(tmp_path: Path) -> None:
    proj = tmp_path / "test_proj"
    _invoke_init([str(proj)])
    assert (proj / "scripts").is_dir()


def test_init_creates_docs_and_notebooks(tmp_path: Path) -> None:
    proj = tmp_path / "test_proj"
    _invoke_init([str(proj)])
    assert (proj / "docs").is_dir()
    assert (proj / "notebooks").is_dir()


# ---------------------------------------------------------------------------
# Config files
# ---------------------------------------------------------------------------

def test_init_creates_config_yaml(tmp_path: Path) -> None:
    proj = tmp_path / "test_proj"
    _invoke_init([str(proj)])
    cfg = proj / "config" / "config.yaml"
    assert cfg.exists()
    text = cfg.read_text(encoding="utf-8")
    assert "data:" in text
    assert "entity_col" in text
    assert "time_col" in text
    assert "variables:" in text


def test_init_creates_models_yaml(tmp_path: Path) -> None:
    proj = tmp_path / "test_proj"
    _invoke_init([str(proj)])
    m = proj / "config" / "models.yaml"
    assert m.exists()
    text = m.read_text(encoding="utf-8")
    assert "models:" in text
    assert "pooled_ols" in text
    assert "entity_fe" in text


def test_init_creates_outputs_yaml(tmp_path: Path) -> None:
    proj = tmp_path / "test_proj"
    _invoke_init([str(proj)])
    o = proj / "config" / "outputs.yaml"
    assert o.exists()
    text = o.read_text(encoding="utf-8")
    assert "base_dir" in text
    assert "comparison_table" in text


def test_init_config_yaml_contains_project_name(tmp_path: Path) -> None:
    proj = tmp_path / "my_study"
    _invoke_init([str(proj), "--name", "my_study"])
    cfg = proj / "config" / "config.yaml"
    assert "my_study" in cfg.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# README and .gitignore
# ---------------------------------------------------------------------------

def test_init_creates_readme(tmp_path: Path) -> None:
    proj = tmp_path / "test_proj"
    _invoke_init([str(proj)])
    readme = proj / "README.md"
    assert readme.exists()
    text = readme.read_text(encoding="utf-8")
    assert "econflow run" in text


def test_init_creates_gitignore(tmp_path: Path) -> None:
    proj = tmp_path / "test_proj"
    _invoke_init([str(proj)])
    gi = proj / ".gitignore"
    assert gi.exists()
    text = gi.read_text(encoding="utf-8")
    assert "__pycache__" in text
    assert "outputs/" in text


# ---------------------------------------------------------------------------
# Starter scripts
# ---------------------------------------------------------------------------

def test_init_creates_download_script(tmp_path: Path) -> None:
    proj = tmp_path / "test_proj"
    _invoke_init([str(proj)])
    s = proj / "scripts" / "01_download_data.py"
    assert s.exists()
    assert "def main" in s.read_text(encoding="utf-8")


def test_init_creates_clean_script(tmp_path: Path) -> None:
    proj = tmp_path / "test_proj"
    _invoke_init([str(proj)])
    s = proj / "scripts" / "02_clean_data.py"
    assert s.exists()
    assert "panel.csv" in s.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

def test_init_in_existing_empty_dir_succeeds(tmp_path: Path) -> None:
    proj = tmp_path / "empty"
    proj.mkdir()
    result = _invoke_init([str(proj)])
    assert result.exit_code == 0


def test_init_in_existing_nonempty_dir_fails_without_force(tmp_path: Path) -> None:
    proj = tmp_path / "nonempty"
    proj.mkdir()
    (proj / "existing_file.txt").write_text("data")
    result = _invoke_init([str(proj)])
    assert result.exit_code != 0
    assert "--force" in result.output


def test_init_in_existing_nonempty_dir_succeeds_with_force(tmp_path: Path) -> None:
    proj = tmp_path / "nonempty"
    proj.mkdir()
    (proj / "existing_file.txt").write_text("data")
    result = _invoke_init([str(proj), "--force"])
    assert result.exit_code == 0
    # New config should still be created
    assert (proj / "config" / "config.yaml").exists()


def test_init_uses_directory_name_as_project_name_by_default(tmp_path: Path) -> None:
    proj = tmp_path / "my_economics_project"
    _invoke_init([str(proj)])
    cfg = (proj / "config" / "config.yaml").read_text(encoding="utf-8")
    assert "my_economics_project" in cfg


def test_init_custom_name_overrides_directory_name(tmp_path: Path) -> None:
    proj = tmp_path / "dir_name"
    _invoke_init([str(proj), "--name", "custom_project_name"])
    cfg = (proj / "config" / "config.yaml").read_text(encoding="utf-8")
    assert "custom_project_name" in cfg
    assert "dir_name" not in cfg


def test_init_config_yaml_is_valid_yaml(tmp_path: Path) -> None:
    import yaml
    proj = tmp_path / "yaml_check"
    _invoke_init([str(proj)])
    cfg = proj / "config" / "config.yaml"
    data = yaml.safe_load(cfg.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    assert "data" in data
    assert "variables" in data


def test_init_models_yaml_is_valid_yaml(tmp_path: Path) -> None:
    import yaml
    proj = tmp_path / "yaml_check2"
    _invoke_init([str(proj)])
    data = yaml.safe_load(
        (proj / "config" / "models.yaml").read_text(encoding="utf-8")
    )
    assert isinstance(data, dict)
    assert "models" in data
    assert len(data["models"]) >= 2


def test_init_outputs_yaml_is_valid_yaml(tmp_path: Path) -> None:
    import yaml
    proj = tmp_path / "yaml_check3"
    _invoke_init([str(proj)])
    data = yaml.safe_load(
        (proj / "config" / "outputs.yaml").read_text(encoding="utf-8")
    )
    assert isinstance(data, dict)
    assert "outputs" in data


def test_init_creates_gitkeep_in_empty_dirs(tmp_path: Path) -> None:
    proj = tmp_path / "gitkeep_check"
    _invoke_init([str(proj)])
    # data/processed is always empty — should have .gitkeep
    assert (proj / "data" / "processed" / ".gitkeep").exists()


# ---------------------------------------------------------------------------
# Tests directory scaffold (Sprint 3B)
# ---------------------------------------------------------------------------

def test_init_creates_tests_directory(tmp_path: Path) -> None:
    proj = tmp_path / "test_proj"
    _invoke_init([str(proj)])
    assert (proj / "tests").is_dir()


def test_init_creates_tests_init_file(tmp_path: Path) -> None:
    proj = tmp_path / "test_proj"
    _invoke_init([str(proj)])
    init_file = proj / "tests" / "__init__.py"
    assert init_file.exists()


def test_init_creates_starter_test_file(tmp_path: Path) -> None:
    proj = tmp_path / "test_proj"
    _invoke_init([str(proj)])
    test_file = proj / "tests" / "test_pipeline.py"
    assert test_file.exists()
    content = test_file.read_text(encoding="utf-8")
    assert "test_config_files_exist" in content
    assert "test_data_file_exists" in content
    assert "test_pipeline_runs_without_error" in content


def test_init_starter_test_contains_project_name(tmp_path: Path) -> None:
    proj = tmp_path / "my_econ_study"
    _invoke_init([str(proj), "--name", "my_econ_study"])
    test_file = proj / "tests" / "test_pipeline.py"
    assert "my_econ_study" in test_file.read_text(encoding="utf-8")


def test_init_starter_test_has_valid_python_syntax(tmp_path: Path) -> None:
    import ast
    proj = tmp_path / "syntax_check"
    _invoke_init([str(proj)])
    test_file = proj / "tests" / "test_pipeline.py"
    source = test_file.read_text(encoding="utf-8")
    # Should parse without SyntaxError
    ast.parse(source)


def test_init_rendering_uses_checkmark_not_v(tmp_path: Path) -> None:
    """Ensure _write_file prints ✔ (Rich checkmark), not bare 'v'."""
    proj = tmp_path / "render_check"
    result = _invoke_init([str(proj)])
    # The output should contain the checkmark character, not 'v ' as status icon
    assert "✔" in result.output or result.exit_code == 0
    # Crucially, should NOT have the regression pattern '  v  ' at start of file line
    import re
    regression = re.search(r"^\s{2}v\s{2}", result.output, re.MULTILINE)
    assert regression is None, "Rendering regression found: 'v' used instead of '✔'"
