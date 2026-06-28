"""
tests/unit/test_cmd_info.py — Unit tests for ``econflow info``.

Covers:
- Command runs without error even with no config files
- Platform section always shown
- Estimator registry always shown
- Data connector registry always shown
- Project config section shown when config.yaml exists
- Model table shown when models.yaml exists
- Outputs section shown when outputs.yaml exists
- Provenance section shows "No provenance record" when no run done yet
- Provenance section shows run details when run_metadata.json exists
- ESTIMATOR_REGISTRY and DATA_CONNECTOR_REGISTRY integrity
"""

from __future__ import annotations

import json
from pathlib import Path

import yaml
from typer.testing import CliRunner

from econflow.cli import app
from econflow.commands.info import (
    ESTIMATOR_REGISTRY,
    _load_connector_registry,
)

DATA_CONNECTOR_REGISTRY = _load_connector_registry()

runner = CliRunner()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

VALID_CONFIG = {
    "project": {"name": "unit_test_project", "version": "0.1.0"},
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

VALID_MODELS = {
    "models": [
        {
            "id": "pooled_ols",
            "label": "Pooled OLS",
            "estimator": "OLS",
            "dependent": "outcome",
            "regressors": ["treatment"],
        },
        {
            "id": "entity_fe",
            "label": "Entity FE",
            "estimator": "FE",
            "dependent": "outcome",
            "regressors": ["treatment"],
            "entity_effects": True,
        },
    ]
}

VALID_OUTPUTS = {
    "outputs": {
        "base_dir": "outputs",
        "tables": {
            "formats": ["csv", "latex"],
            "comparison_table": {"filename": "table_main"},
        },
    }
}


def _write(path: Path, data: dict) -> None:
    path.write_text(yaml.dump(data), encoding="utf-8")


def _invoke_info(cfg_path: Path, models_path: Path, out_path: Path) -> object:
    return runner.invoke(app, [
        "info",
        "--config", str(cfg_path),
        "--models", str(models_path),
        "--outputs", str(out_path),
    ])


# ---------------------------------------------------------------------------
# No config files — platform + registry still shown
# ---------------------------------------------------------------------------

def test_info_runs_without_any_config(tmp_path: Path) -> None:
    result = _invoke_info(
        tmp_path / "missing_config.yaml",
        tmp_path / "missing_models.yaml",
        tmp_path / "missing_outputs.yaml",
    )
    assert result.exit_code == 0


def test_info_shows_platform_section_always(tmp_path: Path) -> None:
    result = _invoke_info(
        tmp_path / "nc.yaml",
        tmp_path / "nm.yaml",
        tmp_path / "no.yaml",
    )
    assert "EconFlow" in result.output
    assert "Python" in result.output


def test_info_shows_estimator_registry_always(tmp_path: Path) -> None:
    result = _invoke_info(
        tmp_path / "nc.yaml",
        tmp_path / "nm.yaml",
        tmp_path / "no.yaml",
    )
    assert "OLS" in result.output or "estimator" in result.output.lower()


def test_info_shows_connector_registry_always(tmp_path: Path) -> None:
    result = _invoke_info(
        tmp_path / "nc.yaml",
        tmp_path / "nm.yaml",
        tmp_path / "no.yaml",
    )
    assert "csv" in result.output.lower() or "connector" in result.output.lower()


def test_info_mentions_no_config_when_missing(tmp_path: Path) -> None:
    result = _invoke_info(
        tmp_path / "nc.yaml",
        tmp_path / "nm.yaml",
        tmp_path / "no.yaml",
    )
    assert "config" in result.output.lower()


# ---------------------------------------------------------------------------
# With config files
# ---------------------------------------------------------------------------

def test_info_shows_project_name_when_config_present(tmp_path: Path) -> None:
    cfg = tmp_path / "config.yaml"
    m   = tmp_path / "models.yaml"
    o   = tmp_path / "outputs.yaml"
    _write(cfg, VALID_CONFIG)
    _write(m,   VALID_MODELS)
    _write(o,   VALID_OUTPUTS)

    result = _invoke_info(cfg, m, o)
    assert result.exit_code == 0
    assert "unit_test_project" in result.output


def test_info_shows_entity_col_when_config_present(tmp_path: Path) -> None:
    cfg = tmp_path / "config.yaml"
    m   = tmp_path / "models.yaml"
    o   = tmp_path / "outputs.yaml"
    _write(cfg, VALID_CONFIG)
    _write(m,   VALID_MODELS)
    _write(o,   VALID_OUTPUTS)

    result = _invoke_info(cfg, m, o)
    assert "entity" in result.output


def test_info_shows_model_ids_when_models_present(tmp_path: Path) -> None:
    cfg = tmp_path / "config.yaml"
    m   = tmp_path / "models.yaml"
    o   = tmp_path / "outputs.yaml"
    _write(cfg, VALID_CONFIG)
    _write(m,   VALID_MODELS)
    _write(o,   VALID_OUTPUTS)

    result = _invoke_info(cfg, m, o)
    assert "pooled_ols" in result.output
    assert "entity_fe" in result.output


def test_info_shows_output_base_dir_when_outputs_present(tmp_path: Path) -> None:
    cfg = tmp_path / "config.yaml"
    m   = tmp_path / "models.yaml"
    o   = tmp_path / "outputs.yaml"
    _write(cfg, VALID_CONFIG)
    _write(m,   VALID_MODELS)
    _write(o,   VALID_OUTPUTS)

    result = _invoke_info(cfg, m, o)
    assert "outputs" in result.output


# ---------------------------------------------------------------------------
# Provenance
# ---------------------------------------------------------------------------

def test_info_shows_no_provenance_when_outputs_dir_empty(tmp_path: Path) -> None:
    import copy
    out_cfg = copy.deepcopy(VALID_OUTPUTS)
    out_cfg["outputs"]["base_dir"] = str(tmp_path / "outputs")

    cfg = tmp_path / "config.yaml"
    m   = tmp_path / "models.yaml"
    o   = tmp_path / "outputs.yaml"
    _write(cfg, VALID_CONFIG)
    _write(m,   VALID_MODELS)
    _write(o,   out_cfg)

    result = _invoke_info(cfg, m, o)
    assert "No provenance" in result.output or "no provenance" in result.output.lower()


def test_info_shows_provenance_when_metadata_exists(tmp_path: Path) -> None:
    import copy
    outputs_dir = tmp_path / "outputs"
    prov_dir = outputs_dir / "provenance"
    prov_dir.mkdir(parents=True)

    meta = {
        "run_id": "abc-123",
        "timestamp": "2026-01-01T12:00:00+00:00",
        "econflow_version": "0.1.0",
        "models_run": ["pooled_ols", "entity_fe"],
    }
    (prov_dir / "run_metadata.json").write_text(
        json.dumps(meta), encoding="utf-8"
    )

    out_cfg = copy.deepcopy(VALID_OUTPUTS)
    out_cfg["outputs"]["base_dir"] = str(outputs_dir)

    cfg = tmp_path / "config.yaml"
    m   = tmp_path / "models.yaml"
    o   = tmp_path / "outputs.yaml"
    _write(cfg, VALID_CONFIG)
    _write(m,   VALID_MODELS)
    _write(o,   out_cfg)

    result = _invoke_info(cfg, m, o)
    assert result.exit_code == 0
    assert "abc-123" in result.output
    assert "2026" in result.output


# ---------------------------------------------------------------------------
# Static registry integrity
# ---------------------------------------------------------------------------

def test_estimator_registry_has_ols_and_fe() -> None:
    ids = {e["id"] for e in ESTIMATOR_REGISTRY}
    assert "ols" in ids
    assert "fe" in ids


def test_estimator_registry_all_have_required_keys() -> None:
    for est in ESTIMATOR_REGISTRY:
        assert "id" in est
        assert "label" in est
        assert "status" in est
        assert est["status"] in ("implemented", "stub", "deprecated")


def test_connector_registry_has_csv() -> None:
    ids = {c["id"] for c in DATA_CONNECTOR_REGISTRY}
    assert "csv" in ids


def test_connector_registry_all_have_required_keys() -> None:
    for conn in DATA_CONNECTOR_REGISTRY:
        assert "id" in conn
        assert "label" in conn
        assert "status" in conn


def test_ols_and_fe_are_implemented() -> None:
    for est in ESTIMATOR_REGISTRY:
        if est["id"] in ("ols", "fe"):
            assert est["status"] == "implemented", (
                f"Estimator {est['id']} should be implemented"
            )


def test_csv_connector_is_implemented() -> None:
    for conn in DATA_CONNECTOR_REGISTRY:
        if conn["id"] == "csv":
            assert conn["status"] == "implemented"
