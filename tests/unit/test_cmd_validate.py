"""
tests/unit/test_cmd_validate.py — Unit tests for ``econflow validate``.

Covers:
- Pass when all three YAML files are valid and well-formed
- Fail when a YAML file is missing
- Fail when required keys are absent from config.yaml
- Fail when models list is empty
- Fail when a model is missing required fields
- Warn on unsupported estimator
- Warn on model regressors not in config
- Data validation (--data flag): missing file, bad columns, duplicate keys
- Exit code 0 when only warnings, 1 when any FAIL
"""

from __future__ import annotations

from pathlib import Path

import yaml
from typer.testing import CliRunner

from econflow.cli import app

runner = CliRunner()

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

MINIMAL_CONFIG = {
    "project": {"name": "test", "version": "0.1.0"},
    "data": {
        "path": "data/processed/panel.csv",
        "entity_col": "entity",
        "time_col": "time",
    },
    "variables": {
        "dependent": "outcome",
        "regressors": ["treatment", "covariate_1"],
    },
}

MINIMAL_MODELS = {
    "models": [
        {
            "id": "pooled_ols",
            "label": "Pooled OLS",
            "estimator": "OLS",
            "dependent": "outcome",
            "regressors": ["treatment", "covariate_1"],
            "entity_effects": False,
            "time_effects": False,
        },
        {
            "id": "entity_fe",
            "label": "Entity FE",
            "estimator": "FE",
            "dependent": "outcome",
            "regressors": ["treatment", "covariate_1"],
            "entity_effects": True,
            "time_effects": False,
            "cluster": "entity",
        },
    ]
}

MINIMAL_OUTPUTS = {
    "outputs": {
        "base_dir": "outputs",
        "tables": {
            "formats": ["csv", "latex"],
            "comparison_table": {
                "filename": "table_main",
                "models": ["pooled_ols", "entity_fe"],
            },
        },
    }
}


def _write_configs(tmp: Path, cfg=None, models=None, outputs=None) -> tuple[Path, Path, Path]:
    c = tmp / "config.yaml"
    m = tmp / "models.yaml"
    o = tmp / "outputs.yaml"
    if cfg is not None:
        c.write_text(yaml.dump(cfg), encoding="utf-8")
    if models is not None:
        m.write_text(yaml.dump(models), encoding="utf-8")
    if outputs is not None:
        o.write_text(yaml.dump(outputs), encoding="utf-8")
    return c, m, o


def _validate(tmp: Path, extra_args: list[str] | None = None) -> object:
    c, m, o = tmp / "config.yaml", tmp / "models.yaml", tmp / "outputs.yaml"
    args = [
        "validate",
        "--config", str(c),
        "--models", str(m),
        "--outputs", str(o),
    ] + (extra_args or [])
    return runner.invoke(app, args)


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

def test_validate_passes_with_valid_configs(tmp_path: Path) -> None:
    _write_configs(tmp_path, MINIMAL_CONFIG, MINIMAL_MODELS, MINIMAL_OUTPUTS)
    result = _validate(tmp_path)
    assert result.exit_code == 0
    assert "passed" in result.output.lower()


# ---------------------------------------------------------------------------
# Missing files
# ---------------------------------------------------------------------------

def test_validate_fails_when_config_missing(tmp_path: Path) -> None:
    _write_configs(tmp_path, None, MINIMAL_MODELS, MINIMAL_OUTPUTS)
    result = _validate(tmp_path)
    assert result.exit_code != 0


def test_validate_fails_when_models_missing(tmp_path: Path) -> None:
    _write_configs(tmp_path, MINIMAL_CONFIG, None, MINIMAL_OUTPUTS)
    result = _validate(tmp_path)
    assert result.exit_code != 0


def test_validate_fails_when_outputs_missing(tmp_path: Path) -> None:
    _write_configs(tmp_path, MINIMAL_CONFIG, MINIMAL_MODELS, None)
    result = _validate(tmp_path)
    assert result.exit_code != 0


