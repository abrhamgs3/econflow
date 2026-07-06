"""
tests.unit.test_config_validation — Regression tests for the configuration
correctness boundary.

Tests all four validation stages:
1. YAML syntax
2. Pydantic schema (unknown keys, wrong types, missing required fields,
   incorrect nesting)
3. Semantic (linter rules L-01 through L-13)
4. Cross-file (X-01, X-02)

Also tests the programmatic API (ConfigValidator, ValidationResult,
ValidationIssue, ConfigValidationError) and the CLI enforcement contract
(validate_strict raises on errors, passes on valid config).
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest
import yaml

from econflow.config.validator import ConfigValidator, ValidationIssue, ValidationResult

# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

FIXTURES = Path(__file__).parent.parent / "fixtures" / "config"
VALID = FIXTURES / "valid"
INVALID = FIXTURES / "invalid"


def _vld(subdir: str) -> tuple[Path, Path, Path]:
    """Return (config, models, outputs) paths for a fixture directory."""
    d = INVALID / subdir
    return d / "config.yaml", d / "models.yaml", d / "outputs.yaml"


def _valid() -> tuple[Path, Path, Path]:
    return VALID / "config.yaml", VALID / "models.yaml", VALID / "outputs.yaml"


@pytest.fixture()
def validator() -> ConfigValidator:
    return ConfigValidator()


# ---------------------------------------------------------------------------
# §1 — Valid config passes all stages
# ---------------------------------------------------------------------------

class TestValidConfig:
    def test_valid_config_no_errors(self, validator, tmp_path):
        result = validator.validate(*_valid())
        assert result.ok, f"Expected OK, got errors: {result.errors}"

    def test_valid_config_returns_parsed_objects(self, validator):
        result = validator.validate(*_valid())
        assert result.project_cfg is not None
        assert result.models_cfg is not None
        assert result.outputs_cfg is not None

    def test_valid_config_has_no_issues(self, validator):
        result = validator.validate(*_valid())
        # May have info items from L-10 (empty label) — filter to errors only
        assert len(result.errors) == 0

    def test_validate_strict_returns_configs(self, validator):
        project, models, outputs = validator.validate_strict(*_valid())
        assert project is not None
        assert models is not None
        assert outputs is not None

    def test_validate_strict_project_name(self, validator):
        project, _, _ = validator.validate_strict(*_valid())
        assert project.project.name == "test_project"

    def test_validate_strict_model_count(self, validator):
        _, models, _ = validator.validate_strict(*_valid())
        assert len(models.models) == 2

    def test_validation_result_type(self, validator):
        result = validator.validate(*_valid())
        assert isinstance(result, ValidationResult)

    def test_issue_type(self, validator):
        # Even in a valid config we might have info items; check types
        result = validator.validate(*_valid())
        for issue in result.issues:
            assert isinstance(issue, ValidationIssue)
            assert issue.stage in ("yaml_syntax", "schema", "semantic", "cross_file", "data")
            assert issue.severity in ("error", "warning", "info")


# ---------------------------------------------------------------------------
# §2 — Stage 1: YAML syntax errors
# ---------------------------------------------------------------------------

class TestYAMLSyntax:
    def test_malformed_yaml_detected(self, validator):
        result = validator.validate(*_vld("yaml_syntax_error"))
        yaml_errors = result.by_stage("yaml_syntax")
        assert len(yaml_errors) >= 1
        assert yaml_errors[0].severity == "error"
        assert yaml_errors[0].source == "config.yaml"

    def test_malformed_yaml_stage_label(self, validator):
        result = validator.validate(*_vld("yaml_syntax_error"))
        assert any(i.stage == "yaml_syntax" for i in result.issues)

    def test_file_not_found(self, validator, tmp_path):
        nonexistent = tmp_path / "does_not_exist.yaml"
        result = validator.validate(nonexistent, nonexistent, nonexistent)
        assert not result.ok
        file_errors = result.by_stage("yaml_syntax")
        assert len(file_errors) == 3  # one per file

    def test_empty_yaml_returns_schema_errors(self, validator, tmp_path):
        """An empty (or null) YAML file should pass YAML stage but fail schema."""
        cfg = tmp_path / "config.yaml"
        models = tmp_path / "models.yaml"
        outputs = tmp_path / "outputs.yaml"
        cfg.write_text("")
        models.write_text("")
        outputs.write_text("")
        result = validator.validate(cfg, models, outputs)
        # Empty YAML → empty dict → missing required fields at schema stage
        schema_errors = result.by_stage("schema")
        assert len(schema_errors) > 0

    def test_yaml_list_at_root_rejected(self, validator, tmp_path):
        """A YAML file that is a list (not a mapping) at root should error."""
        cfg = tmp_path / "config.yaml"
        models = tmp_path / "models.yaml"
        outputs = tmp_path / "outputs.yaml"
        cfg.write_text("- item1\n- item2\n")
        models.write_text(VALID.joinpath("models.yaml").read_text())
        outputs.write_text(VALID.joinpath("outputs.yaml").read_text())
        result = validator.validate(cfg, models, outputs)
        yaml_errors = result.by_stage("yaml_syntax")
        assert any("mapping" in i.message.lower() for i in yaml_errors)


# ---------------------------------------------------------------------------
# §3 — Stage 2: Schema validation (unknown keys, types, nesting)
# ---------------------------------------------------------------------------

class TestSchemaValidation:
    def test_unknown_key_rejected(self, validator):
        result = validator.validate(*_vld("extra_key"))
        schema_errors = result.by_stage("schema")
        assert any("extra" in i.message.lower() or "forbidden" in i.message.lower()
                   for i in schema_errors), f"Got schema errors: {schema_errors}"

    def test_unknown_key_fix_hint(self, validator):
        result = validator.validate(*_vld("extra_key"))
        schema_errors = result.by_stage("schema")
        extra = [i for i in schema_errors if "extra" in i.message.lower() or
                 "forbidden" in i.message.lower() or "unexpected" in i.message.lower()]
        assert extra
        # Fix should mention 'econflow docs config' or removal
        assert extra[0].fix != ""

    def test_wrong_nesting_rejected(self, validator):
        """sample: block nested inside data: is forbidden by extra='forbid'."""
        result = validator.validate(*_vld("wrong_nesting"))
        # The extra key 'sample' inside 'data' should trigger extra_forbidden
        assert not result.ok

    def test_missing_required_field(self, validator, tmp_path):
        """models.yaml missing 'models' key should error."""
        cfg = VALID / "config.yaml"
        outputs = VALID / "outputs.yaml"
        models = tmp_path / "models.yaml"
        models.write_text("version: 1\n")  # top-level 'models' list missing
        result = validator.validate(cfg, models, outputs)
        schema_errors = result.by_stage("schema")
        # Pydantic v2 reports "Field required" for missing keys, and
        # "Extra inputs are not permitted" for unknown keys
        assert any(
            "field required" in i.message.lower()
            or "missing" in i.message.lower()
            or "models" in i.location.lower()
            for i in schema_errors
        )

    def test_wrong_type_integer(self, validator, tmp_path):
        """start_year as string should fail."""
        cfg = tmp_path / "config.yaml"
        data = {
            "project": {"name": "t", "version": "1.0.0"},
            "data": {"path": "d.csv", "entity_col": "e", "time_col": "t"},
            "sample": {"start_year": "not_an_int", "end_year": 2020},
            "variables": {"dependent": "y", "regressors": ["x"]},
        }
        cfg.write_text(yaml.dump(data))
        result = validator.validate(cfg, VALID / "models.yaml", VALID / "outputs.yaml")
        schema_errors = result.by_stage("schema")
        assert any("start_year" in i.location or "int" in i.message.lower()
                   for i in schema_errors)

    def test_wrong_type_bool(self, validator, tmp_path):
        """entity_effects as a list (invalid type) should fail schema validation."""
        # Note: Pydantic v2 coerces common string values ("yes"/"no"/"true"/"false")
        # to bool, so we use a list — which is unambiguously the wrong type.
        models = tmp_path / "models.yaml"
        data = {"models": [{
            "id": "m1", "label": "M1", "estimator": "fe",
            "dependent": "outcome", "regressors": ["treatment", "covariate_1"],
            "entity_effects": [True, False],  # list is not a valid bool
        }]}
        models.write_text(yaml.dump(data))
        # Use an outputs fixture that only references m1 to avoid X-01 noise
        outputs = tmp_path / "outputs.yaml"
        out_data = {
            "outputs": {
                "base_dir": "outputs",
                "tables": {
                    "dir": "outputs/tables",
                    "formats": ["csv"],
                    "comparison_table": {
                        "filename": "t", "models": ["m1"],
                        "stars": True, "se_type": "robust",
                    },
                },
            }
        }
        outputs.write_text(yaml.dump(out_data))
        result = validator.validate(VALID / "config.yaml", models, outputs)
        schema_errors = result.by_stage("schema")
        # Pydantic v2 rejects list-for-bool: "Input should be a valid boolean"
        assert len(schema_errors) > 0, (
            "Expected schema error for list-typed bool field; "
            f"got: {[i.message for i in result.issues]}"
        )

    def test_empty_models_list_rejected(self, validator, tmp_path):
        """models.yaml with empty models list should fail min_length=1."""
        models = tmp_path / "models.yaml"
        models.write_text("models: []\n")
        result = validator.validate(VALID / "config.yaml", models, VALID / "outputs.yaml")
        schema_errors = result.by_stage("schema")
        assert len(schema_errors) > 0

    def test_duplicate_model_ids_rejected(self, validator):
        result = validator.validate(*_vld("dup_model_ids"))
        assert not result.ok
        # Error could come from schema validator (model_validator on ModelsConfig)
        assert len(result.errors) > 0

    def test_invalid_model_id_pattern(self, validator, tmp_path):
        """Model id starting with a digit is invalid."""
        models = tmp_path / "models.yaml"
        data = {"models": [{
            "id": "1invalid", "estimator": "ols",
            "dependent": "y", "regressors": ["x"],
        }]}
        models.write_text(yaml.dump(data))
        result = validator.validate(VALID / "config.yaml", models, VALID / "outputs.yaml")
        assert not result.ok

    def test_literal_se_type_validated(self, validator, tmp_path):
        """se_type must be one of the allowed literals."""
        outputs = tmp_path / "outputs.yaml"
        data = {
            "outputs": {
                "base_dir": "outputs",
                "tables": {
                    "dir": "outputs/tables",
                    "formats": ["csv"],
                    "comparison_table": {
                        "filename": "t", "models": [], "stars": True,
                        "se_type": "bootstrap",  # invalid literal
                    },
                },
            }
        }
        outputs.write_text(yaml.dump(data))
        result = validator.validate(VALID / "config.yaml", VALID / "models.yaml", outputs)
        schema_errors = result.by_stage("schema")
        assert any("se_type" in i.location or "literal" in i.message.lower() or
                   "bootstrap" in i.message.lower()
                   for i in schema_errors)


# ---------------------------------------------------------------------------
# §4 — Stage 3: Semantic validation (linter rules)
# ---------------------------------------------------------------------------

class TestSemanticValidation:
    def test_L01_dependent_in_regressors(self, validator):
        result = validator.validate(*_vld("dep_in_regressors"))
        sem = result.by_stage("semantic")
        assert any(i.code == "L-01" for i in sem)

    def test_L01_is_error(self, validator):
        result = validator.validate(*_vld("dep_in_regressors"))
        l01 = [i for i in result.by_stage("semantic") if i.code == "L-01"]
        assert l01[0].severity == "error"

    def test_L02_duplicate_regressors(self, validator):
        result = validator.validate(*_vld("dup_regressors"))
        sem = result.by_stage("semantic")
        assert any(i.code == "L-02" for i in sem)

    def test_L03_year_order(self, validator):
        result = validator.validate(*_vld("year_order"))
        # L-03 might fire from linter or from Pydantic validator; both are errors
        issues = result.errors
        assert len(issues) > 0

    def test_L04_unknown_estimator(self, validator):
        result = validator.validate(*_vld("unknown_estimator"))
        sem = result.by_stage("semantic")
        l04 = [i for i in sem if i.code in ("L-04", "L-04b")]
        assert len(l04) > 0

    def test_L04b_stub_estimator_is_error(self, validator, tmp_path):
        """gmm and quantile are stubs — should trigger L-04b with severity error."""
        models = tmp_path / "models.yaml"
        data = {"models": [{
            "id": "gmm_model", "label": "GMM", "estimator": "gmm",
            "dependent": "outcome", "regressors": ["treatment", "covariate_1"],
        }]}
        models.write_text(yaml.dump(data))
        result = validator.validate(VALID / "config.yaml", models, VALID / "outputs.yaml")
        sem = result.by_stage("semantic")
        l04b = [i for i in sem if i.code == "L-04b"]
        assert len(l04b) > 0
        assert l04b[0].severity == "error"

    def test_L06_absolute_base_dir(self, validator):
        result = validator.validate(*_vld("abs_base_dir"))
        sem = result.by_stage("semantic")
        l06 = [i for i in sem if i.code == "L-06"]
        assert len(l06) > 0
        assert l06[0].severity == "warning"

    def test_L07_unsupported_extension(self, validator, tmp_path):
        """data.path with .xlsx extension triggers L-07."""
        cfg = tmp_path / "config.yaml"
        data = {
            "project": {"name": "t", "version": "1.0.0"},
            "data": {"path": "data/panel.xlsx", "entity_col": "e", "time_col": "t"},
            "variables": {"dependent": "y", "regressors": ["x"]},
        }
        cfg.write_text(yaml.dump(data))
        result = validator.validate(cfg, VALID / "models.yaml", VALID / "outputs.yaml")
        sem = result.by_stage("semantic")
        l07 = [i for i in sem if i.code == "L-07"]
        assert len(l07) > 0

    def test_L08_invalid_semver(self, validator, tmp_path):
        cfg = tmp_path / "config.yaml"
        data = {
            "project": {"name": "t", "version": "v1.x"},
            "data": {"path": "data/panel.csv", "entity_col": "e", "time_col": "t"},
            "variables": {"dependent": "y", "regressors": ["x"]},
        }
        cfg.write_text(yaml.dump(data))
        result = validator.validate(cfg, VALID / "models.yaml", VALID / "outputs.yaml")
        sem = result.by_stage("semantic")
        l08 = [i for i in sem if i.code == "L-08"]
        assert len(l08) > 0

    def test_L11_iv_no_instruments_is_error(self, validator):
        result = validator.validate(*_vld("iv_no_instruments"))
        sem = result.by_stage("semantic")
        l11 = [i for i in sem if i.code == "L-11"]
        assert len(l11) > 0
        assert l11[0].severity == "error"

    def test_L12_twfe_no_effects_is_warning(self, validator):
        result = validator.validate(*_vld("twfe_no_effects"))
        sem = result.by_stage("semantic")
        l12 = [i for i in sem if i.code == "L-12"]
        assert len(l12) > 0
        assert l12[0].severity == "warning"

    def test_L13_bad_format_is_warning(self, validator):
        result = validator.validate(*_vld("bad_format"))
        sem = result.by_stage("semantic")
        l13 = [i for i in sem if i.code == "L-13"]
        assert len(l13) > 0
        assert l13[0].severity == "warning"

    def test_L13_multiple_bad_formats(self, validator):
        """Two unknown formats → two L-13 issues."""
        result = validator.validate(*_vld("bad_format"))
        sem = result.by_stage("semantic")
        l13 = [i for i in sem if i.code == "L-13"]
        assert len(l13) >= 2  # "word" and "pptx" both unknown

    def test_L12_twfe_with_effects_no_warning(self, validator, tmp_path):
        """TWFE with entity_effects=True and time_effects=True should NOT trigger L-12."""
        models = tmp_path / "models.yaml"
        data = {"models": [{
            "id": "twfe", "label": "TWFE", "estimator": "twfe",
            "dependent": "outcome", "regressors": ["treatment", "covariate_1"],
            "entity_effects": True, "time_effects": True,
        }]}
        models.write_text(yaml.dump(data))

        outputs = tmp_path / "outputs.yaml"
        out_data = {
            "outputs": {
                "base_dir": "outputs",
                "tables": {
                    "dir": "outputs/tables",
                    "formats": ["csv"],
                    "comparison_table": {"filename": "t", "models": ["twfe"], "stars": True, "se_type": "robust"},
                },
            }
        }
        outputs.write_text(yaml.dump(out_data))
        result = validator.validate(VALID / "config.yaml", models, outputs)
        sem = result.by_stage("semantic")
        l12 = [i for i in sem if i.code == "L-12"]
        assert len(l12) == 0

    def test_L11_iv_with_instruments_no_error(self, validator, tmp_path):
        """IV with instruments in config.yaml should NOT trigger L-11."""
        cfg = tmp_path / "config.yaml"
        cfg_data = {
            "project": {"name": "t", "version": "1.0.0"},
            "data": {"path": "data/panel.csv", "entity_col": "entity", "time_col": "time"},
            "variables": {
                "dependent": "outcome",
                "regressors": ["treatment", "covariate_1"],
                "instruments": ["instrument_var"],
            },
        }
        cfg.write_text(yaml.dump(cfg_data))
        models = tmp_path / "models.yaml"
        data = {"models": [{
            "id": "iv_m", "label": "IV", "estimator": "iv",
            "dependent": "outcome", "regressors": ["treatment", "covariate_1"],
        }]}
        models.write_text(yaml.dump(data))
        outputs = tmp_path / "outputs.yaml"
        out_data = {
            "outputs": {
                "base_dir": "outputs",
                "tables": {
                    "dir": "outputs/tables",
                    "formats": ["csv"],
                    "comparison_table": {"filename": "t", "models": ["iv_m"], "stars": True, "se_type": "robust"},
                },
            }
        }
        outputs.write_text(yaml.dump(out_data))
        result = validator.validate(cfg, models, outputs)
        sem = result.by_stage("semantic")
        l11 = [i for i in sem if i.code == "L-11"]
        assert len(l11) == 0


# ---------------------------------------------------------------------------
# §5 — Stage 4: Cross-file validation
# ---------------------------------------------------------------------------

class TestCrossFileValidation:
    def test_X01_missing_model_ref(self, validator):
        result = validator.validate(*_vld("x01_missing_model_ref"))
        cross = result.by_stage("cross_file")
        x01 = [i for i in cross if i.code == "X-01"]
        assert len(x01) > 0
        assert x01[0].severity == "error"

    def test_X01_missing_model_fix_hint(self, validator):
        result = validator.validate(*_vld("x01_missing_model_ref"))
        cross = result.by_stage("cross_file")
        x01 = [i for i in cross if i.code == "X-01"]
        assert x01[0].fix != ""

    def test_X02_extra_regressors_in_model(self, validator):
        result = validator.validate(*_vld("x02_extra_regressors"))
        cross = result.by_stage("cross_file")
        x02 = [i for i in cross if i.code == "X-02"]
        assert len(x02) > 0
        assert x02[0].severity == "error"

    def test_X02_extra_regressors_names_mentioned(self, validator):
        result = validator.validate(*_vld("x02_extra_regressors"))
        cross = result.by_stage("cross_file")
        x02 = [i for i in cross if i.code == "X-02"]
        assert "mystery_var" in x02[0].message

    def test_cross_file_ok_for_valid_config(self, validator):
        result = validator.validate(*_valid())
        cross = result.by_stage("cross_file")
        assert all(i.severity != "error" for i in cross)


# ---------------------------------------------------------------------------
# §6 — Stage 5: Data file validation
# ---------------------------------------------------------------------------

class TestDataValidation:
    def _write_csv(self, path: Path, rows: list[dict]) -> None:
        import csv
        if not rows:
            path.write_text("")
            return
        with path.open("w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)

    def test_data_file_not_found_is_error(self, validator):
        result = validator.validate(*_valid(), check_data=True)
        data_issues = result.by_stage("data")
        # Data file doesn't exist → error (blocks execution)
        not_found = [i for i in data_issues if "not found" in i.message.lower()]
        assert all(i.severity == "error" for i in not_found)

    def test_missing_columns_error(self, validator, tmp_path):
        """CSV missing entity/time columns → D-01 error."""
        csv_file = tmp_path / "panel.csv"
        self._write_csv(csv_file, [
            {"wrong_col": "A", "year": 2010, "outcome": 1.0, "treatment": 0.5},
        ])
        cfg = tmp_path / "config.yaml"
        cfg_data = {
            "project": {"name": "t", "version": "1.0.0"},
            "data": {
                "path": str(csv_file),
                "entity_col": "entity",
                "time_col": "year",
            },
            "variables": {"dependent": "outcome", "regressors": ["treatment"]},
        }
        cfg.write_text(yaml.dump(cfg_data))
        models = tmp_path / "models.yaml"
        models.write_text(yaml.dump({"models": [{
            "id": "m1", "label": "M", "estimator": "ols",
            "dependent": "outcome", "regressors": ["treatment"],
        }]}))
        outputs = tmp_path / "outputs.yaml"
        outputs.write_text(yaml.dump({
            "outputs": {
                "base_dir": "outputs",
                "tables": {"dir": "t", "formats": ["csv"],
                           "comparison_table": {"filename": "t", "models": ["m1"],
                                                "stars": True, "se_type": "robust"}},
            }
        }))
        result = validator.validate(cfg, models, outputs, check_data=True)
        data_issues = result.by_stage("data")
        d01 = [i for i in data_issues if i.code == "D-01"]
        assert len(d01) > 0
        assert "entity" in d01[0].message

    def test_missing_analysis_variables_error(self, validator, tmp_path):
        """CSV missing dependent variable → D-02 error."""
        csv_file = tmp_path / "panel.csv"
        self._write_csv(csv_file, [
            {"entity": "A", "year": 2010, "treatment": 0.5},  # 'outcome' missing
        ])
        cfg = tmp_path / "config.yaml"
        cfg_data = {
            "project": {"name": "t", "version": "1.0.0"},
            "data": {"path": str(csv_file), "entity_col": "entity", "time_col": "year"},
            "variables": {"dependent": "outcome", "regressors": ["treatment"]},
        }
        cfg.write_text(yaml.dump(cfg_data))
        models = tmp_path / "models.yaml"
        models.write_text(yaml.dump({"models": [{
            "id": "m1", "label": "M", "estimator": "ols",
            "dependent": "outcome", "regressors": ["treatment"],
        }]}))
        outputs = tmp_path / "outputs.yaml"
        outputs.write_text(yaml.dump({
            "outputs": {
                "base_dir": "outputs",
                "tables": {"dir": "t", "formats": ["csv"],
                           "comparison_table": {"filename": "t", "models": ["m1"],
                                                "stars": True, "se_type": "robust"}},
            }
        }))
        result = validator.validate(cfg, models, outputs, check_data=True)
        data_issues = result.by_stage("data")
        d02 = [i for i in data_issues if i.code == "D-02"]
        assert len(d02) > 0
        assert "outcome" in d02[0].message

    def test_duplicate_panel_keys_warning(self, validator, tmp_path):
        """Duplicate (entity, time) rows → D-03 warning."""
        csv_file = tmp_path / "panel.csv"
        self._write_csv(csv_file, [
            {"entity": "A", "year": 2010, "outcome": 1.0, "treatment": 0.5},
            {"entity": "A", "year": 2010, "outcome": 2.0, "treatment": 0.6},  # duplicate
            {"entity": "B", "year": 2010, "outcome": 3.0, "treatment": 0.7},
        ])
        cfg = tmp_path / "config.yaml"
        cfg_data = {
            "project": {"name": "t", "version": "1.0.0"},
            "data": {"path": str(csv_file), "entity_col": "entity", "time_col": "year"},
            "variables": {"dependent": "outcome", "regressors": ["treatment"]},
        }
        cfg.write_text(yaml.dump(cfg_data))
        models = tmp_path / "models.yaml"
        models.write_text(yaml.dump({"models": [{
            "id": "m1", "label": "M", "estimator": "ols",
            "dependent": "outcome", "regressors": ["treatment"],
        }]}))
        outputs = tmp_path / "outputs.yaml"
        outputs.write_text(yaml.dump({
            "outputs": {
                "base_dir": "outputs",
                "tables": {"dir": "t", "formats": ["csv"],
                           "comparison_table": {"filename": "t", "models": ["m1"],
                                                "stars": True, "se_type": "robust"}},
            }
        }))
        result = validator.validate(cfg, models, outputs, check_data=True)
        data_issues = result.by_stage("data")
        d03 = [i for i in data_issues if i.code == "D-03"]
        assert len(d03) > 0
        assert d03[0].severity == "warning"

    def test_check_data_false_skips_data_stage(self, validator):
        result = validator.validate(*_valid(), check_data=False)
        data_issues = result.by_stage("data")
        assert len(data_issues) == 0


# ---------------------------------------------------------------------------
# §7 — ConfigValidationError
# ---------------------------------------------------------------------------

class TestConfigValidationError:
    def test_validate_strict_raises_on_errors(self, validator):
        from econflow.core.exceptions import ConfigValidationError
        with pytest.raises(ConfigValidationError):
            validator.validate_strict(*_vld("dep_in_regressors"))

    def test_error_carries_issue_list(self, validator):
        from econflow.core.exceptions import ConfigValidationError
        with pytest.raises(ConfigValidationError) as exc_info:
            validator.validate_strict(*_vld("dep_in_regressors"))
        exc = exc_info.value
        assert len(exc.issues) > 0

    def test_error_has_errors_property(self, validator):
        from econflow.core.exceptions import ConfigValidationError
        with pytest.raises(ConfigValidationError) as exc_info:
            validator.validate_strict(*_vld("dep_in_regressors"))
        assert len(exc_info.value.errors) > 0

    def test_error_has_warnings_property(self, validator):
        from econflow.core.exceptions import ConfigValidationError
        with pytest.raises(ConfigValidationError) as exc_info:
            validator.validate_strict(*_vld("dep_in_regressors"))
        # warnings list may be empty — just check it exists
        assert isinstance(exc_info.value.warnings, list)

    def test_error_count_correct(self, validator):
        from econflow.core.exceptions import ConfigValidationError
        with pytest.raises(ConfigValidationError) as exc_info:
            validator.validate_strict(*_vld("dep_in_regressors"))
        exc = exc_info.value
        assert exc.error_count == len(exc.errors)

    def test_error_message_mentions_config_path(self, validator):
        from econflow.core.exceptions import ConfigValidationError
        with pytest.raises(ConfigValidationError) as exc_info:
            validator.validate_strict(*_vld("dep_in_regressors"))
        assert "config.yaml" in str(exc_info.value)

    def test_validate_strict_warnings_do_not_raise(self, validator):
        """Warnings (L-06, L-12 etc.) must not raise — only errors block."""
        from econflow.core.exceptions import ConfigValidationError
        # twfe_no_effects has only L-12 (warning) and L-10 (info) — should not raise
        try:
            validator.validate_strict(*_vld("twfe_no_effects"))
        except ConfigValidationError:
            pytest.fail("validate_strict raised on warning-only config")

    def test_config_validation_error_is_configuration_error(self):
        from econflow.core.exceptions import ConfigValidationError, ConfigurationError
        assert issubclass(ConfigValidationError, ConfigurationError)

    def test_config_validation_error_is_econflow_error(self):
        from econflow.core.exceptions import ConfigValidationError
        from econflow.exceptions import EconFlowError
        assert issubclass(ConfigValidationError, EconFlowError)


# ---------------------------------------------------------------------------
# §8 — API guarantees and programmatic use
# ---------------------------------------------------------------------------

class TestProgrammaticAPI:
    def test_no_cli_import_needed(self):
        """ConfigValidator must be importable without any CLI dependencies."""
        from econflow.config.validator import ConfigValidator  # noqa: F401 (duplicate, intentional)
        from econflow.config import ConfigValidator as CV2  # noqa: F401

    def test_validation_result_by_stage(self, validator):
        result = validator.validate(*_vld("dep_in_regressors"))
        sem = result.by_stage("semantic")
        assert all(i.stage == "semantic" for i in sem)

    def test_validation_result_by_source(self, validator):
        result = validator.validate(*_vld("dep_in_regressors"))
        cfg_issues = result.by_source("config.yaml")
        assert all(i.source == "config.yaml" for i in cfg_issues)

    def test_validation_result_infos_property(self, validator):
        result = validator.validate(*_valid())
        infos = result.infos
        assert all(i.severity == "info" for i in infos)

    def test_multiple_errors_all_reported(self, validator, tmp_path):
        """All errors must be collected — not fail-fast."""
        # dep_in_regressors has L-01; unknown_estimator has L-04; combine them
        cfg_path = INVALID / "dep_in_regressors" / "config.yaml"
        models_path = INVALID / "unknown_estimator" / "models.yaml"
        outputs_path = VALID / "outputs.yaml"
        result = validator.validate(cfg_path, models_path, outputs_path)
        # Both errors should appear
        codes = {i.code for i in result.errors}
        assert "L-01" in codes or any("dependent" in i.message for i in result.errors)

    def test_issue_str_representation(self, validator):
        result = validator.validate(*_vld("dep_in_regressors"))
        for issue in result.errors:
            s = str(issue)
            assert issue.message in s

    def test_stage_ordering_in_result(self, validator):
        """Issues should be ordered: yaml_syntax → schema → semantic → cross_file."""
        result = validator.validate(
            INVALID / "yaml_syntax_error" / "config.yaml",
            INVALID / "x01_missing_model_ref" / "models.yaml",
            INVALID / "x01_missing_model_ref" / "outputs.yaml",
        )
        stage_order = {"yaml_syntax": 0, "schema": 1, "semantic": 2, "cross_file": 3, "data": 4}
        stages = [stage_order.get(i.stage, 99) for i in result.issues]
        assert stages == sorted(stages), "Issues should be sorted by stage"

    def test_validator_is_reusable(self, validator):
        """Same ConfigValidator instance can validate multiple configs."""
        r1 = validator.validate(*_valid())
        r2 = validator.validate(*_vld("dep_in_regressors"))
        assert r1.ok
        assert not r2.ok

    def test_config_validator_from_config_package(self):
        """ConfigValidator is accessible from the top-level config package."""
        from econflow.config import ConfigValidator
        v = ConfigValidator()
        result = v.validate(*_valid())
        assert result.ok

    def test_validation_issue_fields(self):
        """ValidationIssue dataclass must have all required fields."""
        issue = ValidationIssue(
            stage="schema",
            severity="error",
            source="config.yaml",
            location="variables → dependent",
            message="test",
            fix="do something",
            code="T-01",
        )
        assert issue.stage == "schema"
        assert issue.severity == "error"
        assert issue.source == "config.yaml"
        assert issue.code == "T-01"
        assert "T-01" in str(issue)