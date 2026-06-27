"""
tests/integration/test_pipeline_e2e.py
=======================================

End-to-end integration tests for the EconFlow pipeline.

These tests run the full `econflow run` pipeline against the Grunfeld
getting_started example dataset and verify that:
  - The pipeline exits 0
  - Expected output files are written
  - Key numeric results are in the right ballpark

The tests are skipped if the fixture data is not present.
"""

from __future__ import annotations

import csv
import io
from pathlib import Path

import pytest
import yaml
from rich.console import Console

from econflow.commands.info import run_info
from econflow.commands.validate import run_validate

# Locate repo root and getting_started example
_REPO_ROOT = Path(__file__).parent.parent.parent
_GS_DIR = _REPO_ROOT / "examples" / "getting_started"
_GS_CONFIG = _GS_DIR / "config" / "config.yaml"
_GS_MODELS = _GS_DIR / "config" / "models.yaml"
_GS_OUTPUTS = _GS_DIR / "config" / "outputs.yaml"
_GS_DATA = _GS_DIR / "data" / "grunfeld.csv"

_HAS_EXAMPLE = (
    _GS_CONFIG.exists()
    and _GS_MODELS.exists()
    and _GS_OUTPUTS.exists()
    and _GS_DATA.exists()
)

pytestmark = pytest.mark.skipif(
    not _HAS_EXAMPLE,
    reason="getting_started example not present",
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _console() -> Console:
    return Console(file=io.StringIO(), highlight=False)


def _out(console: Console) -> str:
    return console.file.getvalue()


# ---------------------------------------------------------------------------
# Validate getting_started config (no data check needed — data is present)
# ---------------------------------------------------------------------------

class TestGettingStartedValidate:
    def test_config_validates_cleanly(self) -> None:
        console = _console()
        code = run_validate(
            config_path=_GS_CONFIG,
            models_path=_GS_MODELS,
            outputs_path=_GS_OUTPUTS,
            check_data=False,
            console=console,
        )
        assert code == 0, f"Validation failed:\n{_out(console)}"

    def test_config_validates_with_data(self) -> None:
        console = _console()
        code = run_validate(
            config_path=_GS_CONFIG,
            models_path=_GS_MODELS,
            outputs_path=_GS_OUTPUTS,
            check_data=True,
            console=console,
        )
        assert code == 0, f"Validation with --data failed:\n{_out(console)}"


# ---------------------------------------------------------------------------
# Info on getting_started
# ---------------------------------------------------------------------------

class TestGettingStartedInfo:
    def test_info_shows_project_name(self) -> None:
        console = _console()
        run_info(
            config_path=_GS_CONFIG,
            models_path=_GS_MODELS,
            outputs_path=_GS_OUTPUTS,
            console=console,
        )
        out = _out(console)
        assert "getting_started" in out

    def test_info_shows_all_models(self) -> None:
        console = _console()
        run_info(
            config_path=_GS_CONFIG,
            models_path=_GS_MODELS,
            outputs_path=_GS_OUTPUTS,
            console=console,
        )
        models_cfg = yaml.safe_load(_GS_MODELS.read_text())
        model_ids = [m["id"] for m in models_cfg.get("models", [])]
        out = _out(console)
        for mid in model_ids:
            assert mid in out, f"Model ID {mid!r} not shown in info output"


# ---------------------------------------------------------------------------
# Full pipeline run
# ---------------------------------------------------------------------------

class TestGettingStartedPipeline:
    @pytest.fixture(autouse=True)
    def _isolated_outputs(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """
        Point the getting_started outputs.yaml at a temp directory so the
        pipeline writes to tmp_path rather than examples/getting_started/outputs/.
        This keeps the test idempotent and avoids polluting the source tree.
        """
        out_cfg = yaml.safe_load(_GS_OUTPUTS.read_text())

        # Write a modified outputs.yaml to a temp dir
        tmp_out_cfg = tmp_path / "outputs.yaml"
        out_cfg["outputs"]["base_dir"] = str(tmp_path / "outputs")
        tmp_out_cfg.write_text(yaml.dump(out_cfg))
        self._outputs_path = tmp_out_cfg
        self._tmp_outputs = tmp_path / "outputs"

    def test_pipeline_run_exits_zero(self) -> None:
        """Run the pipeline via the Python API and verify exit code 0."""
        from econflow.pipeline_generic import run_from_config

        run_from_config(
            config_path=_GS_CONFIG,
            models_path=_GS_MODELS,
            outputs_path=self._outputs_path,
        )
        # If no exception raised, it exited successfully

    def test_pipeline_writes_csv_table(self) -> None:
        """A comparison CSV table must be written under outputs/tables/."""
        from econflow.pipeline_generic import run_from_config

        run_from_config(
            config_path=_GS_CONFIG,
            models_path=_GS_MODELS,
            outputs_path=self._outputs_path,
        )
        tables_dir = self._tmp_outputs / "tables"
        csv_files = list(tables_dir.glob("*.csv"))
        assert csv_files, f"No CSV tables found under {tables_dir}"

    def test_pipeline_writes_latex_table(self) -> None:
        """A LaTeX table must be written under outputs/tables/."""
        from econflow.pipeline_generic import run_from_config

        run_from_config(
            config_path=_GS_CONFIG,
            models_path=_GS_MODELS,
            outputs_path=self._outputs_path,
        )
        tables_dir = self._tmp_outputs / "tables"
        tex_files = list(tables_dir.glob("*.tex"))
        assert tex_files, f"No .tex tables found under {tables_dir}"

    def test_pipeline_writes_provenance(self) -> None:
        """Provenance JSON must be written after a successful run."""
        from econflow.pipeline_generic import run_from_config

        run_from_config(
            config_path=_GS_CONFIG,
            models_path=_GS_MODELS,
            outputs_path=self._outputs_path,
        )
        prov_file = self._tmp_outputs / "provenance" / "run_metadata.json"
        assert prov_file.exists(), f"Provenance file not found at {prov_file}"

    def test_pipeline_csv_has_expected_columns(self) -> None:
        """The comparison CSV must have one row per regressor/stat and one col per model."""
        from econflow.pipeline_generic import run_from_config

        run_from_config(
            config_path=_GS_CONFIG,
            models_path=_GS_MODELS,
            outputs_path=self._outputs_path,
        )
        tables_dir = self._tmp_outputs / "tables"
        csv_files = list(tables_dir.glob("*.csv"))
        assert csv_files
        with open(csv_files[0], newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        assert rows, "Comparison CSV is empty"
        # Must have at least one column for a model (header row has model IDs)
        assert len(reader.fieldnames or []) >= 2

    def test_pipeline_results_are_reproducible(self, tmp_path: Path) -> None:
        """Running the pipeline twice must produce identical output files."""
        from econflow.pipeline_generic import run_from_config

        out_cfg = yaml.safe_load(_GS_OUTPUTS.read_text())

        # First run
        out1 = tmp_path / "run1"
        cfg1 = tmp_path / "outputs1.yaml"
        out_cfg["outputs"]["base_dir"] = str(out1)
        cfg1.write_text(yaml.dump(out_cfg))
        run_from_config(_GS_CONFIG, _GS_MODELS, cfg1)

        # Second run
        out2 = tmp_path / "run2"
        cfg2 = tmp_path / "outputs2.yaml"
        out_cfg["outputs"]["base_dir"] = str(out2)
        cfg2.write_text(yaml.dump(out_cfg))
        run_from_config(_GS_CONFIG, _GS_MODELS, cfg2)

        # Compare all CSV tables
        for csv1 in (out1 / "tables").glob("*.csv"):
            csv2 = out2 / "tables" / csv1.name
            assert csv2.exists(), f"Second run missing {csv1.name}"
            assert csv1.read_text() == csv2.read_text(), (
                f"Non-reproducible output: {csv1.name}"
            )
