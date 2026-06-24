"""
econflow.cli_scaffold.main — Future scaffold CLI root (NOT YET ACTIVE).

This module defines the command surface for the EconFlow scaffold architecture.
It is NOT registered in ``pyproject.toml`` and is NOT importable at runtime
until the scaffold package becomes the authoritative implementation (see
``docs/MIGRATION_PLAN.md``, Phase 4).

The active CLI is ``src/econflow/cli.py``, registered as:

    [project.scripts]
    econflow = "econflow.cli:app"

Planned command surface (once active)
--------------------------------------
    $ econflow run <project_id>
    $ econflow validate <project_id>
    $ econflow reproduce --list --project <project_id>
    $ econflow project list
"""

from __future__ import annotations

import typer
from rich.console import Console

from econflow.cli.commands import project, reproduce, run, validate

app = typer.Typer(
    name="econflow",
    help="EconFlow — reproducible panel econometrics research platform.",
    add_completion=True,
    no_args_is_help=True,
    pretty_exceptions_enable=True,
    pretty_exceptions_show_locals=False,
)

console = Console()

# ---------------------------------------------------------------------------
# Register sub-command groups / commands
# ---------------------------------------------------------------------------

app.add_typer(run.app, name="run")
app.add_typer(validate.app, name="validate")
app.add_typer(reproduce.app, name="reproduce")
app.add_typer(project.app, name="project")


# ---------------------------------------------------------------------------
# Global options callback
# ---------------------------------------------------------------------------


@app.callback()
def main(
    version: bool = typer.Option(
        False,
        "--version",
        "-V",
        help="Print version and exit.",
        is_eager=True,
    ),
) -> None:
    """EconFlow research platform."""
    if version:
        from econflow import __version__

        console.print(f"econflow {__version__}")
        raise typer.Exit()


if __name__ == "__main__":
    app()
