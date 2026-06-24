"""
econflow.cli.commands.validate — ``ai_productivity validate`` command.

Validates a project's configuration and (optionally) its ingested data
without running the estimation pipeline.  Useful as a pre-flight check in CI.

Exit codes
----------
0   All checks passed.
1   One or more validation errors detected.

Examples
--------
    # Validate configuration only
    $ ai_productivity validate ai_productivity

    # Validate configuration + check cached data quality
    $ ai_productivity validate ai_productivity --data

    # Emit a JSON report to stdout
    $ ai_productivity validate ai_productivity --data --format json
"""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

app = typer.Typer(help="Validate project configuration and data.")
console = Console()


class OutputFormat(str, Enum):
    """Supported output formats for the validation report."""

    RICH = "rich"
    JSON = "json"


@app.callback(invoke_without_command=True)
def validate(
    project_id: Annotated[str, typer.Argument(help="Project identifier.")],
    data: Annotated[
        bool,
        typer.Option("--data", help="Also validate cached / downloaded data quality."),
    ] = False,
    output_format: Annotated[
        OutputFormat,
        typer.Option("--format", help="Report format."),
    ] = OutputFormat.RICH,
    projects_dir: Annotated[
        Path,
        typer.Option("--projects-dir", help="Root directory containing project sub-directories."),
    ] = Path("projects"),
) -> None:
    """
    Validate the configuration (and optionally the data) for *project_id*.

    Performs the following checks:

    1. ``config.yaml`` parses without errors (:class:`~econflow.core.config.Settings`).
    2. All referenced indicator codes exist in the relevant source APIs.
    3. If ``--data`` is passed: runs :class:`~econflow.processing.quality.QualityReporter`
       over any cached data and surfaces warnings/errors.
    """
    raise NotImplementedError(
        "ai_productivity validate is not yet implemented.  "
        "Implement econflow.core.config.load_config() and "
        "econflow.processing.quality.QualityReporter first."
    )
