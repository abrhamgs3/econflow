"""
econflow.commands.doctor — ``econflow doctor`` command implementation.

Performs a comprehensive environment health check and returns a structured
report with pass/warn/fail status for each item.

Checks performed
----------------
System
  [SYS-01]  Python version >= 3.10
  [SYS-02]  Operating system (info only)
  [SYS-03]  CPU count and model (info only)
  [SYS-04]  Total RAM (info only)

Core Python packages (required for any pipeline run)
  [PKG-*]   pandas, numpy, statsmodels, linearmodels, matplotlib,
             scipy, typer, rich, pyyaml

External tools
  [EXT-01]  git            — version control and provenance
  [EXT-02]  LaTeX          — PDF table / paper rendering (pdflatex / xelatex / lualatex)
  [EXT-03]  pandoc         — document conversion
  [EXT-04]  uv             — fast Python package manager (optional)
  [EXT-05]  pip            — Python package installer

Optional Python packages
  [OPT-01]  pytest         — running the test suite
  [OPT-02]  ruff           — code linting
  [OPT-03]  pyarrow        — Parquet I/O support
  [OPT-04]  jupyter        — notebook support
  [OPT-05]  streamlit      — interactive dashboard

Exit codes
----------
0   All required checks pass (warnings allowed)
1   One or more required checks fail
"""

from __future__ import annotations

import importlib.metadata
import os
import platform
import shutil
import subprocess
import sys
from dataclasses import dataclass
from typing import Literal

from rich.console import Console
from rich.table import Table

from econflow.commands._shared import STATUS_ICONS

# ---------------------------------------------------------------------------
# Result model
# ---------------------------------------------------------------------------

Status = Literal["pass", "warn", "fail", "info"]


@dataclass
class EnvCheck:
    """Result of a single environment check."""

    code: str
    label: str
    status: Status
    detail: str
    fix: str = ""


# ---------------------------------------------------------------------------
# Package specifications
# ---------------------------------------------------------------------------

# (package_name, import_name, min_version, required)
_CORE_PACKAGES: list[tuple[str, str, str, bool]] = [
    ("pandas",       "pandas",       "2.0.0",  True),
    ("numpy",        "numpy",        "1.24.0", True),
    ("statsmodels",  "statsmodels",  "0.14.0", True),
    ("linearmodels", "linearmodels", "5.3.0",  True),
    ("matplotlib",   "matplotlib",   "3.7.0",  True),
    ("scipy",        "scipy",        "1.10.0", True),
    ("typer",        "typer",        "0.12.0", True),
    ("rich",         "rich",         "13.0.0", True),
    ("pyyaml",       "PyYAML",       "6.0.0",  True),
]

_OPTIONAL_PACKAGES: list[tuple[str, str, str]] = [
    ("pytest",    "pytest",    "8.0.0"),
    ("ruff",      "ruff",      "0.4.0"),
    ("pyarrow",   "pyarrow",   "12.0.0"),
    ("jupyter",   "jupyter",   "1.0.0"),
    ("streamlit", "streamlit", "1.35.0"),
]

# External tools: (binary_name, friendly_name, required)
_EXTERNAL_TOOLS: list[tuple[str, str, bool]] = [
    ("git",      "Git",    False),
    ("pandoc",   "Pandoc", False),
]

# Package managers checked under EXT
_PKG_MANAGER_TOOLS: list[tuple[str, str]] = [
    ("uv",  "uv  (fast Python package manager)"),
    ("pip", "pip (Python package installer)"),
]

# LaTeX flavours: try in order, stop at first found
_LATEX_BINARIES = ["pdflatex", "xelatex", "lualatex"]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _parse_version(version_str: str) -> tuple[int, ...]:
    """Parse a version string into a tuple of ints for comparison."""
    parts = []
    for part in version_str.split(".")[:3]:
        try:
            parts.append(int(part.split("-")[0].split("a")[0].split("b")[0].split("rc")[0]))
        except ValueError:
            parts.append(0)
    return tuple(parts)


def _cmp_versions(installed: str, minimum: str) -> bool:
    """Return True if *installed* >= *minimum*.

    Returns True for unrecognised version strings (e.g. ``"unknown"``,
    ``"dev"``) so that unusual dev or editable installs don't trigger
    spurious warnings.
    """
    # If the installed version string contains no digits it cannot be compared
    # meaningfully — assume it is OK (e.g. a dev/editable install).
    if not any(c.isdigit() for c in installed):
        return True
    try:
        return _parse_version(installed) >= _parse_version(minimum)
    except Exception:
        return True  # assume OK on any unexpected error