# ---------------------------------------------------------------------------
# config.yaml schema checks
# ---------------------------------------------------------------------------

def test_validate_fails_when_data_path_missing(tmp_path: Path) -> None:
    import copy
    cfg = copy.deepcopy(MINIMAL_CONFIG)
    del cfg["data"]["path"]
    _write_configs(tmp_path, cfg, MINIMAL_MODELS, MINIMAL_OUTPUTS)
    result = _validate(tmp_path)
    assert result.exit_code != 0


def test_validate_fails_when_entity_col_missing(tmp_path: Path) -> None:
    import copy
    cfg = copy.deepcopy(MINIMAL_CONFIG)
    del cfg["data"]["entity_col"]
    _write_configs(tmp_path, cfg, MINIMAL_MODELS, MINIMAL_OUTPUTS)
    result = _validate(tmp_path)
    assert result.exit_code != 0


def test_validate_fails_when_time_col_missing(tmp_path: Path) -> None:
    import copy
    cfg = copy.deepcopy(MINIMAL_CONFIG)
    del cfg["data"]["time_col"]
    _write_configs(tmp_path, cfg, MINIMAL_MODELS, MINIMAL_OUTPUTS)
    result = _validate(tmp_path)
    assert result.exit_code != 0


def test_validate_fails_when_dependent_missing(tmp_path: Path) -> None:
    import copy
    cfg = copy.deepcopy(MINIMAL_CONFIG)
    del cfg["variables"]["dependent"]
    _write_configs(tmp_path, cfg, MINIMAL_MODELS, MINIMAL_OUTPUTS)
    result = _validate(tmp_path)
    assert result.exit_code != 0


def test_validate_fails_when_regressors_empty(tmp_path: Path) -> None:
    import copy
    cfg = copy.deepcopy(MINIMAL_CONFIG)
    cfg["variables"]["regressors"] = []
    _write_configs(tmp_path, cfg, MINIMAL_MODELS, MINIMAL_OUTPUTS)
    result = _validate(tmp_path)
    assert result.exit_code != 0


# ---------------------------------------------------------------------------
# models.yaml schema checks
# ---------------------------------------------------------------------------

def test_validate_fails_when_models_list_empty(tmp_path: Path) -> None:
    _write_configs(tmp_path, MINIMAL_CONFIG, {"models": []}, MINIMAL_OUTPUTS)
    result = _validate(tmp_path)
    assert result.exit_code != 0


def test_validate_fails_when_model_missing_id(tmp_path: Path) -> None:
    import copy
    models = copy.deepcopy(MINIMAL_MODELS)
    del models["models"][0]["id"]
    _write_configs(tmp_path, MINIMAL_CONFIG, models, MINIMAL_OUTPUTS)
    result = _validate(tmp_path)
    assert result.exit_code != 0


def test_validate_fails_when_duplicate_model_ids(tmp_path: Path) -> None:
    import copy
    models = copy.deepcopy(MINIMAL_MODELS)
    models["models"][1]["id"] = "pooled_ols"  # duplicate
    _write_configs(tmp_path, MINIMAL_CONFIG, models, MINIMAL_OUTPUTS)
    result = _validate(tmp_path)
    assert result.exit_code != 0


def test_validate_warns_on_unsupported_estimator(tmp_path: Path) -> None:
    import copy
    models = copy.deepcopy(MINIMAL_MODELS)
    models["models"][0]["estimator"] = "GMMEstimator"
    _write_configs(tmp_path, MINIMAL_CONFIG, models, MINIMAL_OUTPUTS)
    result = _validate(tmp_path)
    # Should warn but not fail (exit 0)
    assert result.exit_code == 0
    assert "warn" in result.output.lower() or "⚠" in result.output


# ---------------------------------------------------------------------------
# outputs.yaml schema checks
# ---------------------------------------------------------------------------

