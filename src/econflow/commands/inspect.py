"""
econflow.commands.inspect — Implementation of ``econflow inspect``.
"""

from __future__ import annotations

from pathlib import Path

from rich.console import Console
from rich.table import Table


def run_inspect(
    *,
    project_dir: Path,
    output_path: Path | None = None,
    strict: bool = False,
    console: Console,
) -> int:
    """
    Run pre-flight checks on *project_dir* and report results.

    Parameters
    ----------
    project_dir:
        Root of the EconFlow project to inspect.
    output_path:
        Optional path to write the :class:`~econflow.replication.InspectionReport`
        as JSON.
    strict:
        If ``True``, treat warnings as failures (exit code 1).
    console:
        Rich console for output.

    Returns
    -------
    int
        0 when all checks pass (or only warnings and *strict* is ``False``);
        1 on any failure.
    """
    from econflow.replication import InspectionReport, inspect_project

    console.print()
    console.rule("[bold]EconFlow inspect[/bold]")
    console.print()
    console.print(f"  Project: [bold]{project_dir}[/bold]")
    console.print()

    if not project_dir.exists():
        console.print(
            f"[bold red]✘ Project directory not found:[/bold red] {project_dir}"
        )
        return 1

    # Run checks
    report: InspectionReport = inspect_project(project_dir)

    # Print results table
    _print_inspection_table(report, console)

    # Overall result
    status_fmt = {
        "pass": "[bold green]✔ PASS[/bold green]",
        "warn": "[bold yellow]⚠ WARN[/bold yellow]",
        "fail": "[bold red]✘ FAIL[/bold red]",
    }.get(report.overall_status, report.overall_status)

    summary = (
        f"{report.pass_count} passed  "
        f"{report.warn_count} warned  "
        f"{report.fail_count} failed"
    )
    console.print(f"  Status: {status_fmt}  ({summary})")
    console.print()

    # Save JSON if requested
    if output_path is not None:
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(report.to_json(), encoding="utf-8")
            console.print(f"  [dim]Report saved to: {output_path}[/dim]")
            console.print()
        except Exception as exc:
            console.print(f"[bold yellow]⚠ Could not save report:[/bold yellow] {exc}")

    fail_condition = report.overall_status == "fail"
    if strict and report.overall_status == "warn":
        fail_condition = True

    return 1 if fail_condition else 0


def _print_inspection_table(report: object, console: Console) -> None:
    from econflow.replication.models import InspectionReport

    assert isinstance(report, InspectionReport)

    status_fmt = {
        "pass": "[green]pass[/green]",
        "warn": "[yellow]warn[/yellow]",
        "fail": "[red]fail[/red]",
        "skip": "[dim]skip[/dim]",
    }
    icon = {
        "pass": "✔",
        "warn": "⚠",
        "fail": "✘",
        "skip": "–",
    }

    table = Table(show_header=True, header_style="bold", box=None, padding=(0, 2))
    table.add_column("Check")
    table.add_column("Status", width=8)
    table.add_column("Detail")

    for check in report.checks:
        detail = check.message
        if check.detail:
            detail = f"{detail}  [dim]{check.detail}[/dim]"
        table.add_row(
            check.name,
            f"{icon.get(check.status, '?')} {status_fmt.get(check.status, check.status)}",
            detail,
        )

    console.print(table)
    console.print()