def _get_ram_gb() -> str:
    """Return total RAM as a human-readable string, e.g. '15.8 GB'."""
    # Prefer psutil — most accurate cross-platform
    try:
        import psutil  # type: ignore[import-untyped]
        total = psutil.virtual_memory().total
        return f"{total / (1024 ** 3):.1f} GB"
    except ImportError:
        pass

    # Linux fallback: /proc/meminfo
    try:
        with open("/proc/meminfo", encoding="utf-8") as fh:
            for line in fh:
                if line.startswith("MemTotal:"):
                    kb = int(line.split()[1])
                    return f"{kb / (1024 ** 2):.1f} GB"
    except OSError:
        pass

    # Windows fallback: ctypes GlobalMemoryStatusEx
    try:
        import ctypes

        class _MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]

        status = _MEMORYSTATUSEX()
        status.dwLength = ctypes.sizeof(_MEMORYSTATUSEX)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status))  # type: ignore[attr-defined]
        return f"{status.ullTotalPhys / (1024 ** 3):.1f} GB"
    except Exception:
        pass

    return "(unavailable — install psutil for RAM info)"


def _check_package(
    pkg_name: str,
    dist_name: str,
    min_ver: str,
) -> tuple[bool, str]:
    """Return (found, version_or_error_message)."""
    try:
        ver = importlib.metadata.version(dist_name)
        return True, ver
    except importlib.metadata.PackageNotFoundError:
        pass
    # Fallback: try importing and checking __version__
    try:
        mod = __import__(pkg_name)
        ver = getattr(mod, "__version__", "unknown")
        return True, ver
    except ImportError:
        return False, "not installed"


