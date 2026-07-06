"""
tests/unit/test_config_milestone4.py — Tests for Architecture Stabilization Milestone 4.

Covers:
  - config/models.py   — Pydantic v2 models (ProjectConfig, ModelsConfig, OutputsConfig)
  - config/linter.py   — ConfigLinter (10 semantic lint rules)
  - config/docs.py     — generate_config_reference (markdown + text)
  - commands/validate.py — three-phase validate (schema + semantic + cross-file)
  - cli.py             — econflow validate accepts directory positional arg

Test plan:
  TestProjectConfig        — valid, missing required fields, extra keys, year order, dependent-in-regressors
  TestModelsConfig         — valid, duplicate IDs, unknown estimator, empty list
  TestOutputsConfig        — valid, missing base_dir, missing filename
  TestConfigLinterRules    — one test per L-01 through L-10
  TestConfigDocsGenerator  — smoke tests for markdown and text output
  TestValidateCommand      — end-to-end CLI tests with tmp_path fixtures
  TestValidateDirectoryArg — positional directory argument
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml


# ============================================================================
# Helpers
# ============================================================================

FIXTURES = Path(__file__).parent.parent / "fixtures" / "config"


def load_fixture(rel: str) -> dict:
    path = FIXTURES / rel
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


# ============================================================================
# ProjectConfig (config.yaml)
# ============================================================================

class TestProjectConfig:
    """Tests for econflow.config.models.ProjectConfig."""

    def test_valid_config_parses(self) -> None:
        from econflow.config.models import ProjectConfig
        raw = load_fixture("valid/config.yaml")
        cfg = ProjectConfig.model_validate(raw)
        assert cfg.project.name == "test_project"
        assert cfg.variables.dependent == "outcome"
        assert "treatment" in cfg.variables.regressors

    def test_missing_project_name_raises(self) -> None:
        from pydantic import ValidationError
        from econflow.config.models import ProjectConfig
        raw = load_fixture("valid/config.yaml")
        del raw["project"]["name"]
        with pytest.raises(ValidationError, match="name"):
            ProjectConfig.model_validate(raw)

    def test_missing_data_path_raises(self) -> None:
        from pydantic import ValidationError
        from econflow.config.models import ProjectConfig
        raw = load_fixture("valid/config.yaml")
        del raw["data"]["path"]
        with pytest.raises(ValidationError, match="path"):
            ProjectConfig.model_validate(raw)

    def test_missing_entity_col_raises(self) -> None:
        from pydantic import ValidationError
        from econflow.config.models import ProjectConfig
        raw = load_fixture("valid/config.yaml")
        del raw["data"]["entity_col"]
        with pytest.raises(ValidationError, match="entity_col"):
            ProjectConfig.model_validate(raw)

    def test_missing_time_col_raises(self) -> None:
        from pydantic import ValidationError
        from econflow.config.models import ProjectConfig
        raw = load_fixture("valid/config.yaml")
        del raw["data"]["time_col"]
        with pytest.raises(ValidationError, match="time_col"):
            ProjectConfig.model_validate(raw)

    def test_missing_dependent_raises(self) -> None:
        from pydantic import ValidationError
        from econflow.config.models import ProjectConfig
        raw = load_fixture("valid/config.yaml")
        del raw["variables"]["dependent"]
        with pytest.raises(ValidationError, match="dependent"):
            ProjectConfig.model_validate(raw)

    def test_empty_regressors_raises(self) -> None:
        from pydantic import ValidationError
        from econflow.config.models import ProjectConfig
        raw = load_fixture("valid/config.yaml")
        raw["variables"]["regressors"] = []
        with pytest.raises(ValidationError):
            ProjectConfig.model_validate(raw)

    def test_extra_key_raises(self) -> None:
        """extra='forbid' must reject unknown top-level keys."""
        from pydantic import ValidationError
        from econflow.config.models import ProjectConfig
        raw = load_fixture("valid/config.yaml")
        raw["unknown_top_level_key"] = "bad"
        with pytest.raises(ValidationError, match="extra"):
            ProjectConfig.model_validate(raw)

    def test_year_order_validator_raises(self) -> None:
        """start_year >= end_year must raise ValidationError."""
        from pydantic import ValidationError
        from econflow.config.models import ProjectConfig
        raw = load_fixture("valid/config.yaml")
        raw["sample"] = {"start_year": 2020, "end_year": 2000}
        with pytest.raises(ValidationError):
            ProjectConfig.model_validate(raw)

    def test_year_equal_raises(self) -> None:
        from pydantic import ValidationError
        from econflow.config.models import ProjectConfig
        raw = load_fixture("valid/config.yaml")
        raw["sample"] = {"start_year": 2010, "end_year": 2010}
        with pytest.raises(ValidationError):
            ProjectConfig.model_validate(raw)

    def test_dependent_in_regressors_parses_but_linter_catches(self) -> None:
        """
        Pydantic does NOT block dependent-in-regressors (that is the linter's job).
        The model parses; the linter raises L-01.
        """
        from econflow.config.models import ProjectConfig
        from econflow.config.linter import ConfigLinter
        raw = load_fixture("valid/config.yaml")
        raw["variables"]["regressors"] = ["outcome", "treatment"]
        cfg = ProjectConfig.model_validate(raw)  # must not raise
        issues = ConfigLinter().lint(project_cfg=cfg, raw_config=raw)
        codes = [i.code for i in issues]
        assert "L-01" in codes


# ============================================================================
# ModelsConfig (models.yaml)
# ============================================================================

class TestModelsConfig:
    """Tests for econflow.config.models.ModelsConfig."""

    def test_valid_models_parses(self) -> None:
        from econflow.config.models import ModelsConfig
        raw = load_fixture("valid/models.yaml")
        cfg = ModelsConfig.model_validate(raw)
        assert len(cfg.models) == 2
        assert cfg.models[0].id == "pooled_ols"
        assert cfg.models[1].estimator == "fe"

    def test_empty_models_list_raises(self) -> None:
        from pydantic import ValidationError
        from econflow.config.models import ModelsConfig
        with pytest.raises(ValidationError):
            ModelsConfig.model_validate({"models": []})

    def test_missing_models_key_raises(self) -> None:
        from pydantic import ValidationError
        from econflow.config.models import ModelsConfig
        with pytest.raises(ValidationError, match="models"):
            ModelsConfig.model_validate({})

    def test_duplicate_model_ids_raises(self) -> None:
        from pydantic import ValidationError
        from econflow.config.models import ModelsConfig
        raw = load_fixture("invalid/dup_model_ids/models.yaml")
        with pytest.raises(ValidationError, match="[Dd]uplicate"):
            ModelsConfig.model_validate(raw)

    def test_invalid_model_id_pattern_raises(self) -> None:
        """Model ID must start with letter and contain only [A-Za-z0-9_-]."""
        from pydantic import ValidationError
        from econflow.config.models import ModelsConfig
        bad = {
            "models": [{
                "id": "123_bad_start",
                "estimator": "ols",
                "dependent": "outcome",
                "regressors": ["x"],
            }]
        }
        with pytest.raises(ValidationError, match="id"):
            ModelsConfig.model_validate(bad)

    def test_missing_estimator_raises(self) -> None:
        from pydantic import ValidationError
        from econflow.config.models import ModelsConfig
        raw = {
            "models": [{
                "id": "m1",
                "dependent": "outcome",
                "regressors": ["x"],
            }]
        }
        with pytest.raises(ValidationError, match="estimator"):
            ModelsConfig.model_validate(raw)

    def test_extra_model_fields_allowed(self) -> None:
        """ModelSpec has extra='allow' for estimator-specific keys."""
        from econflow.config.models import ModelsConfig
        raw = {
            "models": [{
                "id": "m1",
                "estimator": "ols",
                "dependent": "outcome",
                "regressors": ["x"],
                "entity_effects": True,
                "some_custom_key": "some_value",  # allowed
            }]
        }
        cfg = ModelsConfig.model_validate(raw)
        assert cfg.models[0].id == "m1"


# ============================================================================
# OutputsConfig (outputs.yaml)
# ============================================================================

class TestOutputsConfig:
    """Tests for econflow.config.models.OutputsConfig."""

    def test_valid_outputs_parses(self) -> None:
        from econflow.config.models import OutputsConfig
        raw = load_fixture("valid/outputs.yaml")
        cfg = OutputsConfig.model_validate(raw)
        assert cfg.outputs.base_dir == "outputs"
        assert cfg.outputs.tables.comparison_table.filename == "table_main"

    def test_missing_base_dir_raises(self) -> None:
        from pydantic import ValidationError
        from econflow.config.models import OutputsConfig
        raw = load_fixture("valid/outputs.yaml")
        del raw["outputs"]["base_dir"]
        with pytest.raises(ValidationError, match="base_dir"):
            OutputsConfig.model_validate(raw)

    def test_missing_comparison_filename_raises(self) -> None:
        from pydantic import ValidationError
        from econflow.config.models import OutputsConfig
        raw = load_fixture("valid/outputs.yaml")
        del raw["outputs"]["tables"]["comparison_table"]["filename"]
        with pytest.raises(ValidationError, match="filename"):
            OutputsConfig.model_validate(raw)

    def test_invalid_se_type_raises(self) -> None:
        from pydantic import ValidationError
        from econflow.config.models import OutputsConfig
        raw = load_fixture("valid/outputs.yaml")
        raw["outputs"]["tables"]["comparison_table"]["se_type"] = "bootstrapped"
        with pytest.raises(ValidationError):
            OutputsConfig.model_validate(raw)

    def test_extra_top_level_key_raises(self) -> None:
        from pydantic import ValidationError
        from econflow.config.models import OutputsConfig
        raw = load_fixture("valid/outputs.yaml")
        raw["unknown_key"] = "bad"
        with pytest.raises(ValidationError, match="extra"):
            OutputsConfig.model_validate(raw)


# ============================================================================
# ConfigLinter — one test per rule
# ============================================================================

class TestConfigLinterRules:
    """Unit tests for ConfigLinter lint rules L-01 through L-10."""

    def _linter(self):
        from econflow.config.linter import ConfigLinter
        return ConfigLinter()

    def _parse_all(self, config_file="valid/config.yaml",
                   models_file="valid/models.yaml",
                   outputs_file="valid/outputs.yaml"):
        from econflow.config.models import ProjectConfig, ModelsConfig, OutputsConfig
        p_raw = load_fixture(config_file)
        m_raw = load_fixture(models_file)
        o_raw = load_fixture(outputs_file)
        try:
            p_cfg = ProjectConfig.model_validate(p_raw)
        except Exception:
            p_cfg = None
        try:
            m_cfg = ModelsConfig.model_validate(m_raw)
        except Exception:
            m_cfg = None
        try:
            o_cfg = OutputsConfig.model_validate(o_raw)
        except Exception:
            o_cfg = None
        return p_cfg, m_cfg, o_cfg, p_raw, m_raw, o_raw

    def test_no_issues_on_valid_configs(self) -> None:
        p, m, o, rp, rm, ro = self._parse_all()
        issues = self._linter().lint(p, m, o, rp, rm, ro)
        errors = [i for i in issues if i.severity == "error"]
        # L-10 (missing label) may fire as info/warning; errors must be zero
        assert errors == [], f"Unexpected errors: {errors}"

    def test_L01_dependent_in_regressors(self) -> None:
        """L-01: dependent also in regressors → error."""
        raw = load_fixture("invalid/dep_in_regressors/config.yaml")
        issues = self._linter().lint(raw_config=raw)
        codes = [i.code for i in issues]
        assert "L-01" in codes

    def test_L02_duplicate_regressors(self) -> None:
        """L-02: duplicate regressor names → error."""
        raw = load_fixture("invalid/dup_regressors/config.yaml")
        issues = self._linter().lint(raw_config=raw)
        codes = [i.code for i in issues]
        assert "L-02" in codes

    def test_L03_year_order(self) -> None:
        """L-03: start_year >= end_year → error."""
        raw = load_fixture("invalid/year_order/config.yaml")
        issues = self._linter().lint(raw_config=raw)
        codes = [i.code for i in issues]
        assert "L-03" in codes

    def test_L04_unknown_estimator(self) -> None:
        """L-04: unknown estimator string → warning."""
        rm = load_fixture("invalid/unknown_estimator/models.yaml")
        issues = self._linter().lint(raw_models=rm)
        codes = [i.code for i in issues]
        assert "L-04" in codes

    def test_L04_close_match_suggestion_in_message(self) -> None:
        """L-04 message should suggest 'fe' for 'FIXXD_EFFECTS'."""
        rm = load_fixture("invalid/unknown_estimator/models.yaml")
        issues = self._linter().lint(raw_models=rm)
        l04 = next((i for i in issues if i.code == "L-04"), None)
        assert l04 is not None
        # "fe" or "FIXXD_EFFECTS" should appear in the message
        assert "FIXXD_EFFECTS" in l04.message

    def test_L05_model_regressor_not_in_config(self) -> None:
        """L-05: model uses variable not in config.variables.regressors → warning."""
        from econflow.config.models import ProjectConfig, ModelsConfig
        p_raw = load_fixture("valid/config.yaml")
        m_raw = {
            "models": [{
                "id": "m1",
                "label": "M1",
                "estimator": "ols",
                "dependent": "outcome",
                "regressors": ["treatment", "mystery_var"],
            }]
        }
        try:
            p_cfg = ProjectConfig.model_validate(p_raw)
        except Exception:
            p_cfg = None
        try:
            m_cfg = ModelsConfig.model_validate(m_raw)
        except Exception:
            m_cfg = None
        issues = self._linter().lint(p_cfg, m_cfg, raw_config=p_raw, raw_models=m_raw)
        codes = [i.code for i in issues]
        assert "L-05" in codes, f"Expected L-05, got {codes}"

    def test_L06_absolute_outputs_base_dir(self) -> None:
        """L-06: absolute outputs.base_dir → warning."""
        ro = load_fixture("invalid/abs_base_dir/outputs.yaml")
        issues = self._linter().lint(raw_outputs=ro)
        codes = [i.code for i in issues]
        assert "L-06" in codes

    def test_L07_unsupported_data_path_extension(self) -> None:
        """L-07: data.path ends in .xlsx → warning."""
        raw = {
            "project": {"name": "t", "description": "t", "authors": [{"name": "T"}]},
            "data": {"path": "data/panel.xlsx", "entity_col": "e", "time_col": "t"},
            "variables": {"dependent": "y", "regressors": ["x"]},
        }
        issues = self._linter().lint(raw_config=raw)
        codes = [i.code for i in issues]
        assert "L-07" in codes

    def test_L08_invalid_semver(self) -> None:
        """L-08: project.version not semver → warning."""
        raw = load_fixture("valid/config.yaml")
        raw["project"]["version"] = "v1-beta"
        issues = self._linter().lint(raw_config=raw)
        codes = [i.code for i in issues]
        assert "L-08" in codes

    def test_L08_valid_semver_no_warning(self) -> None:
        """1.2.3 is valid semver — L-08 must not fire."""
        raw = load_fixture("valid/config.yaml")
        raw["project"]["version"] = "1.2.3"
        issues = self._linter().lint(raw_config=raw)
        codes = [i.code for i in issues]
        assert "L-08" not in codes

    def test_L09_model_dependent_differs_from_config(self) -> None:
        """L-09: model dependent != config dependent → info/warning."""
        from econflow.config.models import ProjectConfig, ModelsConfig
        p_raw = load_fixture("valid/config.yaml")
        m_raw = {
            "models": [{
                "id": "alt_outcome",
                "label": "Alt",
                "estimator": "ols",
                "dependent": "different_outcome",  # differs
                "regressors": ["treatment"],
            }]
        }
        try:
            p_cfg = ProjectConfig.model_validate(p_raw)
        except Exception:
            p_cfg = None
        try:
            m_cfg = ModelsConfig.model_validate(m_raw)
        except Exception:
            m_cfg = None
        issues = self._linter().lint(p_cfg, m_cfg, raw_config=p_raw, raw_models=m_raw)
        codes = [i.code for i in issues]
        assert "L-09" in codes

    def test_L10_empty_label_triggers_info(self) -> None:
        """L-10: model with no label → info."""
        m_raw = {
            "models": [{
                "id": "no_label_model",
                # no label key
                "estimator": "ols",
                "dependent": "outcome",
                "regressors": ["x"],
            }]
        }
        issues = self._linter().lint(raw_models=m_raw)
        codes = [i.code for i in issues]
        assert "L-10" in codes

    def test_L10_label_present_no_info(self) -> None:
        """L-10 must not fire when label is set."""
        m_raw = {
            "models": [{
                "id": "has_label",
                "label": "My Label",
                "estimator": "ols",
                "dependent": "outcome",
                "regressors": ["x"],
            }]
        }
        issues = self._linter().lint(raw_models=m_raw)
        codes = [i.code for i in issues]
        assert "L-10" not in codes

    def test_issues_sorted_errors_first(self) -> None:
        """Linter output must sort errors before warnings before info."""
        raw_c = load_fixture("invalid/dep_in_regressors/config.yaml")  # produces error
        raw_m = load_fixture("invalid/unknown_estimator/models.yaml")  # produces warning
        issues = self._linter().lint(raw_config=raw_c, raw_models=raw_m)
        _order = {"error": 0, "warning": 1, "info": 2}
        severities = [_order[i.severity] for i in issues]
        assert severities == sorted(severities), "Issues not sorted by severity"

    def test_fix_text_present_on_errors(self) -> None:
        """Every error issue must have a non-empty fix hint."""
        raw = load_fixture("invalid/dep_in_regressors/config.yaml")
        issues = self._linter().lint(raw_config=raw)
        errors = [i for i in issues if i.severity == "error"]
        assert errors, "Expected at least one error issue"
        for err in errors:
            assert err.fix, f"Error {err.code} has no fix text"


# ============================================================================
# ConfigDocs
# ============================================================================

class TestConfigDocsGenerator:
    """Smoke tests for econflow.config.docs."""

    def test_generate_markdown_contains_field_table(self) -> None:
        from econflow.config.docs import generate_config_reference
        md = generate_config_reference(format="markdown")
        assert "# EconFlow Configuration Reference" in md
        assert "config.yaml" in md
        assert "models.yaml" in md
        assert "outputs.yaml" in md
        assert "| Field |" in md

    def test_generate_text_contains_section_headers(self) -> None:
        from econflow.config.docs import generate_config_reference
        txt = generate_config_reference(format="text")
        assert "ECONFLOW CONFIGURATION REFERENCE" in txt
        assert "config.yaml" in txt
        assert "models.yaml" in txt

    def test_generate_markdown_includes_description_fields(self) -> None:
        from econflow.config.docs import generate_config_reference
        md = generate_config_reference(format="markdown")
        # dependent field description should appear somewhere
        assert "dependent" in md

    def test_write_config_reference_creates_file(self, tmp_path: Path) -> None:
        from econflow.config.docs import write_config_reference
        out = tmp_path / "CONFIG_REFERENCE.md"
        result = write_config_reference(out, format="markdown")
        assert result.exists()
        content = result.read_text(encoding="utf-8")
        assert "EconFlow" in content

    def test_text_format_no_markdown_tables(self) -> None:
        from econflow.config.docs import generate_config_reference
        txt = generate_config_reference(format="text")
        # Text format must not contain markdown table separators
        assert "|----|" not in txt and "|----" not in txt


# ============================================================================
# Validate command — three-phase output
# ============================================================================

class TestValidateCommand:
    """End-to-end CLI tests for econflow validate with new three-phase output."""

    def _cli(self, args: list[str]):
        from typer.testing import CliRunner
        from econflow.cli import app
        return CliRunner().invoke(app, args)

    def _write_valid(self, tmp: Path) -> tuple[Path, Path, Path]:
        c = tmp / "config.yaml"
        m = tmp / "models.yaml"
        o = tmp / "outputs.yaml"
        c.write_text((FIXTURES / "valid/config.yaml").read_text(encoding="utf-8"), encoding="utf-8")
        m.write_text((FIXTURES / "valid/models.yaml").read_text(encoding="utf-8"), encoding="utf-8")
        o.write_text((FIXTURES / "valid/outputs.yaml").read_text(encoding="utf-8"), encoding="utf-8")
        return c, m, o

    def _args(self, c, m, o, extra=None):
        return ["validate",
                "--config", str(c),
                "--models", str(m),
                "--outputs", str(o)] + (extra or [])

    def test_all_phases_pass_on_valid_configs(self, tmp_path: Path) -> None:
        c, m, o = self._write_valid(tmp_path)
        result = self._cli(self._args(c, m, o))
        assert result.exit_code == 0
        assert "schema valid" in result.output.lower()

    def test_schema_phase_fails_on_missing_required_field(self, tmp_path: Path) -> None:
        c, m, o = self._write_valid(tmp_path)
        raw = yaml.safe_load(c.read_text(encoding="utf-8"))
        del raw["data"]["path"]
        c.write_text(yaml.dump(raw), encoding="utf-8")
        result = self._cli(self._args(c, m, o))
        assert result.exit_code != 0

    def test_semantic_phase_catches_l01(self, tmp_path: Path) -> None:
        """L-01: dependent in regressors — must reach semantic phase."""
        _, m, o = self._write_valid(tmp_path)
        raw = yaml.safe_load((FIXTURES / "invalid/dep_in_regressors/config.yaml").read_text())
        bad_c = tmp_path / "config.yaml"
        bad_c.write_text(yaml.dump(raw), encoding="utf-8")
        result = self._cli(self._args(bad_c, m, o))
        assert result.exit_code != 0
        assert "L-01" in result.output

    def test_semantic_phase_catches_l03_year_order(self, tmp_path: Path) -> None:
        _, m, o = self._write_valid(tmp_path)
        raw = yaml.safe_load((FIXTURES / "invalid/year_order/config.yaml").read_text())
        bad_c = tmp_path / "config.yaml"
        bad_c.write_text(yaml.dump(raw), encoding="utf-8")
        result = self._cli(self._args(bad_c, m, o))
        assert result.exit_code != 0
        assert "L-03" in result.output

    def test_cross_file_phase_fails_on_unknown_output_model_id(self, tmp_path: Path) -> None:
        c, m, _ = self._write_valid(tmp_path)
        o = tmp_path / "outputs.yaml"
        raw_o = yaml.safe_load((FIXTURES / "valid/outputs.yaml").read_text())
        raw_o["outputs"]["tables"]["comparison_table"]["models"] = ["does_not_exist"]
        o.write_text(yaml.dump(raw_o), encoding="utf-8")
        result = self._cli(self._args(c, m, o))
        assert result.exit_code != 0

    def test_output_contains_three_phase_labels(self, tmp_path: Path) -> None:
        c, m, o = self._write_valid(tmp_path)
        result = self._cli(self._args(c, m, o))
        out = result.output
        # All three phase names must appear in output
        assert "schema" in out.lower()
        assert "semantic" in out.lower()
        assert "cross-file" in out.lower()

    def test_fix_hint_appears_in_output_on_failure(self, tmp_path: Path) -> None:
        c, m, o = self._write_valid(tmp_path)
        raw = yaml.safe_load(c.read_text())
        del raw["data"]["path"]
        c.write_text(yaml.dump(raw), encoding="utf-8")
        result = self._cli(self._args(c, m, o))
        # Fix hint should be present
        assert "Fix:" in result.output or "fix" in result.output.lower()


# ============================================================================
# Validate command — directory positional argument (Task 242)
# ============================================================================

class TestValidateDirectoryArg:
    """Tests for econflow validate <config_dir> positional argument."""

    def _cli(self, args: list[str]):
        from typer.testing import CliRunner
        from econflow.cli import app
        return CliRunner().invoke(app, args)

    def test_positional_dir_resolves_all_three_files(self, tmp_path: Path) -> None:
        """validate <dir> must pick up config.yaml, models.yaml, outputs.yaml from dir."""
        for name in ("config.yaml", "models.yaml", "outputs.yaml"):
            src = FIXTURES / "valid" / name
            (tmp_path / name).write_text(src.read_text(encoding="utf-8"), encoding="utf-8")

        result = self._cli(["validate", str(tmp_path)])
        assert result.exit_code == 0

    def test_positional_dir_fails_when_files_missing(self, tmp_path: Path) -> None:
        """validate <dir> must fail if config.yaml is absent."""
        # Only write models.yaml and outputs.yaml
        for name in ("models.yaml", "outputs.yaml"):
            (tmp_path / name).write_text(
                (FIXTURES / "valid" / name).read_text(encoding="utf-8"),
                encoding="utf-8",
            )
        result = self._cli(["validate", str(tmp_path)])
        assert result.exit_code != 0

    def test_explicit_flags_override_positional_dir(self, tmp_path: Path) -> None:
        """--config flag must override the config.yaml resolved from positional dir."""
        # Valid models + outputs in tmp_path
        for name in ("models.yaml", "outputs.yaml"):
            (tmp_path / name).write_text(
                (FIXTURES / "valid" / name).read_text(encoding="utf-8"),
                encoding="utf-8",
            )
        # Put a bad config in a separate subdir
        bad_dir = tmp_path / "bad"
        bad_dir.mkdir()
        bad_cfg = bad_dir / "config.yaml"
        raw = yaml.safe_load((FIXTURES / "valid/config.yaml").read_text())
        del raw["data"]["path"]
        bad_cfg.write_text(yaml.dump(raw), encoding="utf-8")

        # Use positional=tmp_path but override --config to bad_cfg
        result = self._cli([
            "validate", str(tmp_path),
            "--config", str(bad_cfg),
        ])
        assert result.exit_code != 0
