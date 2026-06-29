"""
Shared fixtures for replication engine tests.

Provides a self-contained project directory with config, data, and
known expected outputs — used across all replication test modules.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest
import yaml

# ---------------------------------------------------------------------------
# Synthetic dataset
# ---------------------------------------------------------------------------

def _make_panel(seed: int = 42) -> pd.DataFrame:
    """Create a small deterministic 5-firm × 10-year panel dataset."""
    import numpy as np

    rng = np.random.default_rng(seed)
    firms = ["Alpha", "Beta", "Gamma", "Delta", "Epsilon"]
    years = list(range(2000, 2010))
    rows = []
    for firm in firms:
        fe = rng.normal(0, 1)
        for year in years:
            x1 = rng.uniform(10, 100)
            x2 = rng.uniform(1, 20)
            y = 2.5 * x1 + 0.8 * x2 + fe + rng.normal(0, 2)
            rows.append(
                {"firm": firm, "year": year, "invest": round(y, 4),
                 "value": round(x1, 4), "capital": round(x2, 4)}
            )
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Project fixture
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def project_dir(tmp_path_factory) -> Path:
    """
    A complete, valid EconFlow project directory used for replication tests.
    """
    root = tmp_path_factory.mktemp("replication_project")

    # config/config.yaml
    config_dir = root / "config"
    config_dir.mkdir()
    config_yaml = {
        "project": {"name": "replication_test", "description": "Test project"},
        "data": {
            "path": str(root / "data" / "panel.csv"),
            "entity_col": "firm",
            "time_col": "year",
            "required_columns": ["firm", "year", "invest", "value", "capital"],
        },
        "sample": {"start_year": 2000, "end_year": 2009},
        "variables": {"dependent": "invest", "regressors": ["value", "capital"]},
    }
    (config_dir / "config.yaml").write_text(yaml.dump(config_yaml), encoding="utf-8")

    # config/models.yaml
    models_yaml = {
        "models": [
            {"id": "ols_spec", "estimator": "ols", "label": "Pooled OLS"},
            {"id": "fe_spec", "estimator": "fe", "label": "Fixed Effects"},
        ]
    }
    (config_dir / "models.yaml").write_text(yaml.dump(models_yaml), encoding="utf-8")

    # config/outputs.yaml
    outputs_yaml = {
        "outputs": {
            "base_dir": str(root / "outputs"),
            "tables": {
                "dir": "tables",
                "comparison_table": {"filename": "comparison_table.csv"},
            },
        }
    }
    (config_dir / "outputs.yaml").write_text(yaml.dump(outputs_yaml), encoding="utf-8")

    # data/panel.csv
    data_dir = root / "data"
    data_dir.mkdir()
    df = _make_panel()
    data_path = data_dir / "panel.csv"
    df.to_csv(data_path, index=False)

    return root


@pytest.fixture(scope="session")
def project_dir_missing_data(tmp_path_factory) -> Path:
    """Project with config but no data file."""
    root = tmp_path_factory.mktemp("missing_data_project")
    config_dir = root / "config"
    config_dir.mkdir()

    config_yaml = {
        "project": {"name": "missing_data_test"},
        "data": {
            "path": str(root / "data" / "nonexistent.csv"),
            "entity_col": "firm",
            "time_col": "year",
            "required_columns": ["firm", "year", "y"],
        },
        "variables": {"dependent": "y", "regressors": ["x"]},
    }
    (config_dir / "config.yaml").write_text(yaml.dump(config_yaml), encoding="utf-8")
    (config_dir / "models.yaml").write_text(
        yaml.dump({"models": [{"id": "m1", "estimator": "ols"}]}), encoding="utf-8"
    )
    (config_dir / "outputs.yaml").write_text(
        yaml.dump({"outputs": {"base_dir": "outputs"}}), encoding="utf-8"
    )
    return root


@pytest.fixture(scope="session")
def project_dir_bad_estimator(tmp_path_factory) -> Path:
    """Project referencing an unregistered estimator."""
    root = tmp_path_factory.mktemp("bad_estimator_project")
    config_dir = root / "config"
    config_dir.mkdir()
    data_dir = root / "data"
    data_dir.mkdir()
    _make_panel().to_csv(data_dir / "panel.csv", index=False)

    config_yaml = {
        "project": {"name": "bad_estimator_test"},
        "data": {
            "path": str(data_dir / "panel.csv"),
            "entity_col": "firm",
            "time_col": "year",
            "required_columns": ["firm", "year", "invest", "value", "capital"],
        },
        "variables": {"dependent": "invest", "regressors": ["value"]},
    }
    (config_dir / "config.yaml").write_text(yaml.dump(config_yaml), encoding="utf-8")
    (config_dir / "models.yaml").write_text(
        yaml.dump({"models": [{"id": "m1", "estimator": "does_not_exist_42"}]}),
        encoding="utf-8",
    )
    (config_dir / "outputs.yaml").write_text(
        yaml.dump({"outputs": {"base_dir": "outputs"}}), encoding="utf-8"
    )
    return root


@pytest.fixture(scope="session")
def sample_panel_df() -> pd.DataFrame:
    return _make_panel()
