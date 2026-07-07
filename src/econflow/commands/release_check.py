"""
econflow.commands.release_check — ``econflow release-check`` command implementation.

Runs the EconFlow Release Quality Gate: a structured suite of checks that must
all pass before a release can be tagged.  Any check marked as a blocker that
fails causes the command to exit with code 1.

Check catalogue
---------------
QG-01  package_build       Wheel builds from source (python -m build --wheel)
QG-02  package_import      All public sub-packages import without error
QG-03  cli_smoke           CLI entry point responds to --version and doctor
QG-04  schema_validation   ConfigValidator passes on blind_replication example
QG-05  plugin_registry     Estimator / renderer / connector / diagnostic registries
                           meet minimum population thresholds
QG-06  integration_tests   pytest tests/integration/ exits 0
QG-07  blind_replication   econflow reproduce examples/blind_replication/ succeeds
QG-08  doc_api_examples    Key import patterns shown in SDK docs work in-process
QG-09  api_consistency     Every name in __all__ for each public package imports

Severity
--------
BLOCKER  Command exits 1 if any BLOCKER check fails.
WARN     Only logged; does not affect exit code.

Options
-------
--quick / --no-quick   Skip QG-01 (build), QG-06 (integration tests), and
                       QG-07 (blind replication) for a fast pre-flight check.
--output PATH          Write the full report to a Markdown file.
--json PATH            Write a machine-readable JSON report.
--checks LIST          Comma-separated list of check IDs to run (default: all).
"""

from __future__ import annotations

import importlib
import json
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Literal

from rich.console import Console
from rich.table import Table

from econflow import __version__
from econflow.commands._shared import STATUS_ICONS

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

Severity = Literal["blocker", "warn"]
Status = Literal["pass", "fail", "warn", "skip"]


@dataclass
class CheckResult:
    """Result of one quality gate check."""

    id: str                   # QG-01 … QG-09
    name: str                 # short slug
    label: str                # human-readable title
    status: Status
    severity: Severity
    detail: str               # one-line outcome
    fix: str = ""             # actionable fix hint on failure
    duration_ms: float = 0.0
    sub_results: list[dict] = field(default_factory=list)

    @property
    def is_blocker(self) -> bool:
        return self.status == "fail" and self.severity == "blocker"


@dataclass
class ReleaseReport:
    """Aggregated result of the full quality gate run."""

    version: str
    timestamp: str
    checks: list[CheckResult]
    elapsed_s: float = 0.0

    @property
    def passed(self) -> list[CheckResult]:
        return [c for c in self.checks if c.status == "pass"]

    @property
    def warned(self) -> list[CheckResult]:
        return [c for c in self.checks if c.status == "warn"]

    @property
    def failed(self) -> list[CheckResult]:
        return [c for c in self.checks if c.status == "fail"]

    @property
    def skipped(self) -> list[CheckResult]:
        return [c for c in self.checks if c.status == "skip"]

    @property
    def blockers(self) -> list[CheckResult]:
        return [c for c in self.checks if c.is_blocker]

    @property
    def release_blocked(self) -> bool:
        return len(self.blockers) > 0


# ---------------------------------------------------------------------------
# Individual check implementations
# ---------------------------------------------------------------------------

def _time_check(fn: Callable[[], CheckResult]) -> CheckResult:
    t0 = time.perf_counter()
    result = fn()
    result.duration_ms = (time.perf_counter() - t0) * 1000
    return result


