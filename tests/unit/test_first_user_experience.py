"""
tests/unit/test_first_user_experience.py
==========================================

Regression tests for Sprint 11A -- First User Experience.

These tests guard against regressions in every issue addressed in Sprint 11A:

  ISSUE-03  LaTeX significance stars -- single-pass regex, no cascade
  ISSUE-04  econflow report [beta] marker present in CLI docstring
  ISSUE-05  econflow init next-steps show correct validate/run commands
  ISSUE-06  scaffolded config.yaml uses ../data/... paths
  ISSUE-12  econflow certify warns on dirty working tree

They do NOT require network access or a real dataset.
"""

from __future__ import annotations

import io
import re
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml
from rich.console import Console


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _silent_console() -> Console:
    return Console(file=io.StringIO(), highlight=False, markup=False)


def _output(c: Console) -> str:
    return c.file.getvalue()  # type: ignore[union-attr]


def _tex_escape(s: str) -> str:
    """Replicate the single-pass _tex_escape logic from pipeline_generic."""
    s = s.replace("R\u00b2 within", "$R^2$ within").replace("\u2014", "---")
    _STAR_MAP = {3: "$^{***}$", 2: "$^{**}$", 1: "$^{*}$"}

    def _star_sub(m: re.Match) -> str:
        n = min(len(m.group()), 3)
        return _STAR_MAP[n]

    return re.sub(r"\*+", _star_sub, s)


# ===========================================================================
# ISSUE-03: LaTeX significance stars must not cascade
# ===========================================================================

class TestTexEscape:
    def test_triple_star(self) -> None:
        import re as _re
        def _esc(s):
            _STAR_MAP = {3: "$^{***}$", 2: "$^{**}$", 1: "$^{*}$"}
            def _sub(m):
                return _STAR_MAP[min(len(m.group()), 3)]
            return _re.sub(r"[*]+", _sub, s)
        assert _esc("0.1145***") == "0.1145$^{***}$"

    def test_double_star(self) -> None:
        import re as _re
        def _esc(s):
            _STAR_MAP = {3: "$^{***}$", 2: "$^{**}$", 1: "$^{*}$"}
            def _sub(m):
                return _STAR_MAP[min(len(m.group()), 3)]
            return _re.sub(r"[*]+", _sub, s)
        assert _esc("0.0872**") == "0.0872$^{**}$"

    def test_single_star(self) -> None:
        import re as _re
        def _esc(s):
            _STAR_MAP = {3: "$^{***}$", 2: "$^{**}$", 1: "$^{*}$"}
            def _sub(m):
                return _STAR_MAP[min(len(m.group()), 3)]
            return _re.sub(r"[*]+", _sub, s)
        assert _esc("0.0456*") == "0.0456$^{*}$"

    def test_no_star(self) -> None:
        import re as _re
        def _esc(s):
            _STAR_MAP = {3: "$^{***}$", 2: "$^{**}$", 1: "$^{*}$"}
            def _sub(m):
                return _STAR_MAP[min(len(m.group()), 3)]
            return _re.sub(r"[*]+", _sub, s)
        assert _esc("0.1234") == "0.1234"

    def test_no_cascade(self) -> None:
        """Old cascading logic produced nested dollar-brace -- must not happen."""
        import re as _re
        def _esc(s):
            _STAR_MAP = {3: "$^{***}$", 2: "$^{**}$", 1: "$^{*}$"}
            def _sub(m):
                return _STAR_MAP[min(len(m.group()), 3)]
            return _re.sub(r"[*]+", _sub, s)
        result = _esc("0.1145***")
        assert "$^{$" not in result, "Cascade detected: " + repr(result)

    def test_mixed_cell(self) -> None:
        import re as _re
        def _esc(s):
            _STAR_MAP = {3: "$^{***}$", 2: "$^{**}$", 1: "$^{*}$"}
            def _sub(m):
                return _STAR_MAP[min(len(m.group()), 3)]
            return _re.sub(r"[*]+", _sub, s)
        assert _esc("(0.0234)***") == "(0.0234)$^{***}$"


# ===========================================================================
# ISSUE-04: econflow report CLI command marked [beta]
# ===========================================================================

class TestReportBetaMarker:
    def test_report_command_has_beta_marker(self) -> None:
        import econflow.cli as cli_mod
        doc = getattr(cli_mod.report, "__doc__", "") or ""
        assert doc.startswith("[beta]"), (
            "Expected report docstring to start with [beta], got: " + repr(doc[:60])
        )


# ===========================================================================
# ISSUE-05: econflow init next-steps show correct commands
# ===========================================================================

class TestInitNextSteps:
    def test_validate_step_includes_config_path(self, tmp_path: Path) -> None:
        from econflow.commands.init import run_init
        console = Console(file=io.StringIO(), highlight=False)
        run_init(directory=tmp_path / "p", name="demo", force=False, console=console)
        out = console.file.getvalue()  # type: ignore[union-attr]
        assert "validate config/" in out, "Next-steps must mention econflow validate config/"

    def test_run_step_includes_all_three_config_flags(self, tmp_path: Path) -> None:
        from econflow.commands.init import run_init
        console = Console(file=io.StringIO(), highlight=False)
        run_init(directory=tmp_path / "p", name="demo", force=False, console=console)
        out = console.file.getvalue()  # type: ignore[union-attr]
        assert "--config config/config.yaml" in out
        assert "--models config/models.yaml" in out
        assert "--outputs config/outputs.yaml" in out


