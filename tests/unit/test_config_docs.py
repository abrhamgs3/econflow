"""
tests/unit/test_config_docs.py -- Tests for automatic configuration documentation.
"""

from __future__ import annotations

from pathlib import Path

import yaml
from typer.testing import CliRunner

from econflow.cli import app

runner = CliRunner()

# ---------------------------------------------------------------------------
# Minimal valid config fixtures
# ---------------------------------------------------------------------------

_MINIMAL_CONFIG = {
    "project": {"name": "test", "version": "0.1.0"},
    "data": {
        "path": "data/panel.csv",
        "entity_col": "entity",
        "time_col": "time",
    },
    "variables": {
        "dependent": "outcome",
        "regressors": ["treatment"],
    },
}

_MINIMAL_MODELS = {
    "models": [
        {
            "id": "ols1",
            "label": "OLS",
            "estimator": "OLS",
            "dependent": "outcome",
            "regressors": ["treatment"],
        }
    ]
}

_MINIMAL_OUTPUTS = {
    "outputs": {
        "base_dir": "outputs/",
        "tables": {
            "comparison_table": {
                "filename": "comparison_table",
                "models": ["ols1"],
            }
        },
    }
}


def _write_valid_configs(tmp_path: Path) -> None:
    (tmp_path / "config.yaml").write_text(yaml.dump(_MINIMAL_CONFIG))
    (tmp_path / "models.yaml").write_text(yaml.dump(_MINIMAL_MODELS))
    (tmp_path / "outputs.yaml").write_text(yaml.dump(_MINIMAL_OUTPUTS))


# ---------------------------------------------------------------------------
# Tests for generate_config_reference()
# ---------------------------------------------------------------------------

class TestGenerateConfigReference:

    def test_returns_string(self):
        from econflow.config.docs import generate_config_reference
        result = generate_config_reference()
        assert isinstance(result, str)
        assert len(result) > 1000

    def test_markdown_has_allowed_column(self):
        from econflow.config.docs import generate_config_reference
        md = generate_config_reference(format="markdown")
        assert "| Allowed |" in md

    def test_markdown_has_type_column(self):
        from econflow.config.docs import generate_config_reference
        md = generate_config_reference(format="markdown")
        assert "| Type |" in md

    def test_markdown_has_default_column(self):
        from econflow.config.docs import generate_config_reference
        md = generate_config_reference(format="markdown")
        assert "| Default |" in md

    def test_markdown_has_description_column(self):
        from econflow.config.docs import generate_config_reference
        md = generate_config_reference(format="markdown")
        assert "| Description |" in md

    def test_markdown_has_examples(self):
        from econflow.config.docs import generate_config_reference
        md = generate_config_reference(format="markdown")
        assert "*Examples:*" in md

    def test_se_type_literal_allowed_values(self):
        from econflow.config.docs import generate_config_reference
        md = generate_config_reference(format="markdown")
        assert "'robust'" in md
        assert "'clustered'" in md
        assert "'classical'" in md

    def test_required_fields_marked(self):
        from econflow.config.docs import generate_config_reference
        md = generate_config_reference(format="markdown")
        assert "*(required)*" in md

    def test_all_three_yaml_sections_present(self):
        from econflow.config.docs import generate_config_reference
        md = generate_config_reference(format="markdown")
        assert "## `config.yaml`" in md
        assert "## `models.yaml`" in md
        assert "## `outputs.yaml`" in md

    def test_text_format_has_allowed_lines(self):
        from econflow.config.docs import generate_config_reference
        txt = generate_config_reference(format="text")
        assert "allowed:" in txt

    def test_text_format_no_markdown_headers(self):
        from econflow.config.docs import generate_config_reference
        txt = generate_config_reference(format="text")
        assert "## `" not in txt

    def test_auto_generated_notice_present(self):
        from econflow.config.docs import generate_config_reference
        md = generate_config_reference(format="markdown")
        assert "Auto-generated" in md
        assert "econflow docs config" in md

    def test_validate_command_hint_present(self):
        from econflow.config.docs import generate_config_reference
        md = generate_config_reference(format="markdown")
        assert "econflow validate" in md


# ---------------------------------------------------------------------------
# Tests for _allowed_values_str()
# ---------------------------------------------------------------------------

class TestAllowedValuesStr:

    def test_literal_produces_pipe_list(self):
        from typing import Literal

        from econflow.config.docs import _allowed_values_str

        class _FI:
            annotation = Literal["a", "b", "c"]
            metadata = []

        result = _allowed_values_str(_FI())
        assert "'a'" in result
        assert "'b'" in result
        assert "'c'" in result
        assert "|" in result

    def test_unconstrained_field_returns_empty(self):
        from econflow.config.docs import _allowed_values_str

        class _FI:
            annotation = str
            metadata = []

        result = _allowed_values_str(_FI())
        assert result == ""