def check_package_build() -> CheckResult:
    """QG-01: Build the wheel in an isolated temp directory."""
    cid = "QG-01"
    name = "package_build"
    label = "Package build (wheel)"

    try:
        import build  # noqa: F401 — check build is available
    except ImportError:
        return CheckResult(
            id=cid, name=name, label=label,
            status="warn", severity="warn",
            detail="python-build not installed; skipping wheel build",
            fix="pip install build",
        )

    with tempfile.TemporaryDirectory() as tmpdir:
        result = subprocess.run(
            [sys.executable, "-m", "build", "--wheel", "--no-isolation",
             "--outdir", tmpdir],
            capture_output=True,
            text=True,
            cwd=_repo_root(),
        )
        if result.returncode != 0:
            return CheckResult(
                id=cid, name=name, label=label,
                status="fail", severity="blocker",
                detail="python -m build --wheel exited non-zero",
                fix=f"stderr: {result.stderr[-400:].strip()}",
            )
        wheels = list(Path(tmpdir).glob("*.whl"))
        if not wheels:
            return CheckResult(
                id=cid, name=name, label=label,
                status="fail", severity="blocker",
                detail="Build exited 0 but no .whl file was produced",
            )
        whl = wheels[0].name
        return CheckResult(
            id=cid, name=name, label=label,
            status="pass", severity="blocker",
            detail=f"Built {whl}",
        )


def check_package_import() -> CheckResult:
    """QG-02: Import all public sub-packages in-process."""
    cid = "QG-02"
    name = "package_import"
    label = "Package imports"

    packages = [
        "econflow",
        "econflow.estimation",
        "econflow.diagnostics",
        "econflow.outputs",
        "econflow.ingestion",
        "econflow.integrity",
        "econflow.replication",
        "econflow.config",
        "econflow.commands",
    ]

    sub = []
    failures = []
    for pkg in packages:
        try:
            importlib.import_module(pkg)
            sub.append({"package": pkg, "status": "pass"})
        except Exception as exc:
            sub.append({"package": pkg, "status": "fail", "error": str(exc)})
            failures.append(f"{pkg}: {exc}")

    if failures:
        return CheckResult(
            id=cid, name=name, label=label,
            status="fail", severity="blocker",
            detail=f"{len(failures)} import(s) failed",
            fix="; ".join(failures[:3]),
            sub_results=sub,
        )

    return CheckResult(
        id=cid, name=name, label=label,
        status="pass", severity="blocker",
        detail=f"All {len(packages)} packages import cleanly",
        sub_results=sub,
    )


def check_cli_smoke() -> CheckResult:
    """QG-03: Run econflow --version and econflow doctor."""
    cid = "QG-03"
    name = "cli_smoke"
    label = "CLI smoke test"

    sub = []

    # --version
    r_ver = subprocess.run(
        [sys.executable, "-m", "econflow.cli", "--version"],
        capture_output=True, text=True, cwd=_repo_root(),
    )
    # also try the entry point directly
    if r_ver.returncode != 0:
        r_ver = subprocess.run(
            ["econflow", "--version"],
            capture_output=True, text=True, cwd=_repo_root(),
        )

    ver_ok = r_ver.returncode == 0 and __version__ in r_ver.stdout
    sub.append({
        "cmd": "econflow --version",
        "status": "pass" if ver_ok else "fail",
        "output": r_ver.stdout.strip(),
    })

    # doctor
    r_doc = subprocess.run(
        ["econflow", "doctor"],
        capture_output=True, text=True, cwd=_repo_root(),
    )
    doc_ok = r_doc.returncode == 0
    sub.append({
        "cmd": "econflow doctor",
        "status": "pass" if doc_ok else "fail",
        "returncode": r_doc.returncode,
    })

    if not ver_ok or not doc_ok:
        failures = []
        if not ver_ok:
            failures.append("--version failed or missing version string")
        if not doc_ok:
            failures.append(f"doctor exited {r_doc.returncode}")
        return CheckResult(
            id=cid, name=name, label=label,
            status="fail", severity="blocker",
            detail="; ".join(failures),
            fix="Run 'econflow doctor' manually to diagnose",
            sub_results=sub,
        )

    return CheckResult(
        id=cid, name=name, label=label,
        status="pass", severity="blocker",
        detail="--version and doctor both pass",
        sub_results=sub,
    )


