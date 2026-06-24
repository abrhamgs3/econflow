"""
econflow.cli.commands.reproduce — ``aprp reproduce`` command.

Displays or re-runs a previous pipeline run from its provenance snapshot.
Each completed run writes a ``provenance/<run_id>.json`` file under the
project output directory; this command reads those snapshots.

Examples
--------
    # List provenance snapshots for a project
    $ aprp reproduce --list --project ai_productivity

    # Show the full snapshot for a specific run
    $ aprp reproduce 3f2a1b0c-dead-beef-cafe-1234567890ab
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

app = typer.Typer(help="Display or re-run a previous pipeline run from its provenance snapshot.")
console = Console()


@app.callback(invoke_without_command=True)
def reproduce(
    run_id: Annotated[
        str | None,
        typer.Argument(help="Run ID to display.  Omit to use --list."),
    ] = None,
    list_runs: Annotated[
        bool,
        typer.Option("--list", help="List provenance snapshots for the given project."),
    ] = False,
    project_id: Annotated[
        str | None,
        typer.Option("--project", "-p", help="Project identifier (required with --list)."),
    ] = None,
    output_dir: Annotated[
        Path,
        typer.Option("--output-dir", help="Root output directory containing provenance/ snapshots."),
    ] = Path("outputs"),
) -> None:
    """
    Display provenance snapshots written by previous ``aprp run`` invocations.

    Each snapshot is a JSON file at
    ``<output_dir>/<project_id>/provenance/<run_id>.json`` and contains the
    Git SHA, timestamp, configuration values, and terminal status recorded
    by :func:`~econflow.core.provenance.record_run`.
    """
    if list_runs and project_id is None:
        console.print("[red]--list requires --project to be specified.[/red]")
        raise typer.Exit(code=1)

    raise NotImplementedError(
        "aprp reproduce is not yet implemented.  "
        "Implement econflow.core.provenance.record_run() first."
    )
