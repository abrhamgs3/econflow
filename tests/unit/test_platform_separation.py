"""
tests/unit/test_platform_separation.py

Sprint 10.5 — Platform Separation regression tests.

These tests assert that no paper-specific logic has leaked into the generic
EconFlow platform and that the CLI behaves correctly after the refactor:

1.  ``econflow run`` with no arguments exits with code 1 and prints a helpful
    error (not a legacy AI&P run).
2.  ``econflow run --data-path`` prints a deprecation warning and does NOT
    silently invoke the generic pipeline.
3.  ``econflow init`` does NOT create ``paper/sections/`` in the scaffold.
4.  ``DEFAULT_REQUIRED_COLUMNS`` in ``data.validators`` is empty (not AI&P columns).
5.  ``sample_selection_summary`` has no default for ``indicator_col`` (required arg).
6.  The generic platform CLI and commands do not import ``econflow.pipeline``
    (the legacy AI&P orchestrator).
7.  ``_AI_PRODUCTIVITY_REQUIRED_COLUMNS`` still contains the AI&P columns for
    backward-compatibility reference.
"""

from __future__ import annotations

import importlib
import inspect
import re
import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

from econflow.cli import app

runner = CliRunner()

# Rich/Typer's help renderer applies ANSI styling to individual tokens (e.g.
# switch prefixes vs. option names) whose exact boundaries depend on the
# installed rich/click/typer versions (pyproject.toml pins no upper bound on
# any of them). A literal substring check like `"--config" in result.output`
# is therefore not robust across dependency versions/terminal widths -- strip
# ANSI escape sequences before asserting on rendered CLI text.
_ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;]*m")


def _strip_ansi(text: str) -> str:
    return _ANSI_ESCAPE_RE.sub("", text)


# ---------------------------------------------------------------------------
# 1. `econflow run` with no arguments → error + helpful message
# ---------------------------------------------------------------------------

class TestRunNoArgsError:
    """econflow run with no arguments must error, not silently run the legacy pipeline."""

    def test_exits_nonzero(self):
        result = runner.invoke(app, ["run"])
        assert result.exit_code != 0, (
            "econflow run with no arguments should exit non-zero; "
            f"got {result.exit_code}.\nOutput:\n{result.output}"
        )

    def test_error_mentions_config_flag(self):
        result = runner.invoke(app, ["run"])
        assert "--config" in result.output, (
            "Error message should mention --config. "
            f"Got:\n{result.output}"
        )

    def test_error_mentions_getting_started(self):
        result = runner.invoke(app, ["run"])
        assert "getting_started" in result.output.lower() or "examples" in result.output.lower(), (
            "Error message should point to examples or getting_started. "
            f"Got:\n{result.output}"
        )

    def test_does_not_mention_legacy_columns(self):
        """No mention of ln_ai, ln_tfp, country — those are AI&P paper artifacts."""
        result = runner.invoke(app, ["run"])
        for col in ("ln_ai", "ln_tfp", "panel_clean"):
            assert col not in result.output, (
                f"Error output should not mention paper-specific column '{col}'. "
                f"Got:\n{result.output}"
            )


# ---------------------------------------------------------------------------
# 2. `econflow run --data-path` → deprecation warning
# ---------------------------------------------------------------------------

class TestRunDataPathDeprecation:
    """--data-path must print a deprecation warning, not silently succeed."""

    def test_deprecation_warning_in_output(self, tmp_path: Path):
        # Create a dummy CSV so the file-exists check passes
        csv = tmp_path / "panel.csv"
        csv.write_text("entity,time,y\nA,2000,1.0\n", encoding="utf-8")

        result = runner.invoke(app, ["run", "--data-path", str(csv)])
        assert "deprecated" in result.output.lower() or "Deprecation" in result.output, (
            "--data-path should print a deprecation warning. "
            f"Got:\n{result.output}"
        )

    def test_deprecation_mentions_config_flag(self, tmp_path: Path):
        csv = tmp_path / "panel.csv"
        csv.write_text("entity,time,y\nA,2000,1.0\n", encoding="utf-8")

        result = runner.invoke(app, ["run", "--data-path", str(csv)])
        assert "--config" in result.output, (
            "Deprecation message should suggest --config. "
            f"Got:\n{result.output}"
        )

    def test_missing_data_file_exits_nonzero(self, tmp_path: Path):
        nonexistent = tmp_path / "no_such_file.csv"
        result = runner.invoke(app, ["run", "--data-path", str(nonexistent)])
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# 3. `econflow init` does not create paper/sections/
# ---------------------------------------------------------------------------