def test_validate_fails_when_base_dir_missing(tmp_path: Path) -> None:
    import copy
    out = copy.deepcopy(MINIMAL_OUTPUTS)
    del out["outputs"]["base_dir"]
    _write_configs(tmp_path, MINIMAL_CONFIG, MINIMAL_MODELS, out)
    result = _validate(tmp_path)
    assert result.exit_code != 0


def test_validate_fails_when_comparison_table_filename_missing(tmp_path: Path) -> None:
    import copy
    out = copy.deepcopy(MINIMAL_OUTPUTS)
    del out["outputs"]["tables"]["comparison_table"]["filename"]
    _write_configs(tmp_path, MINIMAL_CONFIG, MINIMAL_MODELS, out)
    result = _validate(tmp_path)
    assert result.exit_code != 0


# ---------------------------------------------------------------------------
# Cross-file consistency
# ---------------------------------------------------------------------------

def test_validate_fails_when_output_model_id_not_in_models(tmp_path: Path) -> None:
    import copy
    out = copy.deepcopy(MINIMAL_OUTPUTS)
    out["outputs"]["tables"]["comparison_table"]["models"] = ["nonexistent_model"]
    _write_configs(tmp_path, MINIMAL_CONFIG, MINIMAL_MODELS, out)
    result = _validate(tmp_path)
    assert result.exit_code != 0


# ---------------------------------------------------------------------------
# --data flag
# ---------------------------------------------------------------------------

def test_validate_data_flag_warns_when_file_missing(tmp_path: Path) -> None:
    _write_configs(tmp_path, MINIMAL_CONFIG, MINIMAL_MODELS, MINIMAL_OUTPUTS)
    result = _validate(tmp_path, ["--data"])
    # Data file doesn't exist — should fail that check
    assert result.exit_code != 0


def test_validate_data_flag_passes_with_valid_csv(tmp_path: Path) -> None:
    import copy
    cfg = copy.deepcopy(MINIMAL_CONFIG)
    csv_path = tmp_path / "panel.csv"
    csv_path.write_text(
        "entity,time,outcome,treatment,covariate_1\n"
        "A,2020,1.0,0.5,9.0\n"
        "A,2021,1.1,0.6,9.1\n"
        "B,2020,2.0,0.4,8.0\n"
        "B,2021,2.1,0.5,8.1\n",
        encoding="utf-8",
    )
    cfg["data"]["path"] = str(csv_path)
    _write_configs(tmp_path, cfg, MINIMAL_MODELS, MINIMAL_OUTPUTS)
    result = _validate(tmp_path, ["--data"])
    assert result.exit_code == 0


def test_validate_data_flag_fails_on_missing_column(tmp_path: Path) -> None:
    import copy
    cfg = copy.deepcopy(MINIMAL_CONFIG)
    csv_path = tmp_path / "panel_bad.csv"
    # Missing 'outcome' column
    csv_path.write_text(
        "entity,time,treatment,covariate_1\n"
        "A,2020,0.5,9.0\n",
        encoding="utf-8",
    )
    cfg["data"]["path"] = str(csv_path)
    _write_configs(tmp_path, cfg, MINIMAL_MODELS, MINIMAL_OUTPUTS)
    result = _validate(tmp_path, ["--data"])
    assert result.exit_code != 0


def test_validate_data_flag_warns_on_duplicate_panel_keys(tmp_path: Path) -> None:
    import copy
    cfg = copy.deepcopy(MINIMAL_CONFIG)
    csv_path = tmp_path / "panel_dup.csv"
    csv_path.write_text(
        "entity,time,outcome,treatment,covariate_1\n"
        "A,2020,1.0,0.5,9.0\n"
        "A,2020,1.1,0.6,9.1\n",  # duplicate (A, 2020)
        encoding="utf-8",
    )
    cfg["data"]["path"] = str(csv_path)
    _write_configs(tmp_path, cfg, MINIMAL_MODELS, MINIMAL_OUTPUTS)
    result = _validate(tmp_path, ["--data"])
    # Duplicates trigger a warning — exit should still be 0
    assert result.exit_code == 0
    assert "duplicate" in result.output.lower()
