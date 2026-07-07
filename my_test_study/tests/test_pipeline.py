"""
tests/test_pipeline.py — smoke tests for my_test_study.

Run with:
    pytest tests/
"""

from pathlib import Path

import pytest

# Locate project root (one level above tests/)
PROJECT_ROOT = Path(__file__).parent.parent


def test_config_files_exist() -> None:
    """All three config files must be present before running the pipeline."""
    assert (PROJECT_ROOT / "config" / "config.yaml").exists(), (
        "config/config.yaml not found — run `econflow init` or create it manually"
    )
    assert (PROJECT_ROOT / "config" / "models.yaml").exists(), (
        "config/models.yaml not found"
    )
    assert (PROJECT_ROOT / "config" / "outputs.yaml").exists(), (
        "config/outputs.yaml not found"
    )


def test_data_file_exists() -> None:
    """Processed panel CSV must exist before estimation."""
    data_file = PROJECT_ROOT / "data" / "processed" / "panel.csv"
    assert data_file.exists(), (
        f"Panel CSV not found at {data_file}. "
        "Run scripts/01_download_data.py and scripts/02_clean_data.py first."
    )


@pytest.mark.skipif(
    not (PROJECT_ROOT / "data" / "processed" / "panel.csv").exists(),
    reason="panel.csv not yet created",
)
def test_pipeline_runs_without_error() -> None:
    """End-to-end smoke test: run the pipeline and verify output tables exist."""
    import subprocess
    import sys

    result = subprocess.run(
        [
            sys.executable, "-m", "econflow.cli", "run",
            "--config",  str(PROJECT_ROOT / "config" / "config.yaml"),
            "--models",  str(PROJECT_ROOT / "config" / "models.yaml"),
            "--outputs", str(PROJECT_ROOT / "config" / "outputs.yaml"),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"Pipeline exited {result.returncode}:\n{result.stdout}\n{result.stderr}"
    )
    # At least one table should have been written
    tables_dir = PROJECT_ROOT / "outputs" / "tables"
    csv_tables = list(tables_dir.glob("*.csv"))
    assert csv_tables, f"No CSV tables found in {tables_dir} after pipeline run"