def check_schema_validation() -> CheckResult:
    """QG-04: ConfigValidator on the blind_replication example."""
    cid = "QG-04"
    name = "schema_validation"
    label = "Config schema validation"

    config_dir = _repo_root() / "examples" / "blind_replication" / "config"
    config_path = config_dir / "config.yaml"
    models_path = config_dir / "models.yaml"
    outputs_path = config_dir / "outputs.yaml"

    missing = [p for p in (config_path, models_path, outputs_path) if not p.exists()]
    if missing:
        return CheckResult(
            id=cid, name=name, label=label,
            status="fail", severity="blocker",
            detail=f"Example config files missing: {[str(p) for p in missing]}",
            fix="Restore examples/blind_replication/config/",
        )

    try:
        from econflow.config.validator import ConfigValidator

        validator = ConfigValidator()
        result = validator.validate(
            config_path=config_path,
            models_path=models_path,
            outputs_path=outputs_path,
            check_data=False,
        )
        errors = [i for i in result.issues if i.severity == "error"]
        if errors:
            return CheckResult(
                id=cid, name=name, label=label,
                status="fail", severity="blocker",
                detail=f"{len(errors)} validation error(s) on blind_replication config",
                fix=errors[0].message if errors else "",
                sub_results=[{"message": i.message, "severity": i.severity} for i in result.issues],
            )
        warnings = [i for i in result.issues if i.severity == "warning"]
        return CheckResult(
            id=cid, name=name, label=label,
            status="pass" if not warnings else "warn",
            severity="blocker",
            detail=(
                f"Schema valid — {len(warnings)} warning(s)"
                if warnings else "Schema valid — no issues"
            ),
            sub_results=[{"message": i.message, "severity": i.severity} for i in result.issues],
        )
    except Exception as exc:
        return CheckResult(
            id=cid, name=name, label=label,
            status="fail", severity="blocker",
            detail=f"ConfigValidator raised: {exc}",
        )


def check_plugin_registry() -> CheckResult:
    """QG-05: Verify all registries meet minimum population thresholds."""
    cid = "QG-05"
    name = "plugin_registry"
    label = "Plugin registry integrity"

    sub = []
    failures = []

    # Thresholds: (registry name, fetch fn, min count, import error hint)
    checks: list[tuple[str, Callable, int]] = [
        (
            "estimators",
            lambda: __import__(
                "econflow.estimation", fromlist=["list_estimators"]
            ).list_estimators(),
            6,
        ),
        (
            "renderers",
            lambda: __import__(
                "econflow.outputs.registry", fromlist=["list_renderers"]
            ).list_renderers(),
            5,
        ),
        (
            "connectors",
            lambda: __import__(
                "econflow.ingestion", fromlist=["list_connectors"]
            ).list_connectors(),
            4,
        ),
        (
            "diagnostics",
            lambda: __import__(
                "econflow.diagnostics", fromlist=["list_diagnostics"]
            ).list_diagnostics(),
            4,
        ),
        (
            "integrity_checks",
            lambda: __import__("econflow.integrity", fromlist=["list_checks"]).list_checks(),
            2,
        ),
    ]

    for reg_name, fetch, min_count in checks:
        try:
            items = fetch()
            count = len(items)
            ok = count >= min_count
            sub.append({
                "registry": reg_name,
                "count": count,
                "min_required": min_count,
                "status": "pass" if ok else "fail",
            })
            if not ok:
                failures.append(f"{reg_name}: {count} < {min_count}")
        except Exception as exc:
            sub.append({"registry": reg_name, "status": "fail", "error": str(exc)})
            failures.append(f"{reg_name}: {exc}")

    if failures:
        return CheckResult(
            id=cid, name=name, label=label,
            status="fail", severity="blocker",
            detail=f"Registry population too low: {'; '.join(failures)}",
            fix="Check that all estimators/renderers/connectors are registered",
            sub_results=sub,
        )

    return CheckResult(
        id=cid, name=name, label=label,
        status="pass", severity="blocker",
        detail="All registries meet minimum thresholds",
        sub_results=sub,
    )


