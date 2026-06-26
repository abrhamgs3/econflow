"""
econflow.cli.commands.project — ``ai_productivity project`` command group.

Manages APRP projects: listing discovered projects, showing metadata, and
initialising new project skeletons.

Sub-commands
------------
list    : List all projects discovered under the projects directory.
info    : Show detailed metadata for a single project.
init    : Scaffold a new project directory with template YAML files.

Examples
--------
    $ ai_productivity project list
    $ ai_productivity project info ai_productivity
    $ ai_productivity project init my_new_study --description "Trade and AI"
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

app = typer.Typer(help="Manage APRP projects.")
console = Console()


# ---------------------------------------------------------------------------
# list
# ---------------------------------------------------------------------------


@app.command("list")
def project_list(
    projects_dir: Annotated[
        Path,
        typer.Option("--projects-dir", help="Root directory containing project sub-directories."),
    ] = Path("projects"),
) -> None:
    """
    List all APRP projects discovered under *projects_dir*.

    Scans for ``config.yaml`` files and prints a Rich table with columns:
    ID, Name, Version, Description.
    """
    raise NotImplementedError(
        "ai_productivity project list is not yet implemented.  "
        "Implement econflow.core.registry.ProjectRegistry.discover() first."
    )


# ---------------------------------------------------------------------------
# info
# ---------------------------------------------------------------------------


@app.command("info")
def project_info(
    project_id: Annotated[str, typer.Argument(help="Project identifier.")],
    projects_dir: Annotated[
        Path,
        typer.Option("--projects-dir", help="Root directory containing project sub-directories."),
    ] = Path("projects"),
) -> None:
    """
    Display detailed configuration metadata for *project_id*.

    Prints the parsed :class:`~econflow.core.config.Settings` as a formatted
    Rich panel, including data sources, sample bounds, and variable
    assignments.
    """
    raise NotImplementedError(
        "ai_productivity project info is not yet implemented.  "
        "Implement econflow.core.config.load_config() first."
    )


# ---------------------------------------------------------------------------
# init
# ---------------------------------------------------------------------------


@app.command("init")
def project_init(
    project_id: Annotated[str, typer.Argument(help="New project identifier (used as directory name).")],
    description: Annotated[
        str,
        typer.Option("--description", "-d", help="Short project description."),
    ] = "",
    projects_dir: Annotated[
        Path,
        typer.Option("--projects-dir", help="Root directory containing project sub-directories."),
    ] = Path("projects"),
    overwrite: Annotated[
        bool,
        typer.Option("--overwrite", help="Overwrite existing project directory."),
    ] = False,
) -> None:
    """
    Scaffold a new APRP project directory at ``projects/<project_id>/``.

    Creates ``config.yaml``, ``models.yaml``, and ``outputs.yaml`` from the
    bundled templates, substituting *project_id* and *description*.

    Raises
    ------
    typer.Exit
        With exit code 1 if the directory already exists and ``--overwrite``
        is not set.
    """
    target = projects_dir / project_id
    if target.exists() and not overwrite:
        console.print(
            f"[red]Project directory '{target}' already exists.  "
            "Use --overwrite to replace it.[/red]"
        )
        raise typer.Exit(code=1)

    raise NotImplementedError(
        "ai_productivity project init is not yet implemented.  "
        "Wire up the template-copying logic once templates/ is in place."
    )