def _check_external_tool(binary: str) -> tuple[bool, str]:
    """Return (found, version_string)."""
    path = shutil.which(binary)
    if path is None:
        return False, "not found on PATH"
    try:
        result = subprocess.run(
            [binary, "--version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        raw = (result.stdout or result.stderr).strip()
        first_line = raw.split("\n")[0] if raw else "(version unknown)"
        return True, first_line
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return True, "(version unknown)"


def _check_latex() -> tuple[bool, str, str]:
    """Return (found, binary_name, version_line)."""
    for binary in _LATEX_BINARIES:
        path = shutil.which(binary)
        if path is None:
            continue
        try:
            result = subprocess.run(
                [binary, "--version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            raw = (result.stdout or result.stderr).strip()
            first_line = raw.split("\n")[0] if raw else "(version unknown)"
            return True, binary, first_line
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            return True, binary, "(version unknown)"
    return False, "", ""


# ---------------------------------------------------------------------------
# Check suites
# ---------------------------------------------------------------------------

def _run_system_checks() -> list[EnvCheck]:
    checks: list[EnvCheck] = []

    # Python version
    py_ver = platform.python_version()
    py_ok = sys.version_info >= (3, 10)
    checks.append(EnvCheck(
        code="SYS-01",
        label=f"Python {py_ver}",
        status="pass" if py_ok else "fail",
        detail=py_ver if py_ok else f"{py_ver} — need ≥ 3.10",
        fix="" if py_ok else "Install Python 3.10+ from https://www.python.org",
    ))

    # OS info (always info)
    os_str = f"{platform.system()} {platform.release()} ({platform.machine()})"
    checks.append(EnvCheck(
        code="SYS-02",
        label="Operating system",
        status="info",
        detail=os_str,
    ))

    # CPU info
    cpu_count = os.cpu_count() or 0
    cpu_model = platform.processor() or platform.machine() or "unknown"
    cpu_detail = f"{cpu_count} logical core(s)"
    if cpu_model and cpu_model != "unknown":
        cpu_detail = f"{cpu_count} logical core(s) — {cpu_model}"
    checks.append(EnvCheck(
        code="SYS-03",
        label="CPU",
        status="info",
        detail=cpu_detail,
    ))

    # RAM info
    ram_detail = _get_ram_gb()
    checks.append(EnvCheck(
        code="SYS-04",
        label="RAM",
        status="info",
        detail=ram_detail,
    ))

    return checks


def _run_package_checks() -> list[EnvCheck]:
    checks: list[EnvCheck] = []
    for i, (pkg_name, dist_name, min_ver, required) in enumerate(_CORE_PACKAGES, start=1):
        found, ver_or_err = _check_package(pkg_name, dist_name, min_ver)
        if not found:
            checks.append(EnvCheck(
                code=f"PKG-{i:02d}",
                label=pkg_name,
                status="fail" if required else "warn",
                detail=ver_or_err,
                fix=f"pip install {pkg_name}>={min_ver}",
            ))
        elif not _cmp_versions(ver_or_err, min_ver):
            checks.append(EnvCheck(
                code=f"PKG-{i:02d}",
                label=f"{pkg_name} {ver_or_err}",
                status="warn",
                detail=f"Installed {ver_or_err} — recommend ≥ {min_ver}",
                fix=f"pip install --upgrade {pkg_name}>={min_ver}",
            ))
        else:
            checks.append(EnvCheck(
                code=f"PKG-{i:02d}",
                label=f"{pkg_name} {ver_or_err}",
                status="pass",
                detail="",
            ))
    return checks


def _run_external_checks() -> list[EnvCheck]:
    checks: list[EnvCheck] = []

    # Git
    git_found, git_ver = _check_external_tool("git")
    checks.append(EnvCheck(
        code="EXT-01",
        label="git",
        status="pass" if git_found else "warn",
        detail=git_ver if git_found else "not found — provenance commits will fail",
        fix="" if git_found else "Install Git: https://git-scm.com",
    ))

    # LaTeX
    latex_found, latex_bin, latex_ver = _check_latex()
    checks.append(EnvCheck(
        code="EXT-02",
        label=f"LaTeX ({latex_bin})" if latex_found else "LaTeX",
        status="pass" if latex_found else "warn",
        detail=latex_ver if latex_found else (
            "no LaTeX installation found — .tex tables cannot be compiled to PDF"
        ),
        fix="" if latex_found else (
            "Install TeX Live (Linux/macOS) or MiKTeX (Windows): "
            "https://www.latex-project.org/get/"
        ),
    ))

    # Pandoc
    pandoc_found, pandoc_ver = _check_external_tool("pandoc")
    checks.append(EnvCheck(
        code="EXT-03",
        label="pandoc",
        status="pass" if pandoc_found else "warn",
        detail=pandoc_ver if pandoc_found else "not found — document conversion unavailable",
        fix="" if pandoc_found else "Install Pandoc: https://pandoc.org/installing.html",
    ))

    # Package managers (uv, pip) — informational / warn if missing
    for i, (binary, friendly) in enumerate(_PKG_MANAGER_TOOLS, start=4):
        found, ver = _check_external_tool(binary)
        checks.append(EnvCheck(
            code=f"EXT-{i:02d}",
            label=friendly,                           # fixed label, version in detail
            status="pass" if found else "warn",
            detail=ver if found else "not found on PATH",
            fix="" if found else (
                "Install uv: https://docs.astral.sh/uv/"
                if binary == "uv" else ""
            ),
        ))

    return checks


def _run_optional_checks() -> list[EnvCheck]:
    checks: list[EnvCheck] = []
    for i, (pkg_name, dist_name, min_ver) in enumerate(_OPTIONAL_PACKAGES, start=1):
        found, ver_or_err = _check_package(pkg_name, dist_name, min_ver)
        if found:

            checks.append(EnvCheck(
                code=f"OPT-{i:02d}",
                label=f"{pkg_name} {ver_or_err}",
                status="pass",
                detail="",
            ))
        else:
            checks.append(EnvCheck(
                code=f"OPT-{i:02d}",
                label=pkg_name,
                status="warn",
                detail="Optional -- not installed",
                fix=f"pip install {pkg_name}>={min_ver}",
            ))
    return checks


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

# STATUS_ICONS imported from ._shared (includes pass/warn/fail/skip/info)
_STATUS_ICON = STATUS_ICONS


def _render(checks: list[EnvCheck], title: str, console: Console) -> None:
    table = Table(
        show_header=False,
        box=None,
        padding=(0, 1, 0, 0),
        title=f"[bold]{title}[/bold]",
        title_justify="left",
        title_style="",
    )
    table.add_column("", width=2)
    table.add_column("Code", style="dim", width=7)
    table.add_column("Label", min_width=28)
    table.add_column("Detail", style="dim")

    for c in checks:
        icon = _STATUS_ICON[c.status]
        detail = c.detail
        if c.fix:
            detail = f"{c.detail}  →  {c.fix}" if c.detail else c.fix
        table.add_row(icon, c.code, c.label, detail)

    console.print(table)
    console.print()


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def run_doctor(console: Console) -> int:
    """
    Run all environment checks and render a health report.

    Parameters
    ----------
    console:
        Rich console for output.

    Returns
    -------
    int
        0 if all required checks pass, 1 otherwise.
    """
    console.print()
    console.print("[bold]EconFlow — environment health check[/bold]\n")

    system_checks   = _run_system_checks()
    package_checks  = _run_package_checks()
    external_checks = _run_external_checks()
    optional_checks = _run_optional_checks()

    _render(system_checks,   "System",            console)
    _render(package_checks,  "Core packages",     console)
    _render(external_checks, "External tools",    console)
    _render(optional_checks, "Optional packages", console)

    all_checks = system_checks + package_checks + external_checks + optional_checks
    n_fail = sum(1 for c in all_checks if c.status == "fail")
    n_warn = sum(1 for c in all_checks if c.status == "warn")
    n_pass = sum(1 for c in all_checks if c.status == "pass")

    if n_fail == 0:
        status_line = (
            f"[bold green]✔ Ready[/bold green]  "
            f"({n_pass} passed, {n_warn} warning(s))"
        )
        console.print(status_line)
    else:
        status_line = (
            f"[bold red]✘ {n_fail} required check(s) failed.[/bold red]  "
            f"({n_pass} passed, {n_warn} warning(s))"
        )
        console.print(status_line)

    console.print()
    return 0 if n_fail == 0 else 1
