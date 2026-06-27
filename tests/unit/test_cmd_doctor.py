"""
tests/unit/test_cmd_doctor.py — Unit tests for ``econflow doctor``.

Tests cover:
- Command runs without error
- Exit code 0 when all required packages are present
- Output contains expected section headings
- Internal version-comparison helper
- External tool check helper (mocked)
"""

from __future__ import annotations

from unittest import mock

from typer.testing import CliRunner

from econflow.cli import app
from econflow.commands.doctor import (
    _check_external_tool,
    _check_latex,
    _check_package,
    _cmp_versions,
    _parse_version,
    run_doctor,
)

runner = CliRunner()


# ---------------------------------------------------------------------------
# CLI smoke test
# ---------------------------------------------------------------------------

def test_doctor_exits_zero() -> None:
    """doctor should exit 0 in the test environment where packages are installed."""
    result = runner.invoke(app, ["doctor"])
    # All core packages are installed in the dev environment
    assert result.exit_code == 0


def test_doctor_output_contains_system_section() -> None:
    result = runner.invoke(app, ["doctor"])
    assert "System" in result.output or "Python" in result.output


def test_doctor_output_contains_package_section() -> None:
    result = runner.invoke(app, ["doctor"])
    assert "pandas" in result.output or "Core" in result.output


def test_doctor_output_contains_external_tools_section() -> None:
    result = runner.invoke(app, ["doctor"])
    assert "git" in result.output.lower() or "External" in result.output


def test_doctor_output_contains_optional_section() -> None:
    result = runner.invoke(app, ["doctor"])
    assert "pytest" in result.output or "Optional" in result.output


# ---------------------------------------------------------------------------
# Version helpers
# ---------------------------------------------------------------------------

def test_parse_version_simple() -> None:
    assert _parse_version("2.1.0") == (2, 1, 0)


def test_parse_version_with_prerelease() -> None:
    # pre-release suffixes should be stripped
    assert _parse_version("2.1.0rc1")[0] == 2


def test_parse_version_short() -> None:
    assert _parse_version("3.10") == (3, 10)


def test_cmp_versions_newer_passes() -> None:
    assert _cmp_versions("2.2.0", "2.0.0") is True


def test_cmp_versions_equal_passes() -> None:
    assert _cmp_versions("2.0.0", "2.0.0") is True


def test_cmp_versions_older_fails() -> None:
    assert _cmp_versions("1.9.9", "2.0.0") is False


def test_cmp_versions_unknown_passes() -> None:
    # Unknown format — assume OK
    assert _cmp_versions("unknown", "2.0.0") is True


# ---------------------------------------------------------------------------
# _check_package
# ---------------------------------------------------------------------------

def test_check_package_installed() -> None:
    found, ver = _check_package("pandas", "pandas", "2.0.0")
    assert found is True
    assert ver != "not installed"


def test_check_package_missing() -> None:
    found, ver = _check_package(
        "nonexistent_pkg_xyz",
        "nonexistent_pkg_xyz",
        "1.0.0",
    )
    assert found is False
    assert "not installed" in ver


# ---------------------------------------------------------------------------
# _check_external_tool (mocked)
# ---------------------------------------------------------------------------

def test_check_external_tool_found() -> None:
    with mock.patch("shutil.which", return_value="/usr/bin/git"), \
         mock.patch("subprocess.run") as mock_run:
        mock_run.return_value = mock.Mock(
            stdout="git version 2.42.0\n", stderr="", returncode=0
        )
        found, ver = _check_external_tool("git")
    assert found is True
    assert "git version" in ver


def test_check_external_tool_not_found() -> None:
    with mock.patch("shutil.which", return_value=None):
        found, ver = _check_external_tool("nonexistent_tool_abc")
    assert found is False
    assert "not found" in ver


def test_check_external_tool_found_but_version_fails() -> None:
    with mock.patch("shutil.which", return_value="/usr/bin/sometool"), \
         mock.patch("subprocess.run", side_effect=OSError("fail")):
        found, ver = _check_external_tool("sometool")
    assert found is True
    assert "unknown" in ver


# ---------------------------------------------------------------------------
# _check_latex (mocked)
# ---------------------------------------------------------------------------

def test_check_latex_found_pdflatex() -> None:
    def fake_which(binary: str) -> str | None:
        return "/usr/bin/pdflatex" if binary == "pdflatex" else None

    with mock.patch("shutil.which", side_effect=fake_which), \
         mock.patch("subprocess.run") as mock_run:
        mock_run.return_value = mock.Mock(
            stdout="pdfTeX 3.141592653\n", stderr="", returncode=0
        )
        found, binary, ver = _check_latex()

    assert found is True
    assert binary == "pdflatex"
    assert "pdfTeX" in ver


def test_check_latex_not_found() -> None:
    with mock.patch("shutil.which", return_value=None):
        found, binary, ver = _check_latex()
    assert found is False
    assert binary == ""


# ---------------------------------------------------------------------------
# run_doctor return codes
# ---------------------------------------------------------------------------

def test_run_doctor_returns_zero_when_all_pass(capsys) -> None:
    from rich.console import Console

    console = Console(file=open("/dev/null", "w"))
    code = run_doctor(console)
    assert code == 0


def test_run_doctor_returns_one_when_required_package_missing() -> None:
    """Patch _check_package directly to simulate a missing required package."""
    import io

    from rich.console import Console

    from econflow.commands import doctor as doctor_mod

    def fake_check_package(pkg_name: str, dist_name: str, min_ver: str):
        if pkg_name == "pandas":
            return False, "not installed"
        return True, "99.0.0"

    console = Console(file=io.StringIO())
    with mock.patch.object(doctor_mod, "_check_package", side_effect=fake_check_package):
        code = run_doctor(console)

    assert code == 1