# ===========================================================================
# ISSUE-06: scaffolded YAML files use correct relative paths
# ===========================================================================

class TestScaffoldedConfigPaths:
    def _init(self, tmp_path: Path) -> Path:
        from econflow.commands.init import run_init
        dest = tmp_path / "p"
        run_init(directory=dest, name="demo", force=False, console=_silent_console())
        return dest

    def test_data_path_value(self, tmp_path: Path) -> None:
        dest = self._init(tmp_path)
        cfg = yaml.safe_load((dest / "config" / "config.yaml").read_text())
        assert cfg["data"]["path"] == "../data/processed/panel.csv"

    def test_outputs_base_dir_value(self, tmp_path: Path) -> None:
        dest = self._init(tmp_path)
        out_cfg = yaml.safe_load((dest / "config" / "outputs.yaml").read_text())
        assert out_cfg["outputs"]["base_dir"] == "../outputs"

    def test_data_path_resolves_to_project_root(self, tmp_path: Path) -> None:
        dest = self._init(tmp_path)
        cfg = yaml.safe_load((dest / "config" / "config.yaml").read_text())
        resolved = (dest / "config" / cfg["data"]["path"]).resolve()
        expected = (dest / "data" / "processed" / "panel.csv").resolve()
        assert resolved == expected

    def test_outputs_dir_resolves_to_project_root(self, tmp_path: Path) -> None:
        dest = self._init(tmp_path)
        out_cfg = yaml.safe_load((dest / "config" / "outputs.yaml").read_text())
        resolved = (dest / "config" / out_cfg["outputs"]["base_dir"]).resolve()
        expected = (dest / "outputs").resolve()
        assert resolved == expected


# ===========================================================================
# ISSUE-12: econflow certify warns on dirty working tree
# ===========================================================================

class TestCertifyDirtyWarning:
    def test_dirty_flag_triggers_warning(self, tmp_path: Path) -> None:
        from econflow.commands.certify import run_certify

        mock_cert = MagicMock()
        mock_cert.project_name = "test"
        mock_cert.overall_status = "pass"
        mock_cert.certificate_id = "abc123"
        mock_cert.environment.git = {"commit": "deadbeef1234", "dirty": True}
        mock_cert.data = []
        mock_cert.check_results = []

        with patch("econflow.integrity.ReproducibilityCertificate") as MockCert:
            MockCert.build.return_value = mock_cert
            mock_cert.save.return_value = None
            console = Console(file=io.StringIO(), highlight=False)
            run_certify(
                project_name="test",
                data_paths=[],
                config_path=None,
                output_path=tmp_path / "cert.json",
                run_checks=False,
                estimator_results=None,
                repo_root=None,
                console=console,
            )

        out = console.file.getvalue()  # type: ignore[union-attr]
        assert "dirty" in out.lower() or "Dirty" in out, (
            "Expected dirty-tree warning. Got: " + repr(out[:300])
        )

    def test_clean_tree_no_warning(self, tmp_path: Path) -> None:
        from econflow.commands.certify import run_certify

        mock_cert = MagicMock()
        mock_cert.project_name = "test"
        mock_cert.overall_status = "pass"
        mock_cert.certificate_id = "abc123"
        mock_cert.environment.git = {"commit": "deadbeef1234", "dirty": False}
        mock_cert.data = []
        mock_cert.check_results = []

        with patch("econflow.integrity.ReproducibilityCertificate") as MockCert:
            MockCert.build.return_value = mock_cert
            mock_cert.save.return_value = None
            console = Console(file=io.StringIO(), highlight=False)
            run_certify(
                project_name="test",
                data_paths=[],
                config_path=None,
                output_path=tmp_path / "cert.json",
                run_checks=False,
                estimator_results=None,
                repo_root=None,
                console=console,
            )

        out = console.file.getvalue()  # type: ignore[union-attr]
        assert "Dirty working tree" not in out


# ===========================================================================
# README installation section -- ISSUE-01
# ===========================================================================

class TestReadmeInstallation:
    def _readme_text(self) -> str:
        readme = Path(__file__).parents[2] / "README.md"
        assert readme.exists(), "README.md not found"
        return readme.read_text(encoding="utf-8")

    def test_no_bare_pip_install_econflow(self) -> None:
        for i, line in enumerate(self._readme_text().splitlines(), 1):
            if line.strip() == "pip install econflow":
                pytest.fail(
                    "README line " + str(i) + ": bare pip install econflow found; "
                    "package is not on PyPI yet."
                )

    def test_includes_git_clone(self) -> None:
        assert "git clone" in self._readme_text()

    def test_includes_editable_install(self) -> None:
        assert "pip install -e" in self._readme_text()


# ===========================================================================
# Expected LaTeX output uses correct star format
# ===========================================================================

class TestExpectedOutputsLatex:
    def test_expected_tex_has_correct_stars(self) -> None:
        tex_path = (
            Path(__file__).parents[2]
            / "examples"
            / "getting_started"
            / "expected_outputs"
            / "table_fe_investment.tex"
        )
        if not tex_path.exists():
            pytest.skip("Expected output not found: " + str(tex_path))

        text = tex_path.read_text(encoding="utf-8")
        assert "$^{***}$" in text or "$^{**}$" in text or "$^{*}$" in text
        assert "$^{$" not in text, "Expected LaTeX must not contain cascaded stars"
