"""
econflow.cli.commands.run — ``ai_productivity run`` command.

Executes a full or partial pipeline run for a named APRP project.

Examples
--------
    # Full run of the ai_productivity project
    $ ai_productivity run ai_productivity

    # Run only the ingestion and processing stages
    $ ai_productivity run ai_productivity --stages ingestion --stages processing

    # Force re-run of all stages even if outputs are up to date
    $ ai_productivity run ai_productivity --force

    # Print the execution plan without running
    $ ai_productivity run ai_productivity --dry-run
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

app = typer.Typer(help="Execute a project pipeline run.")
console = Console()


@app.callback(invoke_without_command=True)
def run(
    project_id: Annotated[str, typer.Argument(help="Project identifier (sub-directory name under projects/).")],
    stages: Annotated[
        list[str] | None,
        typer.Option("--stages", "-s", help="Limit execution to these stages (repeatable)."),
    ] = None,
    force: Annotated[
        bool,
        typer.Option("--force", "-f", help="Re-run stages even if outputs are up to date."),
    ] = False,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", "-n", help="Print execution plan without running anything."),
    ] = False,
    projects_dir: Annotated[
        Path,
        typer.Option("--projects-dir", help="Root directory containing project sub-directories."),
    ] = Path("projects"),
) -> None:
    """
    Run the APRP pipeline for *project_id*.

    Loads the project configuration from ``projects/<project_id>/config.yaml``,
    constructs the DAG-based :class:`~econflow.core.pipeline.Pipeline`, resolves
    the stage execution order, and runs each stage in sequence while recording
    provenance.
    """
    raise NotImplementedError(
        "ai_productivity run is not yet implemented.  "
        "Implement econflow.core.pipeline.Pipeline.run() first."
    )
