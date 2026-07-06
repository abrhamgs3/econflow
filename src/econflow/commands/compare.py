"""
econflow.commands.compare — Implementation of ``econflow compare``.
"""

from __future__ import annotations

from pathlib import Path

from rich.console import Console
from rich.table import Table


def run_compare(
    *,
    baseline_dir: Path,
    replica_dir: Path,
    tolerance: float = 1e-6,
    output_path: Path | None = None,
    extensions: tuple[str, ...] = (".csv", ".tex", ".json"),
    console: Console,
) -> int:
    """
    Compare *baseline_dir* against *replica_dir* and report differences.

    Parameters
    ----------
    baseline_dir:
        Directory containing the original (authoritative) outputs.
    replica_dir:
        Directory containing the reproduced outputs.
    tolerance:
        Absolute tolerance for floating-point comparison.
    output_path:
        Optional path to write the :class:`~econflow.replication.ComparisonReport`
        as JSON.
    extensions:
        File extensions to compare.
    console:
        Rich console for output.

    Returns
    -------
    int
        0 when all files match (or only warnings); 1 on any mismatch.
    """
    from econflow.replication import compare_outputs

    console.print()
    console.rule("[bold]EconFlow compare[/bold]")
    console.print()

    if not baseline_dir.exists():
        console.print(
            f"[bold red]✘ Baseline directory not found:[/bold red] {baseline_dir}"
        )
        return 1

    if not replica_dir.exists():
        console.print(
            f"[bold red]✘ Replica directory not found:[/bold red] {replica_dir}"
        )
        return 1

    console.print(f"  Baseline: [bold]{baseline_dir}[/bold]")
    console.print(f"  Replica:  [bold]{replica_dir}[/bold]")
    console.print(f"  Tolerance: {tolerance:.0e}")
    console.print()

    # Run comparison
    report = compare_outputs(
        baseline_dir=baseline_dir,
        replica_dir=replica_dir,
        tolerance=tolerance,
        extensions=extensions,
    )

    # Print table
    _print_comparison_table(report, console)

    # Overall result
    status_fmt = {
        "pass": "[bold green]✔ PASS[/bold green]",
        "warn": "[bold yellow]⚠ WARN[/bold yellow]",
        "fail": "[bold red]✘ FAIL[/bold red]",
    }.get(report.overall_status, report.overall_status)

    summary = (
        f"{report.match_count} matched  "
        f"{report.mismatch_count} mismatched  "
        f"{report.missing_count} missing"
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
            console.print(
                f"[bold yellow]⚠ Could not save report:[/bold yellow] {exc}"
            )

    return 0 if report.overall_status in ("pass", "warn") else 1


def _print_comparison_table(report: object, console: Console) -> None:
    from econflow.replication.models import ComparisonReport

    assert isinstance(report, ComparisonReport)

    icons = {
        "match": "[green]✔[/green]",
        "mismatch": "[red]✘[/red]",
        "missing_replica": "[yellow]⚠[/yellow]",
        "missing_baseline": "[yellow]⚠[/yellow]",
        "skip": "[dim]–[/dim]",
    }
    status_fmt = {
        "match": "[green]match[/green]",
        "mismatch": "[red]mismatch[/red]",
        "missing_replica": "[yellow]missing_replica[/yellow]",
        "missing_baseline": "[yellow]missing_baseline[/yellow]",
        "skip": "[dim]skip[/dim]",
    }

    table = Table(show_header=True, header_style="bold", box=None, padding=(0, 2))
    table.add_column("File")
    table.add_column("Status", width=18)
    table.add_column("Details")

    for c in report.comparisons:
        icon = icons.get(c.status, "?")
        sfmt = status_fmt.get(c.status, c.status)
        details = c.message[:80] if c.message else ""
        table.add_row(
            f"`{c.filename}`",
            f"{icon} {sfmt}",
            details,
        )

    console.print(table)
    console.print()
