"""
econflow.commands.reproduce — Implementation of ``econflow reproduce``.
"""

from __future__ import annotations

from pathlib import Path

from rich.console import Console


def run_reproduce(
    *,
    project_dir: Path,
    output_dir: Path | None = None,
    skip_inspect: bool = False,
    compare: bool = True,
    tolerance: float = 1e-6,
    timeout: int = 600,
    report_dir: Path | None = None,
    console: Console,
) -> int:
    """
    Reproduce the analysis pipeline of *project_dir* in isolation.

    Workflow
    --------
    1. Inspect the project directory (unless *skip_inspect* is set).
    2. Build an execution plan.
    3. Execute each step in a subprocess.
    4. If ``original_outputs/`` exists and *compare* is ``True``,
       compare produced outputs against it.
    5. Write a :class:`~econflow.replication.ReproducibilityReport`.

    Parameters
    ----------
    project_dir:
        Root of the EconFlow project to reproduce.
    output_dir:
        Destination for reproduced outputs.  Defaults to
        ``<project_dir>/replication_outputs/``.
    skip_inspect:
        Skip pre-flight checks and proceed directly to execution.
    compare:
        Compare reproduced outputs against ``original_outputs/`` if it
        exists.
    tolerance:
        Absolute tolerance for numeric comparison.
    timeout:
        Per-step subprocess timeout in seconds.
    report_dir:
        Where to write the reproducibility report.  Defaults to
        ``<output_dir>/``.
    console:
        Rich console for output.

    Returns
    -------
    int
        0 on success; 1 on any failure.
    """
    from econflow.replication import (
        ReproducibilityReport,
        build_plan,
        compare_outputs,
        execute_plan,
        inspect_project,
    )

    console.print()
    console.rule("[bold]EconFlow reproduce[/bold]")
    console.print()
    console.print(f"  Project: [bold]{project_dir}[/bold]")

    if not project_dir.exists():
        console.print(
            f"[bold red]✘ Project directory not found:[/bold red] {project_dir}"
        )
        return 1

    # Default output directory
    if output_dir is None:
        output_dir = project_dir / "replication_outputs"

    console.print(f"  Output:  [bold]{output_dir}[/bold]")
    console.print()

    full_report = ReproducibilityReport()

    # ---- [1/4] Inspect --------------------------------------------------
    if not skip_inspect:
        console.print("  [bold][1/4][/bold] Inspecting project …")
        inspection = inspect_project(project_dir)
        full_report.inspection = inspection

        _print_mini_inspection(inspection, console)

        if inspection.overall_status == "fail":
            console.print(
                "[bold red]✘ Inspection failed. Fix errors before reproducing.[/bold red]"
            )
            console.print()
            _write_report(full_report, report_dir or output_dir, console)
            return 1
    else:
        console.print("  [dim][1/4] Inspection skipped (--skip-inspect)[/dim]")

    # ---- [2/4] Plan ------------------------------------------------------
    console.print("  [bold][2/4][/bold] Building execution plan …")
    plan = build_plan(project_dir=project_dir, output_dir=output_dir)
    console.print(f"         {len(plan.steps)} step(s) planned")
    console.print()

    # ---- [3/4] Execute --------------------------------------------------
    console.print("  [bold][3/4][/bold] Executing pipeline …")
    # Clean the replica tables directory before each run so stale artifacts
    # from previous runs do not appear as spurious "missing_baseline" warnings.
    _replica_tables_pre = project_dir / "outputs" / "tables"
    if _replica_tables_pre.exists():
        import shutil as _shutil
        try:
            _shutil.rmtree(_replica_tables_pre)
        except OSError:
            pass  # non-fatal: leave stale files; comparison will warn
    # The pipeline writes to its own configured outputs/ directory (outputs.yaml base_dir).
    # We pass project_dir as the output scan root so the executor finds what was produced.
    result = execute_plan(plan, output_dir=project_dir, timeout_seconds=timeout)
    full_report.execution = result

    _print_step_results(result, console)

    if result.status == "failed":
        console.print(
            "[bold red]✘ Replication failed. See step output above for details.[/bold red]"
        )
        console.print()
        _write_report(full_report, report_dir or (project_dir / 'outputs'), console)
        return 1

    # ---- [4/4] Compare --------------------------------------------------
    # Compare original_outputs/tables/ against outputs/tables/ so relative
    # filenames align (both dirs have comparison_table.csv at root level).
    baseline_root = project_dir / "original_outputs"
    _tables_sub = baseline_root / "tables"
    baseline_dir = _tables_sub if _tables_sub.exists() else baseline_root
    replica_tables = project_dir / "outputs" / "tables"
    if not replica_tables.exists():
        replica_tables = project_dir / "outputs"

    if compare and baseline_root.exists():
        console.print("  [bold][4/4][/bold] Comparing outputs …")

        comparison = compare_outputs(
            baseline_dir=baseline_dir,
            replica_dir=replica_tables,
            tolerance=tolerance,
            baseline_only=True,  # ignore extra intermediate files in outputs/
        )
        full_report.comparison = comparison

        _print_comparison_results(comparison, console)
    elif compare and not baseline_root.exists():
        console.print(
            "  [dim][4/4] No original_outputs/ directory — skipping comparison[/dim]"
        )
        console.print()
    else:
        console.print("  [dim][4/4] Comparison skipped (--no-compare)[/dim]")
        console.print()

    # ---- Write report ---------------------------------------------------
    _write_report(full_report, report_dir or (project_dir / "outputs"), console)

    # ---- Final status ---------------------------------------------------
    overall = full_report.overall_status
    status_fmt = {
        "pass": "[bold green]✔ PASS — Replication successful[/bold green]",
        "warn": "[bold yellow]⚠ WARN — Replication completed with warnings[/bold yellow]",
        "fail": "[bold red]✘ FAIL — Replication failed[/bold red]",
    }.get(overall, overall)

    console.print(f"  {status_fmt}")
    console.print(f"  Elapsed: {result.elapsed_seconds:.1f} s")
    actual_out = project_dir / "outputs"
    console.print(f"  Outputs: {len(result.outputs)} file(s) in {actual_out}")
    console.print()

    return 0 if overall in ("pass", "warn") else 1