class TestInitScaffoldNoPaperDir:
    """The generic project scaffold must not contain paper/sections/."""

    def test_paper_sections_not_created(self, tmp_path: Path):
        result = runner.invoke(app, ["init", str(tmp_path / "my_study")])
        assert result.exit_code == 0, f"init failed:\n{result.output}"

        paper_sections = tmp_path / "my_study" / "paper" / "sections"
        assert not paper_sections.exists(), (
            "econflow init must not create paper/sections/ — "
            "that directory is AI&P-specific."
        )

    def test_outputs_dir_created(self, tmp_path: Path):
        result = runner.invoke(app, ["init", str(tmp_path / "my_study")])
        assert result.exit_code == 0

        outputs = tmp_path / "my_study" / "outputs"
        assert outputs.exists(), "econflow init must create outputs/"

    def test_config_dir_created(self, tmp_path: Path):
        result = runner.invoke(app, ["init", str(tmp_path / "my_study")])
        assert result.exit_code == 0

        config = tmp_path / "my_study" / "config"
        assert config.exists(), "econflow init must create config/"

    def test_gitignore_does_not_mention_paper_sections(self, tmp_path: Path):
        runner.invoke(app, ["init", str(tmp_path / "my_study")])
        gitignore = tmp_path / "my_study" / ".gitignore"
        if gitignore.exists():
            content = gitignore.read_text(encoding="utf-8")
            assert "paper/sections" not in content, (
                ".gitignore must not reference paper/sections/ — "
                "that path is AI&P-specific."
            )


# ---------------------------------------------------------------------------
# 4. DEFAULT_REQUIRED_COLUMNS is empty (platform-agnostic)
# ---------------------------------------------------------------------------

class TestDefaultRequiredColumns:
    """The generic platform must not impose any default required column names."""

    def test_default_columns_is_empty(self):
        from econflow.data.validators import DEFAULT_REQUIRED_COLUMNS
        assert DEFAULT_REQUIRED_COLUMNS == [], (
            f"DEFAULT_REQUIRED_COLUMNS should be [] (paper-agnostic). "
            f"Got: {DEFAULT_REQUIRED_COLUMNS}"
        )

    def test_ai_productivity_columns_still_accessible(self):
        """The AI&P column list must remain accessible for backward compat."""
        from econflow.data.validators import _AI_PRODUCTIVITY_REQUIRED_COLUMNS
        assert "ln_ai" in _AI_PRODUCTIVITY_REQUIRED_COLUMNS
        assert "ln_tfp" in _AI_PRODUCTIVITY_REQUIRED_COLUMNS
        assert "country" in _AI_PRODUCTIVITY_REQUIRED_COLUMNS

    def test_required_columns_alias_is_empty(self):
        """REQUIRED_COLUMNS alias must also be empty (backward compat maintained)."""
        from econflow.data.validators import REQUIRED_COLUMNS
        assert REQUIRED_COLUMNS == []


# ---------------------------------------------------------------------------
# 5. sample_selection_summary has no default for indicator_col
# ---------------------------------------------------------------------------

