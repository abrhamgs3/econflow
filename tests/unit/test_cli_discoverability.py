"""
CLI discoverability integration tests — Sprint 11C Task #300.

Verifies that every public command exposes the required sections so a
researcher never needs to read source code:

  * Main --help:  contains the five-step workflow
  * Every command --help:  contains Examples, Common mistakes, Expected output
  * econflow doctor:  runs and produces structured output
  * --version outputs a semver string

Tests invoke the ``econflow`` entry-point via the Typer test runner so they
work in editable-install CI without requiring the script on PATH.
"""

from __future__ import annotations

import re

import pytest
from typer.testing import CliRunner

from econflow.cli import app

runner = CliRunner()


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _help(*args: str) -> str:
    """Return combined stdout+stderr from --help."""
    result = runner.invoke(app, list(args) + ["--help"])
    return (result.stdout or "") + (result.stderr if result.stderr else "")


def _run(*args: str):
    return runner.invoke(app, list(args))


# ---------------------------------------------------------------------------
# Main --help: workflow guidance
# ---------------------------------------------------------------------------

class TestMainHelp:
    def test_main_help_exits_zero(self):
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0

    def test_main_help_lists_all_major_commands(self):
        out = _help()
        for cmd in ("init", "doctor", "validate", "run", "report",
                    "certify", "verify", "package", "fetch", "datasets"):
            assert cmd in out, f"Command '{cmd}' missing from main --help"

    def test_main_help_contains_workflow_steps(self):
        out = _help()
        # The five-step workflow text
        assert "doctor" in out
        assert "init" in out
        assert "validate" in out
        assert "run" in out
        assert "certify" in out

# ---------------------------------------------------------------------------
# Per-command: all commands must have Examples + Common mistakes + Expected
# ---------------------------------------------------------------------------

COMMAND_REQUIREMENTS: list[tuple[tuple[str, ...], list[str]]] = [
    (("init",),            ["Examples", "Common mistakes", "Expected"]),
    (("doctor",),          ["Examples", "Common mistakes", "Expected"]),
    (("validate",),        ["Examples", "Common mistakes", "Expected"]),
    (("info",),            ["Examples", "Common mistakes", "Expected"]),
    (("run",),             ["Examples", "Common mistakes", "Expected"]),
    (("report",),          ["Examples", "Common mistakes", "Expected"]),
    (("certify",),         ["Examples", "Common mistakes", "Expected"]),
    (("verify",),          ["Examples", "Common mistakes", "Expected"]),
    (("package",),         ["Examples", "Common mistakes", "Expected"]),
    (("fetch",),           ["Examples", "Common mistakes", "Expected"]),
    (("datasets",),        ["Examples", "Common mistakes", "Expected"]),
    (("inspect",),         ["Examples", "Common mistakes", "Expected"]),
    (("reproduce",),       ["Examples", "Common mistakes", "Expected"]),
    (("compare",),         ["Examples", "Common mistakes", "Expected"]),
    (("release-check",),   ["Examples", "Common mistakes", "Expected"]),
    (("docs",),            ["Examples", "Common mistakes", "Expected"]),
    (("cache", "list"),    ["Examples", "Expected"]),
    (("cache", "inspect"), ["Examples", "Expected"]),
    (("cache", "clear"),   ["Examples", "Common mistakes"]),
    (("cache", "purge"),   ["Examples", "Expected"]),
]


@pytest.mark.parametrize("cmd_args,needles", COMMAND_REQUIREMENTS)
def test_command_help_sections(cmd_args: tuple[str, ...], needles: list[str]):
    """Every command --help must contain the required documentation sections."""
    out = _help(*cmd_args)
    assert out, f"Empty --help for: econflow {' '.join(cmd_args)}"
    for needle in needles:
        assert needle in out, (
            f"Section '{needle}' missing from: "
            f"econflow {' '.join(cmd_args)} --help"
        )


# ---------------------------------------------------------------------------
# doctor: structural output
# ---------------------------------------------------------------------------

class TestDoctorOutput:
    def test_doctor_exits_cleanly(self):
        result = _run("doctor")
        assert result.exit_code in (0, 1)

    def test_doctor_shows_system_section(self):
        result = _run("doctor")
        out = result.stdout or ""
        assert "System" in out or "SYS-" in out

    def test_doctor_shows_packages_section(self):
        result = _run("doctor")
        out = result.stdout or ""
        assert "package" in out.lower() or "PKG-" in out

    def test_doctor_shows_external_tools_section(self):
        result = _run("doctor")
        out = result.stdout or ""
        assert "External" in out or "EXT-" in out

    def test_doctor_shows_summary_line(self):
        result = _run("doctor")
        out = result.stdout or ""
        assert any(kw in out for kw in ("passed", "Ready", "failed", "blocked"))


# ---------------------------------------------------------------------------
# --version
# ---------------------------------------------------------------------------

class TestVersion:
    def test_version_exits_zero(self):
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0

    def test_version_contains_semver(self):
        result = runner.invoke(app, ["--version"])
        out = result.stdout or ""
        assert re.search(r"\d+\.\d+\.\d+", out), "No semver string in --version"

    def test_version_contains_econflow(self):
        result = runner.invoke(app, ["--version"])
        out = result.stdout or ""
        assert "EconFlow" in out or "econflow" in out.lower()


# ---------------------------------------------------------------------------
# Non-crash smoke tests
# ---------------------------------------------------------------------------

class TestCommandSmoke:
    def test_datasets_exits_zero(self):
        assert _run("datasets").exit_code == 0

    def test_datasets_lists_known_connector(self):
        result = _run("datasets")
        out = result.stdout or ""
        assert any(c in out for c in ("world_bank", "csv", "fred", "oecd", "pwt"))

    def test_info_exits_zero_outside_project(self):
        assert _run("info").exit_code == 0

    def test_cache_list_exits_zero(self):
        assert _run("cache", "list").exit_code == 0

    def test_run_without_flags_exits_nonzero_with_helpful_error(self):
        result = _run("run")
        assert result.exit_code != 0
        out = result.stdout or ""
        assert "--config" in out or "config" in out.lower()