# ---------------------------------------------------------------------------
# Tests for write_config_reference()
# ---------------------------------------------------------------------------

class TestWriteConfigReference:

    def test_writes_to_default_path(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        from econflow.config.docs import write_config_reference
        dest = write_config_reference()
        assert dest.exists()
        content = dest.read_text()
        assert "# EconFlow Configuration Reference" in content

    def test_writes_to_custom_path(self, tmp_path):
        from econflow.config.docs import write_config_reference
        custom = tmp_path / "subdir" / "ref.md"
        dest = write_config_reference(path=custom)
        assert dest.exists()
        assert dest == custom.resolve()

    def test_creates_parent_directories(self, tmp_path):
        from econflow.config.docs import write_config_reference
        nested = tmp_path / "a" / "b" / "c" / "ref.md"
        dest = write_config_reference(path=nested)
        assert dest.exists()

    def test_text_format_written(self, tmp_path):
        from econflow.config.docs import write_config_reference
        dest = write_config_reference(path=tmp_path / "ref.txt", format="text")
        assert "ECONFLOW CONFIGURATION REFERENCE" in dest.read_text()

    def test_default_output_path_constant(self):
        from econflow.config.docs import DEFAULT_OUTPUT_PATH
        assert DEFAULT_OUTPUT_PATH == "docs/reference/configuration.md"


# ---------------------------------------------------------------------------
# CLI tests -- econflow docs config
# ---------------------------------------------------------------------------

class TestDocsCommand:

    def test_docs_config_writes_file(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        result = runner.invoke(app, ["docs", "config"])
        assert result.exit_code == 0, result.output
        dest = tmp_path / "docs" / "reference" / "configuration.md"
        assert dest.exists()
        assert "# EconFlow Configuration Reference" in dest.read_text()

    def test_docs_config_stdout(self):
        result = runner.invoke(app, ["docs", "config", "--stdout"])
        assert result.exit_code == 0
        assert "EconFlow Configuration Reference" in result.output

    def test_docs_config_text_stdout(self):
        result = runner.invoke(app, ["docs", "config", "--text", "--stdout"])
        assert result.exit_code == 0
        assert "ECONFLOW CONFIGURATION REFERENCE" in result.output

    def test_docs_config_custom_output(self, tmp_path):
        out = tmp_path / "myref.md"
        result = runner.invoke(app, ["docs", "config", "--output", str(out)])
        assert result.exit_code == 0
        assert out.exists()
        assert "| Allowed |" in out.read_text()

    def test_docs_config_output_contains_allowed_column(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        result = runner.invoke(app, ["docs", "config"])
        assert result.exit_code == 0
        content = (tmp_path / "docs" / "reference" / "configuration.md").read_text()
        assert "| Allowed |" in content

    def test_docs_config_output_contains_se_type_values(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        runner.invoke(app, ["docs", "config"])
        content = (tmp_path / "docs" / "reference" / "configuration.md").read_text()
        assert "'robust'" in content

    def test_docs_unknown_topic_exits_1(self):
        result = runner.invoke(app, ["docs", "nonexistent"])
        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# CLI tests -- econflow validate config/
# ---------------------------------------------------------------------------

class TestValidateDocsIntegration:

    def test_valid_config_no_doc_hint_in_error(self, tmp_path):
        """Valid config: no error, so exit code 0."""
        _write_valid_configs(tmp_path)
        result = runner.invoke(app, ["validate", str(tmp_path)])
        assert result.exit_code == 0

    def test_invalid_config_shows_doc_reference(self, tmp_path):
        """Invalid config: output should mention the reference doc."""
        bad = {"project": {"name": "x"}}
        (tmp_path / "config.yaml").write_text(yaml.dump(bad))
        (tmp_path / "models.yaml").write_text(yaml.dump(_MINIMAL_MODELS))
        (tmp_path / "outputs.yaml").write_text(yaml.dump(_MINIMAL_OUTPUTS))
        result = runner.invoke(app, ["validate", str(tmp_path)])
        assert result.exit_code != 0
        assert "docs/reference/configuration.md" in result.output

    def test_validate_dir_argument_accepted(self, tmp_path):
        """Positional directory argument is accepted."""
        _write_valid_configs(tmp_path)
        result = runner.invoke(app, ["validate", str(tmp_path)])
        assert result.exit_code == 0

    def test_validate_missing_files_exits_1(self, tmp_path):
        """Missing YAML files should produce errors."""
        result = runner.invoke(app, ["validate", str(tmp_path)])
        assert result.exit_code != 0