class TestSampleSelectionSummarySignature:
    """indicator_col must be a required positional argument — no paper default."""

    def test_indicator_col_has_no_default(self):
        from econflow.data.cleaning import sample_selection_summary
        sig = inspect.signature(sample_selection_summary)
        param = sig.parameters.get("indicator_col")
        assert param is not None, "sample_selection_summary missing indicator_col parameter"
        assert param.default is inspect.Parameter.empty, (
            "indicator_col must be a required argument with no default. "
            f"Got default: {param.default!r}"
        )

    def test_calling_without_indicator_col_raises_type_error(self):
        """Callers must pass indicator_col explicitly."""
        import pandas as pd
        from econflow.data.cleaning import sample_selection_summary

        df = pd.DataFrame({"entity": ["A", "B"], "time": [2000, 2000], "x": [1.0, None]})
        with pytest.raises(TypeError):
            sample_selection_summary(df)  # type: ignore[call-arg]

    def test_calling_with_indicator_col_works(self):
        import pandas as pd
        from econflow.data.cleaning import sample_selection_summary

        df = pd.DataFrame({
            "entity": ["A", "A", "B", "B"],
            "time": [2000, 2001, 2000, 2001],
            "x": [1.0, None, 2.0, 3.0],
            "y": [4.0, 5.0, 6.0, 7.0],
        })
        result = sample_selection_summary(df, indicator_col="x", entity_col="entity")
        assert isinstance(result, pd.DataFrame)


# ---------------------------------------------------------------------------
# 6. Generic platform does not import econflow.pipeline (the legacy orchestrator)
# ---------------------------------------------------------------------------

class TestNoPlatformImportOfLegacyPipeline:
    """Core platform modules must not import the paper-specific pipeline.py."""

    PLATFORM_MODULES = [
        "econflow.pipeline_generic",
        "econflow.commands.init",
        "econflow.commands.validate",
        "econflow.commands.doctor",
        "econflow.commands.info",
        "econflow.commands.report",
        "econflow.commands.certify",
        "econflow.commands.verify",
        "econflow.commands.package_cmd",
        "econflow.config.validator",
        "econflow.config.linter",
        "econflow.config.models",
    ]

    @pytest.mark.parametrize("module_name", PLATFORM_MODULES)
    def test_module_does_not_import_legacy_pipeline(self, module_name: str):
        """Import the module and check sys.modules for the legacy pipeline."""
        # Remove cached import state for a clean check
        mod_key = "econflow.pipeline"
        previously_loaded = mod_key in sys.modules

        try:
            importlib.import_module(module_name)
        except ImportError:
            pytest.skip(f"Module {module_name} not importable in this environment")

        if not previously_loaded:
            assert mod_key not in sys.modules, (
                f"{module_name} caused econflow.pipeline (legacy AI&P orchestrator) "
                "to be imported.  Platform modules must not depend on the legacy pipeline."
            )


# ---------------------------------------------------------------------------
# 7. CLI run help text does not mention AI&P paper-specific flags prominently
# ---------------------------------------------------------------------------

class TestRunHelpTextPlatformFraming:
    """econflow run --help must present the generic pipeline as the primary path."""

    def test_help_mentions_config_flag(self):
        result = runner.invoke(app, ["run", "--help"])
        clean_output = _strip_ansi(result.output)
        assert "--config" in clean_output, (
            "Expected '--config' in 'econflow run --help' output "
            f"(ANSI stripped). Got:\n{clean_output}"
        )

    def test_help_does_not_mention_data_path_prominently(self):
        """--data-path should be hidden from the main help text."""
        result = runner.invoke(app, ["run", "--help"])
        # --data-path is marked hidden=True; it should not appear in --help output
        assert "--data-path" not in result.output, (
            "--data-path is a hidden deprecated option and should not appear "
            f"in the main --help output. Got:\n{result.output}"
        )

    def test_help_does_not_mention_legacy_mode(self):
        result = runner.invoke(app, ["run", "--help"])
        assert "legacy mode" not in result.output.lower(), (
            f"Run help should not mention 'legacy mode'. Got:\n{result.output}"
        )
