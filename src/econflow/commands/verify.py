"""
econflow.commands.verify — Implementation of ``econflow verify``.
"""

from __future__ import annotations

from pathlib import Path

from rich.console import Console


def run_verify(
    *,
    baseline_path: Path,
    current_path: Path | None,
    output_path: Path | None,
    console: Console,
) -> int:
    """
    Compare two certificates and report drift.

    When *current_path* is ``None``, the current environment is captured
    freshly and compared against *baseline_path*.

    Parameters
    ----------
    baseline_path:
        Path to the baseline :class:`~econflow.integrity.ReproducibilityCertificate`.
    current_path:
        Path to the current certificate, or ``None`` to capture live.
    output_path:
        Optional destination for the JSON :class:`~econflow.integrity.DriftReport`.
    console:
        Rich console for output.

    Returns
    -------
    int
        0 when status is ``"pass"`` or ``"warn"``; 1 when ``"fail"``.
    """
    from econflow.integrity import ReproducibilityCertificate, detect_drift

    console.print()
    console.rule("[bold]EconFlow verify[/bold]")
    console.print()

    # ---- Load baseline ---------------------------------------------------
    if not baseline_path.exists():
        console.print(
            f"[bold red]✘ Baseline certificate not found:[/bold red] {baseline_path}"
        )
        return 1

    try:
        baseline = ReproducibilityCertificate.load(baseline_path)
    except Exception as exc:
        console.print(
            f"[bold red]✘ Could not load baseline certificate:[/bold red] {exc}"
        )
        return 1

    # ---- Load or capture current ----------------------------------------
    if current_path is not None:
        if not current_path.exists():
            console.print(
                f"[bold red]✘ Current certificate not found:[/bold red] {current_path}"
            )
            return 1
        try:
            current = ReproducibilityCertificate.load(current_path)
        except Exception as exc:
            console.print(
                f"[bold red]✘ Could not load current certificate:[/bold red] {exc}"
            )
            return 1
        current_label = str(current_path)
    else:
        console.print("[dim]Capturing current environment fingerprint…[/dim]")
        current = ReproducibilityCertificate.build(
            project_name=baseline.project_name,
            data_paths=[d.path for d in baseline.data],
            config_path=baseline.config.path if baseline.config else None,
        )
        current_label = "(live environment)"

    # ---- Run drift detection --------------------------------------------
    try:
        report = detect_drift(
            baseline.to_dict(),
            current.to_dict(),
            baseline_path=str(baseline_path),
            current_path=current_label,
        )
    except Exception as exc:
        console.print(
            f"[bold red]✘ Drift detection failed:[/bold red] {exc}"
        )
        return 1

    # ---- Display --------------------------------------------------------
    status_fmt = {
        "pass": "[bold green]✔ PASS — no significant drift detected[/bold green]",
        "warn": "[bold yellow]⚠ WARN — minor drift detected[/bold yellow]",
        "fail": "[bold red]✘ FAIL — significant drift detected[/bold red]",
    }.get(report.overall_status, report.overall_status)

    console.print(f"  Baseline:  [dim]{baseline_path}[/dim]")
    console.print(f"  Current:   [dim]{current_label}[/dim]")
    console.print(f"  Status:    {status_fmt}")
    console.print(f"  Changes:   {len(report.items)}")
    console.print()

    if report.items:
        _print_drift_items(report.items, console)

    # ---- Write report ---------------------------------------------------
    if output_path is not None:
        try:
            report.save(output_path)
            console.print(f"  [bold]Drift report written to:[/bold] {output_path}")
            console.print()
        except Exception as exc:
            console.print(f"[bold yellow]⚠ Could not write drift report:[/bold yellow] {exc}")

    return 0 if report.overall_status in ("pass", "warn") else 1


def _print_drift_items(items: list, console: Console) -> None:
    from rich.table import Table

    sev_fmt = {
        "fail": "[red]fail[/red]",
        "warn": "[yellow]warn[/yellow]",
        "none": "[dim]info[/dim]",
    }

    table = Table(show_header=True, header_style="bold", box=None, padding=(0, 1))
    table.add_column("Severity", width=8)
    table.add_column("Field")
    table.add_column("Message")

    for item in items:
        table.add_row(
            sev_fmt.get(item.severity, item.severity),
            item.field,
            item.message[:80] if item.message else "",
        )

    console.print(table)
    console.print()
