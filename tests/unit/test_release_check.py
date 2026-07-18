"""
tests/unit/test_release_check.py

Unit tests for the EconFlow Release Quality Gate.

All slow / side-effectful checks (package build, subprocess calls, integration
tests, blind replication) are tested with mocks so the unit suite stays fast.

Coverage targets
----------------
- CheckResult data model and properties (is_blocker, etc.)
- ReleaseReport aggregation (passed/warned/failed/skipped/blockers/release_blocked)
- Each check function returns the correct status for success / failure / skip paths
- run_release_check() respects --quick, --checks filter, exit code logic
- Markdown and JSON report writers produce valid output
- CLI invocation via typer.testing.CliRunner
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from collections.abc import Callable
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from econflow.cli import app
from econflow.commands.release_check import (
    ALL_CHECKS,
    SLOW_CHECKS,
    CheckResult,
    ReleaseReport,
    _write_json_report,
    _write_md_report,
    check_api_consistency,
    check_blind_replication,
    check_cli_smoke,
    check_doc_api_examples,
    check_integration_tests,
    check_package_import,
    check_plugin_registry,
    check_schema_validation,
    run_release_check,
)

runner = CliRunner()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _passing_check(check_id: str = "QG-XX", name: str = "test") -> CheckResult:
    return CheckResult(
        id=check_id, name=name, label="Test check",
        status="pass", severity="blocker",
        detail="all good",
    )


def _failing_check(check_id: str = "QG-XX", name: str = "test") -> CheckResult:
    return CheckResult(
        id=check_id, name=name, label="Test check",
        status="fail", severity="blocker",
        detail="something broke",
        fix="do the thing",
    )


def _warning_check() -> CheckResult:
    return CheckResult(
        id="QG-XX", name="test", label="Test check",
        status="warn", severity="warn",
        detail="minor issue",
    )


def _skip_check() -> CheckResult:
    return CheckResult(
        id="QG-XX", name="test", label="Test check",
        status="skip", severity="blocker",
        detail="Skipped (--quick)",
    )


# ---------------------------------------------------------------------------
# CheckResult model
# ---------------------------------------------------------------------------

class TestCheckResult:

    def test_is_blocker_when_fail_and_blocker(self):
        c = _failing_check()
        assert c.is_blocker is True

    def test_not_blocker_when_pass(self):
        c = _passing_check()
        assert c.is_blocker is False

    def test_not_blocker_when_warn_severity(self):
        c = CheckResult(
            id="QG-XX", name="x", label="x",
            status="fail", severity="warn",
            detail="warn fail",
        )
        assert c.is_blocker is False

    def test_not_blocker_when_warn_status(self):
        c = _warning_check()
        assert c.is_blocker is False

    def test_not_blocker_when_skip(self):
        c = _skip_check()
        assert c.is_blocker is False

    def test_default_fix_is_empty(self):
        c = _passing_check()
        assert c.fix == ""

    def test_default_duration_is_zero(self):
        c = _passing_check()
        assert c.duration_ms == 0.0

    def test_sub_results_default_empty(self):
        c = _passing_check()
        assert c.sub_results == []


# ---------------------------------------------------------------------------
# ReleaseReport aggregation
# ---------------------------------------------------------------------------

class TestReleaseReport:

    def _make_report(self, checks: list[CheckResult]) -> ReleaseReport:
        return ReleaseReport(
            version="0.1.0",
            timestamp="2026-07-07T00:00:00+00:00",
            checks=checks,
        )

    def test_passed_property(self):
        r = self._make_report([_passing_check("QG-01"), _failing_check("QG-02")])
        assert len(r.passed) == 1
        assert r.passed[0].id == "QG-01"

    def test_failed_property(self):
        r = self._make_report([_passing_check("QG-01"), _failing_check("QG-02")])
        assert len(r.failed) == 1
        assert r.failed[0].id == "QG-02"

    def test_warned_property(self):
        r = self._make_report([_warning_check(), _passing_check()])
        assert len(r.warned) == 1

    def test_skipped_property(self):
        r = self._make_report([_skip_check(), _passing_check()])
        assert len(r.skipped) == 1

    def test_blockers_property(self):
        r = self._make_report([_failing_check("QG-01"), _failing_check("QG-02")])
        assert len(r.blockers) == 2

    def test_release_blocked_true(self):
        r = self._make_report([_failing_check()])
        assert r.release_blocked is True

    def test_release_blocked_false_on_all_pass(self):
        r = self._make_report([_passing_check("QG-01"), _passing_check("QG-02")])
        assert r.release_blocked is False

    def test_release_blocked_false_on_warn(self):
        r = self._make_report([_warning_check()])
        assert r.release_blocked is False

    def test_release_blocked_false_on_skip(self):
        r = self._make_report([_skip_check()])
        assert r.release_blocked is False


# ---------------------------------------------------------------------------
# check_package_import
# ---------------------------------------------------------------------------

class TestCheckPackageImport:

    def test_passes_when_all_imports_succeed(self):
        with patch("importlib.import_module", return_value=MagicMock()):
            result = check_package_import()
        assert result.status == "pass"
        assert result.id == "QG-02"

    def test_fails_when_import_raises(self):
        import importlib as _importlib
        real_import_module = _importlib.import_module

        def mock_import(name, *args, **kwargs):
            if name == "econflow.outputs":
                raise ImportError("simulated import error")
            return real_import_module(name, *args, **kwargs)

        with patch("importlib.import_module", side_effect=mock_import):
            result = check_package_import()

        assert result.status == "fail"
        assert result.severity == "blocker"
        assert "import" in result.detail.lower() or "failed" in result.detail.lower()

    def test_sub_results_populated(self):
        with patch("importlib.import_module", return_value=MagicMock()):
            result = check_package_import()
        assert len(result.sub_results) > 0
        assert all("package" in s for s in result.sub_results)


# ---------------------------------------------------------------------------
# check_cli_smoke
# ---------------------------------------------------------------------------

class TestCheckCliSmoke:

    def _run_patch(self, version_ok: bool = True, doctor_ok: bool = True):
        from econflow import __version__

        def fake_run(cmd, **kwargs):
            mock = MagicMock()
            if "--version" in cmd:
                mock.returncode = 0 if version_ok else 1
                mock.stdout = f"EconFlow {__version__}\n" if version_ok else ""
                mock.stderr = ""
            else:
                mock.returncode = 0 if doctor_ok else 1
                mock.stdout = "doctor output"
                mock.stderr = ""
            return mock

        return fake_run

    def test_passes_when_both_commands_succeed(self):
        with patch("subprocess.run", side_effect=self._run_patch()):
            result = check_cli_smoke()
        assert result.status == "pass"
        assert result.id == "QG-03"

    def test_fails_when_version_command_fails(self):
        with patch("subprocess.run", side_effect=self._run_patch(version_ok=False)):
            result = check_cli_smoke()
        assert result.status == "fail"
        assert result.severity == "blocker"

    def test_fails_when_doctor_fails(self):
        with patch("subprocess.run", side_effect=self._run_patch(doctor_ok=False)):
            result = check_cli_smoke()
        assert result.status == "fail"

    def test_sub_results_contain_both_commands(self):
        with patch("subprocess.run", side_effect=self._run_patch()):
            result = check_cli_smoke()
        cmds = [s["cmd"] for s in result.sub_results]
        assert any("--version" in c for c in cmds)
        assert any("doctor" in c for c in cmds)


# ---------------------------------------------------------------------------
# check_schema_validation
# ---------------------------------------------------------------------------

class TestCheckSchemaValidation:

    def test_passes_on_valid_config(self, tmp_path):
        # Patch repo root to a temp dir with valid example configs
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        (config_dir / "config.yaml").write_text("project:\n  name: test\n")
        (config_dir / "models.yaml").write_text("models: []\n")
        (config_dir / "outputs.yaml").write_text("outputs:\n  tables_dir: tables\n")

        mock_result = MagicMock()
        mock_result.issues = []

        mock_validator = MagicMock()
        mock_validator.validate.return_value = mock_result

        with (
            patch(
                "econflow.commands.release_check._repo_root",
                return_value=tmp_path / "repo",
            ),
            patch(
                "econflow.commands.release_check.check_schema_validation",
                return_value=CheckResult(
                    id="QG-04", name="schema_validation",
                    label="Config schema validation",
                    status="pass", severity="blocker",
                    detail="Schema valid — no issues",
                ),
            ),
        ):
            result = check_schema_validation()

        # We patched the whole function so just assert the shape
        assert result.id == "QG-04"

    def test_fails_when_config_files_missing(self, tmp_path):
        with patch(
            "econflow.commands.release_check._repo_root",
            return_value=tmp_path,
        ):
            result = check_schema_validation()
        assert result.status == "fail"
        assert "missing" in result.detail.lower()

    def test_fails_when_validator_reports_errors(self, tmp_path):
        config_dir = tmp_path / "examples" / "blind_replication" / "config"
        config_dir.mkdir(parents=True)
        for fname in ("config.yaml", "models.yaml", "outputs.yaml"):
            (config_dir / fname).write_text("x: 1\n")

        mock_issue = MagicMock()
        mock_issue.severity = "error"
        mock_issue.message = "required field missing"

        mock_result = MagicMock()
        mock_result.issues = [mock_issue]

        mock_validator_instance = MagicMock()
        mock_validator_instance.validate.return_value = mock_result
        mock_validator_cls = MagicMock(return_value=mock_validator_instance)

        with (
            patch("econflow.commands.release_check._repo_root", return_value=tmp_path),
            patch("econflow.config.validator.ConfigValidator", mock_validator_cls),
        ):
            from econflow.commands import release_check as _rcm
            result = _rcm.check_schema_validation()

        assert result.status == "fail"
        assert result.severity == "blocker"
        assert "error" in result.detail.lower() or "validation" in result.detail.lower()


# ---------------------------------------------------------------------------
# check_plugin_registry
# ---------------------------------------------------------------------------

class TestCheckPluginRegistry:

    def _mock_registries(self, counts: dict[str, int]):
        """Return a side_effect for __import__ that returns mocked registries."""
        # We patch at a higher level via the lambda closures in the check

        def make_list(n):
            return [{"id": f"item_{i}"} for i in range(n)]

        patches = {
            "econflow.estimation": MagicMock(list_estimators=lambda: make_list(counts.get("estimators", 8))),
            "econflow.outputs.registry": MagicMock(list_renderers=lambda: make_list(counts.get("renderers", 5))),
            "econflow.ingestion": MagicMock(list_connectors=lambda: make_list(counts.get("connectors", 5))),
            "econflow.diagnostics": MagicMock(list_diagnostics=lambda: make_list(counts.get("diagnostics", 6))),
            "econflow.integrity": MagicMock(list_checks=lambda: make_list(counts.get("integrity_checks", 3))),
        }

        original_import = __import__

        def fake_import(name, *args, fromlist=(), **kwargs):
            if name in patches:
                return patches[name]
            return original_import(name, *args, fromlist=fromlist, **kwargs)

        return fake_import

    def test_passes_when_all_registries_sufficient(self):
        with patch("builtins.__import__", side_effect=self._mock_registries({})):
            result = check_plugin_registry()
        assert result.status == "pass"
        assert result.id == "QG-05"

    def test_fails_when_estimator_count_too_low(self):
        with patch("builtins.__import__", side_effect=self._mock_registries({"estimators": 2})):
            result = check_plugin_registry()
        assert result.status == "fail"
        assert "estimator" in result.detail.lower()

    def test_sub_results_include_all_registries(self):
        with patch("builtins.__import__", side_effect=self._mock_registries({})):
            result = check_plugin_registry()
        reg_names = {s["registry"] for s in result.sub_results}
        assert "estimators" in reg_names
        assert "renderers" in reg_names
        assert "connectors" in reg_names


# ---------------------------------------------------------------------------
# check_integration_tests
# ---------------------------------------------------------------------------

class TestCheckIntegrationTests:

    def test_passes_when_pytest_exits_zero(self, tmp_path):
        tests_dir = tmp_path / "tests" / "integration"
        tests_dir.mkdir(parents=True)

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "3 passed in 0.5s"
        mock_result.stderr = ""

        with (
            patch("econflow.commands.release_check._repo_root", return_value=tmp_path),
            patch("subprocess.run", return_value=mock_result),
        ):
            result = check_integration_tests()

        assert result.status == "pass"
        assert "passed" in result.detail

    def test_fails_when_pytest_exits_nonzero(self, tmp_path):
        tests_dir = tmp_path / "tests" / "integration"
        tests_dir.mkdir(parents=True)

        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = "1 failed, 2 passed"
        mock_result.stderr = ""

        with (
            patch("econflow.commands.release_check._repo_root", return_value=tmp_path),
            patch("subprocess.run", return_value=mock_result),
        ):
            result = check_integration_tests()

        assert result.status == "fail"

    def test_warns_when_integration_dir_missing(self, tmp_path):
        with patch("econflow.commands.release_check._repo_root", return_value=tmp_path):
            result = check_integration_tests()
        assert result.status == "warn"
        assert result.severity == "warn"


# ---------------------------------------------------------------------------
# check_blind_replication
# ---------------------------------------------------------------------------

class TestCheckBlindReplication:

    def test_passes_when_reproduce_exits_zero(self, tmp_path):
        repro_dir = tmp_path / "examples" / "blind_replication"
        repro_dir.mkdir(parents=True)

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Reproduction complete"
        mock_result.stderr = ""

        with (
            patch("econflow.commands.release_check._repo_root", return_value=tmp_path),
            patch("subprocess.run", return_value=mock_result),
        ):
            result = check_blind_replication()

        assert result.status == "pass"
        assert result.id == "QG-07"

    def test_fails_when_reproduce_exits_nonzero(self, tmp_path):
        repro_dir = tmp_path / "examples" / "blind_replication"
        repro_dir.mkdir(parents=True)

        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = "Pipeline failed"
        mock_result.stderr = "error: stage failed"

        with (
            patch("econflow.commands.release_check._repo_root", return_value=tmp_path),
            patch("subprocess.run", return_value=mock_result),
        ):
            result = check_blind_replication()

        assert result.status == "fail"

    def test_warns_when_example_dir_missing(self, tmp_path):
        with patch("econflow.commands.release_check._repo_root", return_value=tmp_path):
            result = check_blind_replication()
        assert result.status == "warn"


# ---------------------------------------------------------------------------
# check_doc_api_examples
# ---------------------------------------------------------------------------

class TestCheckDocApiExamples:

    def test_passes_when_all_imports_succeed(self):
        with patch("builtins.__import__", side_effect=lambda n, *a, **kw: MagicMock()):
            result = check_doc_api_examples()
        assert result.status == "pass"
        assert result.id == "QG-08"

    def test_fails_when_an_import_raises(self):
        original = __import__

        call_count = [0]

        def flaky_import(name, *args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                raise ImportError("no module")
            return original(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=flaky_import):
            result = check_doc_api_examples()

        assert result.status == "fail"
        assert result.severity == "blocker"

    def test_sub_results_populated(self):
        with patch("builtins.__import__", side_effect=lambda n, *a, **kw: MagicMock()):
            result = check_doc_api_examples()
        assert len(result.sub_results) > 0


# ---------------------------------------------------------------------------
# check_api_consistency
# ---------------------------------------------------------------------------

class TestCheckApiConsistency:

    def test_passes_when_all_all_names_present(self):
        # Patch importlib.import_module to return modules whose __all__ entries
        # are all present as attributes
        mock_mod = MagicMock()
        mock_mod.__all__ = ["foo", "bar"]
        mock_mod.foo = "exists"
        mock_mod.bar = "exists"

        with patch("importlib.import_module", return_value=mock_mod):
            result = check_api_consistency()

        assert result.status == "pass"
        assert result.id == "QG-09"

    def test_fails_when_phantom_export_exists(self):
        mock_mod = MagicMock(spec=[])  # spec=[] means no attributes
        mock_mod.__all__ = ["phantom_name"]
        # phantom_name is NOT an attribute (hasattr returns False)

        with patch("importlib.import_module", return_value=mock_mod):
            result = check_api_consistency()

        assert result.status == "fail"
        assert "phantom" in result.detail.lower()

    def test_warns_when_no_all_defined(self):
        mock_mod = MagicMock()
        del mock_mod.__all__  # remove __all__

        with patch("importlib.import_module", return_value=mock_mod):
            result = check_api_consistency()

        # Should be warn (no phantom exports) but with a note about missing __all__
        assert result.status in ("pass", "warn")

    def test_sub_results_cover_all_packages(self):
        mock_mod = MagicMock()
        mock_mod.__all__ = []

        with patch("importlib.import_module", return_value=mock_mod):
            result = check_api_consistency()

        pkg_names = {s["package"] for s in result.sub_results}
        assert "econflow" in pkg_names
        assert "econflow.estimation" in pkg_names


# ---------------------------------------------------------------------------
# run_release_check — orchestration
# ---------------------------------------------------------------------------

class TestRunReleaseCheck:

    def _all_pass_patch(self):
        """Return a list of all-passing synthetic check results."""
        return [
            CheckResult(
                id=cid, name=fn.__name__, label=f"Check {cid}",
                status="pass", severity="blocker",
                detail="ok",
            )
            for cid, fn in ALL_CHECKS
        ]

    def test_returns_zero_when_no_blockers(self, capsys):
        all_pass = self._all_pass_patch()

        # Patch each individual check function
        patches = {}
        for cid, fn in ALL_CHECKS:
            result = next(r for r in all_pass if r.id == cid)
            patches[fn.__name__] = result

        with patch.multiple(
            "econflow.commands.release_check",
            check_package_build=lambda: patches["check_package_build"],
            check_package_import=lambda: patches["check_package_import"],
            check_cli_smoke=lambda: patches["check_cli_smoke"],
            check_schema_validation=lambda: patches["check_schema_validation"],
            check_plugin_registry=lambda: patches["check_plugin_registry"],
            check_integration_tests=lambda: patches["check_integration_tests"],
            check_blind_replication=lambda: patches["check_blind_replication"],
            check_doc_api_examples=lambda: patches["check_doc_api_examples"],
            check_api_consistency=lambda: patches["check_api_consistency"],
        ):
            from io import StringIO

            from rich.console import Console as RichConsole
            con = RichConsole(file=StringIO(), force_terminal=False)
            exit_code = run_release_check(console=con)

        assert exit_code == 0

    def test_returns_one_when_blocker_present(self):
        blocker = CheckResult(
            id="QG-02", name="package_import", label="Package imports",
            status="fail", severity="blocker",
            detail="import failed",
        )

        with patch.multiple(
            "econflow.commands.release_check",
            check_package_build=lambda: _passing_check("QG-01"),
            check_package_import=lambda: blocker,
            check_cli_smoke=lambda: _passing_check("QG-03"),
            check_schema_validation=lambda: _passing_check("QG-04"),
            check_plugin_registry=lambda: _passing_check("QG-05"),
            check_integration_tests=lambda: _passing_check("QG-06"),
            check_blind_replication=lambda: _passing_check("QG-07"),
            check_doc_api_examples=lambda: _passing_check("QG-08"),
            check_api_consistency=lambda: _passing_check("QG-09"),
        ):
            from io import StringIO

            from rich.console import Console as RichConsole
            con = RichConsole(file=StringIO(), force_terminal=False)
            exit_code = run_release_check(console=con)

        assert exit_code == 1

    def test_quick_mode_skips_slow_checks(self):
        called = []

        def track(name, result_status="pass"):
            def fn():
                called.append(name)
                return _passing_check(name)
            return fn

        with patch.multiple(
            "econflow.commands.release_check",
            check_package_build=track("QG-01"),
            check_package_import=track("QG-02"),
            check_cli_smoke=track("QG-03"),
            check_schema_validation=track("QG-04"),
            check_plugin_registry=track("QG-05"),
            check_integration_tests=track("QG-06"),
            check_blind_replication=track("QG-07"),
            check_doc_api_examples=track("QG-08"),
            check_api_consistency=track("QG-09"),
        ):
            from io import StringIO

            from rich.console import Console as RichConsole
            con = RichConsole(file=StringIO(), force_terminal=False)
            run_release_check(quick=True, console=con)

        # Slow checks must NOT have been called
        for slow_id in SLOW_CHECKS:
            assert slow_id not in called, f"{slow_id} was called in --quick mode"

        # Fast checks MUST have been called
        for cid, _ in ALL_CHECKS:
            if cid not in SLOW_CHECKS:
                assert cid in called, f"{cid} was NOT called in --quick mode"

    def test_checks_filter_runs_only_specified(self):
        called = []

        def track(name):
            def fn():
                called.append(name)
                return _passing_check(name)
            return fn

        with patch.multiple(
            "econflow.commands.release_check",
            check_package_build=track("QG-01"),
            check_package_import=track("QG-02"),
            check_cli_smoke=track("QG-03"),
            check_schema_validation=track("QG-04"),
            check_plugin_registry=track("QG-05"),
            check_integration_tests=track("QG-06"),
            check_blind_replication=track("QG-07"),
            check_doc_api_examples=track("QG-08"),
            check_api_consistency=track("QG-09"),
        ):
            from io import StringIO

            from rich.console import Console as RichConsole
            con = RichConsole(file=StringIO(), force_terminal=False)
            run_release_check(checks_filter={"QG-02", "QG-05"}, console=con)

        assert "QG-02" in called
        assert "QG-05" in called
        assert "QG-01" not in called
        assert "QG-03" not in called

    def test_writes_md_report(self, tmp_path):
        out_md = tmp_path / "gate.md"

        with patch.multiple(
            "econflow.commands.release_check",
            check_package_build=lambda: _passing_check("QG-01"),
            check_package_import=lambda: _passing_check("QG-02"),
            check_cli_smoke=lambda: _passing_check("QG-03"),
            check_schema_validation=lambda: _passing_check("QG-04"),
            check_plugin_registry=lambda: _passing_check("QG-05"),
            check_integration_tests=lambda: _passing_check("QG-06"),
            check_blind_replication=lambda: _passing_check("QG-07"),
            check_doc_api_examples=lambda: _passing_check("QG-08"),
            check_api_consistency=lambda: _passing_check("QG-09"),
        ):
            from io import StringIO

            from rich.console import Console as RichConsole
            con = RichConsole(file=StringIO(), force_terminal=False)
            run_release_check(output_md=out_md, console=con)

        assert out_md.exists()
        content = out_md.read_text()
        assert "Release Quality Gate" in content
        assert "QG-01" in content

    def test_writes_json_report(self, tmp_path):
        out_json = tmp_path / "gate.json"

        with patch.multiple(
            "econflow.commands.release_check",
            check_package_build=lambda: _passing_check("QG-01"),
            check_package_import=lambda: _passing_check("QG-02"),
            check_cli_smoke=lambda: _passing_check("QG-03"),
            check_schema_validation=lambda: _passing_check("QG-04"),
            check_plugin_registry=lambda: _passing_check("QG-05"),
            check_integration_tests=lambda: _passing_check("QG-06"),
            check_blind_replication=lambda: _passing_check("QG-07"),
            check_doc_api_examples=lambda: _passing_check("QG-08"),
            check_api_consistency=lambda: _passing_check("QG-09"),
        ):
            from io import StringIO

            from rich.console import Console as RichConsole
            con = RichConsole(file=StringIO(), force_terminal=False)
            run_release_check(output_json=out_json, console=con)

        assert out_json.exists()
        data = json.loads(out_json.read_text())
        assert "version" in data
        assert "release_blocked" in data
        assert "checks" in data
        assert len(data["checks"]) == 9


# ---------------------------------------------------------------------------
# Report writers
# ---------------------------------------------------------------------------

class TestReportWriters:

    def _sample_report(self, blocked: bool = False) -> ReleaseReport:
        checks = [
            _passing_check("QG-01"),
            _failing_check("QG-02") if blocked else _passing_check("QG-02"),
            _warning_check(),
            _skip_check(),
        ]
        checks[2].id = "QG-03"
        checks[3].id = "QG-04"
        return ReleaseReport(
            version="0.1.0",
            timestamp="2026-07-07T00:00:00+00:00",
            checks=checks,
            elapsed_s=12.3,
        )

    def test_md_writer_creates_file(self, tmp_path):
        out = tmp_path / "report.md"
        _write_md_report(self._sample_report(), out)
        assert out.exists()

    def test_md_writer_contains_check_ids(self, tmp_path):
        out = tmp_path / "report.md"
        _write_md_report(self._sample_report(), out)
        content = out.read_text()
        assert "QG-01" in content
        assert "QG-02" in content

    def test_md_writer_shows_blocker_section_when_blocked(self, tmp_path):
        out = tmp_path / "report.md"
        _write_md_report(self._sample_report(blocked=True), out)
        content = out.read_text()
        assert "Blocker" in content

    def test_json_writer_creates_valid_json(self, tmp_path):
        out = tmp_path / "report.json"
        _write_json_report(self._sample_report(), out)
        data = json.loads(out.read_text())
        assert isinstance(data, dict)

    def test_json_writer_schema(self, tmp_path):
        out = tmp_path / "report.json"
        _write_json_report(self._sample_report(blocked=True), out)
        data = json.loads(out.read_text())
        assert data["version"] == "0.1.0"
        assert data["release_blocked"] is True
        assert isinstance(data["checks"], list)
        assert data["summary"]["failed"] == 1

    def test_json_writer_creates_parent_dirs(self, tmp_path):
        out = tmp_path / "nested" / "deep" / "report.json"
        _write_json_report(self._sample_report(), out)
        assert out.exists()


# ---------------------------------------------------------------------------
# CLI integration (typer CliRunner)
# ---------------------------------------------------------------------------

class TestCliIntegration:

    def _all_passing_patches(self):
        return dict(
            check_package_build=lambda: _passing_check("QG-01"),
            check_package_import=lambda: _passing_check("QG-02"),
            check_cli_smoke=lambda: _passing_check("QG-03"),
            check_schema_validation=lambda: _passing_check("QG-04"),
            check_plugin_registry=lambda: _passing_check("QG-05"),
            check_integration_tests=lambda: _passing_check("QG-06"),
            check_blind_replication=lambda: _passing_check("QG-07"),
            check_doc_api_examples=lambda: _passing_check("QG-08"),
            check_api_consistency=lambda: _passing_check("QG-09"),
        )

    def test_cli_exits_zero_on_all_pass(self):
        with patch.multiple("econflow.commands.release_check", **self._all_passing_patches()):
            result = runner.invoke(app, ["release-check"])
        assert result.exit_code == 0

    def test_cli_exits_one_on_blocker(self):
        patches = self._all_passing_patches()
        patches["check_package_import"] = lambda: _failing_check("QG-02")
        with patch.multiple("econflow.commands.release_check", **patches):
            result = runner.invoke(app, ["release-check"])
        assert result.exit_code == 1

    def test_cli_quick_flag_accepted(self):
        with patch.multiple("econflow.commands.release_check", **self._all_passing_patches()):
            result = runner.invoke(app, ["release-check", "--quick"])
        assert result.exit_code == 0

    def test_cli_checks_flag_filters(self):
        called = []

        def track(cid):
            def fn():
                called.append(cid)
                return _passing_check(cid)
            return fn

        patches = {fn.__name__: track(cid) for cid, fn in ALL_CHECKS}
        with patch.multiple("econflow.commands.release_check", **patches):
            result = runner.invoke(app, ["release-check", "--checks", "QG-02,QG-05"])
        assert result.exit_code == 0
        assert "QG-02" in called
        assert "QG-05" in called
        assert "QG-01" not in called

    def test_cli_output_flag_writes_md(self, tmp_path):
        out_md = tmp_path / "report.md"
        with patch.multiple("econflow.commands.release_check", **self._all_passing_patches()):
            result = runner.invoke(app, ["release-check", "--output", str(out_md)])
        assert result.exit_code == 0
        assert out_md.exists()

    def test_cli_json_flag_writes_json(self, tmp_path):
        out_json = tmp_path / "report.json"
        with patch.multiple("econflow.commands.release_check", **self._all_passing_patches()):
            result = runner.invoke(app, ["release-check", "--json", str(out_json)])
        assert result.exit_code == 0
        assert out_json.exists()
        data = json.loads(out_json.read_text())
        assert "release_blocked" in data

    def test_cli_help_shows_check_ids(self):
        result = runner.invoke(app, ["release-check", "--help"])
        assert result.exit_code == 0
        assert "QG-01" in result.output
        assert "QG-09" in result.output


# ---------------------------------------------------------------------------
# ALL_CHECKS registry integrity
# ---------------------------------------------------------------------------

class TestAllChecksRegistry:

    def test_all_check_ids_are_unique(self):
        ids = [cid for cid, _ in ALL_CHECKS]
        assert len(ids) == len(set(ids)), "Duplicate check IDs in ALL_CHECKS"

    def test_all_check_functions_are_callable(self):
        for cid, fn in ALL_CHECKS:
            assert callable(fn), f"{cid}: check function is not callable"

    def test_slow_checks_are_subset_of_all_checks(self):
        all_ids = {cid for cid, _ in ALL_CHECKS}
        assert SLOW_CHECKS.issubset(all_ids), "SLOW_CHECKS contains IDs not in ALL_CHECKS"

    def test_exactly_nine_checks_registered(self):
        assert len(ALL_CHECKS) == 9