def check_integration_tests() -> CheckResult:
    """QG-06: Run pytest tests/integration/ in a subprocess."""
    cid = "QG-06"
    name = "integration_tests"
    label = "Integration tests"

    tests_dir = _repo_root() / "tests" / "integration"
    if not tests_dir.exists():
        return CheckResult(
            id=cid, name=name, label=label,
            status="warn", severity="warn",
            detail="tests/integration/ not found",
            fix="Create integration test suite",
        )

    result = subprocess.run(
        [sys.executable, "-m", "pytest", str(tests_dir), "-q", "--tb=short",
         "--timeout=120", "-x"],
        capture_output=True,
        text=True,
        cwd=_repo_root(),
    )

    # Parse summary line
    lines = result.stdout.strip().splitlines()
    summary = lines[-1] if lines else "(no output)"

    if result.returncode != 0:
        # Extract failure count from pytest output
        tail = "\n".join(lines[-20:])
        return CheckResult(
            id=cid, name=name, label=label,
            status="fail", severity="blocker",
            detail=f"Integration tests FAILED — {summary}",
            fix=f"pytest tests/integration/ -v --tb=long\n{tail}",
        )

    return CheckResult(
        id=cid, name=name, label=label,
        status="pass", severity="blocker",
        detail=f"Integration tests passed — {summary}",
    )


def check_blind_replication() -> CheckResult:
    """QG-07: Run econflow reproduce examples/blind_replication/."""
    cid = "QG-07"
    name = "blind_replication"
    label = "Blind replication"

    repro_dir = _repo_root() / "examples" / "blind_replication"
    if not repro_dir.exists():
        return CheckResult(
            id=cid, name=name, label=label,
            status="warn", severity="warn",
            detail="examples/blind_replication/ not found",
            fix="Restore blind_replication example directory",
        )

    with tempfile.TemporaryDirectory() as tmpdir:
        result = subprocess.run(
            ["econflow", "reproduce", str(repro_dir),
             "--output-dir", tmpdir,
             "--no-compare"],
            capture_output=True,
            text=True,
            cwd=_repo_root(),
            timeout=300,
        )

        if result.returncode != 0:
            tail = (result.stdout + result.stderr)[-600:].strip()
            return CheckResult(
                id=cid, name=name, label=label,
                status="fail", severity="blocker",
                detail="econflow reproduce examples/blind_replication/ failed",
                fix=f"stderr tail:\n{tail}",
            )

    return CheckResult(
        id=cid, name=name, label=label,
        status="pass", severity="blocker",
        detail="Blind replication reproduced successfully",
    )