# ---------------------------------------------------------------------------
# Console helpers
# ---------------------------------------------------------------------------

def _print_mini_inspection(report: object, console: Console) -> None:
    from econflow.replication.models import InspectionReport

    assert isinstance(report, InspectionReport)
    icons = {"pass": "[green]✔[/green]", "warn": "[yellow]⚠[/yellow]",
             "fail": "[red]✘[/red]", "skip": "[dim]–[/dim]"}

    for check in report.checks:
        icon = icons.get(check.status, "?")
        console.print(f"         {icon} {check.name}: {check.message}")
    console.print()


def _print_step_results(result: object, console: Console) -> None:
    from econflow.replication.models import ReplicationResult

    assert isinstance(result, ReplicationResult)
    icons = {
        "success": "[green]✔[/green]",
        "failed": "[red]✘[/red]",
        "skipped": "[dim]–[/dim]",
    }

    for sr in result.step_results:
        icon = icons.get(sr.status, "?")
        elapsed = f"{sr.elapsed_seconds:.1f}s"
        console.print(
            f"         {icon} {sr.description} ({elapsed})"
        )
        if sr.status == "failed" and sr.stderr:
            for line in sr.stderr.splitlines()[-5:]:
                console.print(f"           [dim]{line}[/dim]")

    console.print()


def _print_comparison_results(report: object, console: Console) -> None:
    from econflow.replication.models import ComparisonReport

    assert isinstance(report, ComparisonReport)
    icons = {
        "match": "[green]✔[/green]",
        "mismatch": "[red]✘[/red]",
        "missing_replica": "[yellow]⚠[/yellow]",
        "missing_baseline": "[yellow]⚠[/yellow]",
        "skip": "[dim]–[/dim]",
    }

    for c in report.comparisons:
        icon = icons.get(c.status, "?")
        console.print(f"         {icon} {c.filename}: {c.message}")
    console.print()


def _write_report(report: object, report_dir: Path, console: Console) -> None:
    from econflow.replication.reporter import ReproducibilityReport

    assert isinstance(report, ReproducibilityReport)
    try:
        md_path, json_path = report.save(report_dir)
        console.print(
            f"  [dim]Report saved: {md_path.name}  {json_path.name}[/dim]"
        )
        console.print()
    except Exception as exc:
        console.print(f"  [dim yellow]Could not save report: {exc}[/dim yellow]")
        console.print()