def check_doc_api_examples() -> CheckResult:
    """QG-08: Verify key import patterns from SDK / API docs work in-process."""
    cid = "QG-08"
    name = "doc_api_examples"
    label = "Documentation API examples"

    # Each tuple: (description, callable that raises on failure)
    patterns: list[tuple[str, Callable]] = [
        # estimation public API (from PLUGIN_SDK.md §4, API_STABILITY.md)
        (
            "from econflow.estimation import BaseEstimator, list_estimators, get_estimator",
            lambda: (
                __import__(
                    "econflow.estimation",
                    fromlist=["BaseEstimator", "list_estimators", "get_estimator"],
                )
            ),
        ),
        (
            "from econflow.estimation import EstimationResult, register_estimator",
            lambda: (
                __import__(
                    "econflow.estimation",
                    fromlist=["EstimationResult", "register_estimator"],
                )
            ),
        ),
        # outputs public API (from PLUGIN_SDK.md §6, §7)
        (
            "from econflow.outputs import BaseRenderer, FigureBuilder, ReportTable, ReportFigure",
            lambda: (
                __import__("econflow.outputs", fromlist=["BaseRenderer", "FigureBuilder",
                                                          "ReportTable", "ReportFigure"])
            ),
        ),
        (
            "from econflow.outputs import get_renderer, list_renderers, register_renderer",
            lambda: (
                __import__("econflow.outputs", fromlist=["get_renderer", "list_renderers",
                                                          "register_renderer"])
            ),
        ),
        # ingestion public API (from PLUGIN_SDK.md §3)
        (
            "from econflow.ingestion import AbstractConnector, get_connector, list_connectors",
            lambda: (
                __import__("econflow.ingestion", fromlist=["AbstractConnector", "get_connector",
                                                            "list_connectors"])
            ),
        ),
        # diagnostics public API (from PLUGIN_SDK.md §5)
        (
            "from econflow.diagnostics import BaseDiagnostic, list_diagnostics, get_diagnostic",
            lambda: (
                __import__("econflow.diagnostics", fromlist=["BaseDiagnostic", "list_diagnostics",
                                                              "get_diagnostic"])
            ),
        ),
        # integrity public API (from PLUGIN_SDK.md §8)
        (
            "from econflow.integrity import BaseIntegrityCheck, list_checks",
            lambda: (
                __import__("econflow.integrity", fromlist=["BaseIntegrityCheck", "list_checks"])
            ),
        ),
        # config public API
        (
            "from econflow.config.validator import ConfigValidator",
            lambda: __import__("econflow.config.validator", fromlist=["ConfigValidator"]),
        ),
    ]

    sub = []
    failures = []
    for desc, fn in patterns:
        try:
            fn()
            sub.append({"import": desc, "status": "pass"})
        except Exception as exc:
            sub.append({"import": desc, "status": "fail", "error": str(exc)})
            failures.append(f"{desc}: {exc}")

    if failures:
        return CheckResult(
            id=cid, name=name, label=label,
            status="fail", severity="blocker",
            detail=f"{len(failures)} doc API example(s) failed",
            fix=failures[0],
            sub_results=sub,
        )

    return CheckResult(
        id=cid, name=name, label=label,
        status="pass", severity="blocker",
        detail=f"All {len(patterns)} documented import patterns work",
        sub_results=sub,
    )


def check_api_consistency() -> CheckResult:
    """QG-09: Verify every name in each public __all__ is importable."""
    cid = "QG-09"
    name = "api_consistency"
    label = "API surface consistency (__all__)"

    packages = [
        "econflow",
        "econflow.estimation",
        "econflow.diagnostics",
        "econflow.outputs",
        "econflow.ingestion",
        "econflow.integrity",
    ]

    sub = []
    phantom: list[str] = []   # in __all__ but not importable
    warnings: list[str] = []  # package has no __all__

    for pkg_name in packages:
        try:
            mod = importlib.import_module(pkg_name)
        except Exception as exc:
            sub.append({"package": pkg_name, "status": "fail", "error": str(exc)})
            phantom.append(f"{pkg_name}: import failed — {exc}")
            continue

        all_names = getattr(mod, "__all__", None)
        if all_names is None:
            sub.append({"package": pkg_name, "status": "warn", "note": "no __all__"})
            warnings.append(f"{pkg_name}: no __all__ defined")
            continue

        pkg_failures = []
        for name_str in all_names:
            if not hasattr(mod, name_str):
                pkg_failures.append(name_str)

        if pkg_failures:
            sub.append({
                "package": pkg_name,
                "status": "fail",
                "phantom_names": pkg_failures,
            })
            phantom.append(f"{pkg_name}: {pkg_failures}")
        else:
            sub.append({
                "package": pkg_name,
                "status": "pass",
                "exported": len(all_names),
            })

    if phantom:
        return CheckResult(
            id=cid, name=name, label=label,
            status="fail", severity="blocker",
            detail=f"Phantom exports found in {len(phantom)} package(s)",
            fix=f"Remove or implement: {phantom[0]}",
            sub_results=sub,
        )

    status: Status = "warn" if warnings else "pass"
    return CheckResult(
        id=cid, name=name, label=label,
        status=status, severity="blocker",
        detail=(
            "All __all__ entries importable"
            + (f" ({len(warnings)} package(s) missing __all__)" if warnings else "")
        ),
        sub_results=sub,
    )


# ---------------------------------------------------------------------------
# Registry of all checks
# ---------------------------------------------------------------------------

ALL_CHECKS: list[tuple[str, Callable[[], CheckResult]]] = [
    ("QG-01", check_package_build),
    ("QG-02", check_package_import),
    ("QG-03", check_cli_smoke),
    ("QG-04", check_schema_validation),
    ("QG-05", check_plugin_registry),
    ("QG-06", check_integration_tests),
    ("QG-07", check_blind_replication),
    ("QG-08", check_doc_api_examples),
    ("QG-09", check_api_consistency),
]

# Checks skipped in --quick mode
SLOW_CHECKS = {"QG-01", "QG-06", "QG-07"}


# ---------------------------------------------------------------------------
# Main runner
# ---------------------------------------------------------------------------

def run_release_check(
    *,
    quick: bool = False,
    checks_filter: set[str] | None = None,
    output_md: Path | None = None,
    output_json: Path | None = None,
    console: Console | None = None,
) -> int:
    """
    Execute the EconFlow Release Quality Gate.

    Parameters
    ----------
    quick:
        Skip QG-01, QG-06, QG-07 (build, integration tests, blind replication).
    checks_filter:
        If set, run only the listed check IDs.
    output_md:
        Write a Markdown report to this path when specified.
    output_json:
        Write a JSON report to this path when specified.
    console:
        Rich console for output.

    Returns
    -------
    int
        0 if no blockers, 1 if one or more blockers.
    """
    import datetime

    if console is None:
        console = Console()

    OK   = STATUS_ICONS["pass"]
    WARN = STATUS_ICONS["warn"]
    FAIL = STATUS_ICONS["fail"]
    SKIP = STATUS_ICONS["skip"]
    INFO = STATUS_ICONS["info"]

    console.print()
    console.rule(f"[bold]EconFlow {__version__} — Release Quality Gate[/bold]")
    console.print()

    if quick:
        console.print(
            f"  {INFO} [dim]--quick mode: QG-01 / QG-06 / QG-07 skipped[/dim]"
        )
        console.print()

    t_start = time.perf_counter()
    results: list[CheckResult] = []

    for check_id, check_fn in ALL_CHECKS:
        skip = False
        if quick and check_id in SLOW_CHECKS:
            skip = True
        if checks_filter and check_id not in checks_filter:
            skip = True

        if skip:
            # Synthesise a skip result so the report is complete
            check_name, check_label = _check_meta(check_id)
            r = CheckResult(
                id=check_id,
                name=check_name,
                label=check_label,
                status="skip",
                severity="blocker",
                detail="Skipped" + (" (--quick)" if quick and check_id in SLOW_CHECKS else ""),
            )
        else:
            icon_run = "[dim]…[/dim]"
            console.print(f"  {icon_run} [{check_id}] {_check_meta(check_id)[1]} …", end="\r")
            # Look up the current module-level binding so unit-test patches are respected
            import sys as _sys
            _live_fn = getattr(_sys.modules[__name__], check_fn.__name__, check_fn)
            r = _time_check(_live_fn)

        results.append(r)

        icon = {
            "pass": OK,
            "fail": FAIL,
            "warn": WARN,
            "skip": SKIP,
        }[r.status]

        duration_str = f"[dim]{r.duration_ms:.0f} ms[/dim]" if r.duration_ms else ""
        blocker_tag = " [bold red][BLOCKER][/bold red]" if r.is_blocker else ""
        console.print(
            f"  {icon} [{check_id}] {r.label}  "
            f"— {r.detail}{blocker_tag}  {duration_str}"
        )
        if r.fix and r.status == "fail":
            console.print(f"      [dim]Fix: {r.fix[:200]}[/dim]")

    elapsed = time.perf_counter() - t_start

    # Build report object
    timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
    report = ReleaseReport(
        version=__version__,
        timestamp=timestamp,
        checks=results,
        elapsed_s=elapsed,
    )

    # Summary table
    console.print()
    console.rule()

    tbl = Table(show_header=True, header_style="bold", box=None, padding=(0, 1))
    tbl.add_column("Status", width=8)
    tbl.add_column("Count", justify="right", width=6)
    tbl.add_row(OK + " Passed",  str(len(report.passed)))
    tbl.add_row(WARN + " Warned", str(len(report.warned)))
    tbl.add_row(FAIL + " Failed", str(len(report.failed)))
    tbl.add_row(SKIP + " Skipped", str(len(report.skipped)))
    console.print(tbl)
    console.print()

    if report.blockers:
        console.print(
            f"[bold red]✘ RELEASE BLOCKED[/bold red] — "
            f"{len(report.blockers)} blocker(s):"
        )
        for c in report.blockers:
            console.print(f"  [red]· [{c.id}] {c.label}[/red] — {c.detail}")
    else:
        console.print(
            f"[bold green]✔ RELEASE APPROVED[/bold green]  "
            f"EconFlow {__version__} — all checks passed"
            + (" (quick mode)" if quick else "")
        )

    console.print(f"\n  Completed in {elapsed:.1f} s")
    console.print()

    # Write optional outputs
    if output_md:
        _write_md_report(report, output_md)
        console.print(f"  {OK} Markdown report written to {output_md}")

    if output_json:
        _write_json_report(report, output_json)
        console.print(f"  {OK} JSON report written to {output_json}")

    return 1 if report.release_blocked else 0


# ---------------------------------------------------------------------------
# Report writers
# ---------------------------------------------------------------------------

def _write_md_report(report: ReleaseReport, path: Path) -> None:
    lines = [
        f"# EconFlow {report.version} — Release Quality Gate Report",
        "",
        f"**Date:** {report.timestamp}",
        f"**Version:** {report.version}",
        f"**Outcome:** {'❌ RELEASE BLOCKED' if report.release_blocked else '✅ RELEASE APPROVED'}",
        f"**Duration:** {report.elapsed_s:.1f} s",
        "",
        "## Check Results",
        "",
        "| ID | Check | Status | Duration | Detail |",
        "|---|---|---|---|---|",
    ]
    for c in report.checks:
        status_emoji = {"pass": "✅", "fail": "❌", "warn": "⚠️", "skip": "–"}[c.status]
        dur = f"{c.duration_ms:.0f} ms" if c.duration_ms else "–"
        detail = c.detail.replace("|", "\\|")
        row = f"| {c.id} | {c.label} | {status_emoji} {c.status.upper()} | {dur} | {detail} |"
        lines.append(row)

    if report.blockers:
        lines += [
            "",
            "## Blockers",
            "",
        ]
        for c in report.blockers:
            lines += [
                f"### [{c.id}] {c.label}",
                "",
                f"**Detail:** {c.detail}",
                "",
                f"**Fix:** {c.fix}" if c.fix else "",
                "",
            ]

    lines += [
        "",
        "## Summary",
        "",
        f"- Passed: {len(report.passed)}",
        f"- Warned: {len(report.warned)}",
        f"- Failed: {len(report.failed)}",
        f"- Skipped: {len(report.skipped)}",
    ]

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_json_report(report: ReleaseReport, path: Path) -> None:
    data = {
        "version": report.version,
        "timestamp": report.timestamp,
        "elapsed_s": report.elapsed_s,
        "release_blocked": report.release_blocked,
        "summary": {
            "passed": len(report.passed),
            "warned": len(report.warned),
            "failed": len(report.failed),
            "skipped": len(report.skipped),
            "blockers": len(report.blockers),
        },
        "checks": [asdict(c) for c in report.checks],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _repo_root() -> Path:
    """Return the repository root (src/ parent)."""
    import econflow
    return Path(econflow.__file__).parent.parent.parent


def _check_meta(check_id: str) -> tuple[str, str]:
    """Return (name, label) for a check ID from the registered list."""
    for cid, fn in ALL_CHECKS:
        if cid == check_id:
            # infer label from docstring first line
            doc = (fn.__doc__ or "").strip().split("\n")[0]
            label = doc.split(":", 1)[-1].strip() if ":" in doc else fn.__name__
            return fn.__name__.replace("check_", ""), label
    return check_id.lower(), check_id
