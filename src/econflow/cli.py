"""
Command-line interface for the EconFlow panel econometrics platform.

Entry point: ``econflow`` (registered in pyproject.toml).

Commands
--------
econflow --version
    Print version and exit.

econflow init [DIRECTORY]
    Scaffold a new EconFlow project.

econflow doctor
    Comprehensive environment health check (Python, packages, git, LaTeX, …).

econflow validate
    Validate configuration files and project structure.

econflow info
    Display project version, estimator registry, and configuration summary.

econflow run [OPTIONS]
    Execute the analysis pipeline (generic or legacy mode).

econflow report [OUTPUT_DIR]
    Render estimation results into a publication-ready bundle
    (tables in CSV / LaTeX / Markdown / HTML, figures as JSON).

Examples
--------
    $ econflow --version
    EconFlow 0.1.0

    $ econflow init my_project
    EconFlow init — creating project my_project …

    $ econflow doctor
    EconFlow — environment health check …

    $ econflow validate --config config/config.yaml
    EconFlow validate …

    $ econflow info --config config/config.yaml
    EconFlow info …

    $ econflow run \\
          --config  config/config.yaml \\
          --models  config/models.yaml \\
          --outputs config/outputs.yaml
"""

from __future__ import annotations

import time
from pathlib import Path

import typer
from rich.console import Console

from econflow import __version__

app = typer.Typer(
    name="econflow",
    help="EconFlow — panel econometrics research platform.",
    add_completion=False,
    no_args_is_help=True,
)
console = Console()


# ---------------------------------------------------------------------------
# --version callback
# ---------------------------------------------------------------------------

def _version_callback(value: bool) -> None:
    if value:
        console.print(f"EconFlow {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        None,
        "--version",
        "-V",
        callback=_version_callback,
        is_eager=True,
        help="Show version and exit.",
    ),
) -> None:
    """EconFlow pipeline CLI."""


# ---------------------------------------------------------------------------
# init
# ---------------------------------------------------------------------------

@app.command()
def init(
    directory: Path = typer.Argument(
        Path("."),
        help="Directory for the new project.  Defaults to the current directory.",
    ),
    name: str = typer.Option(
        "",
        "--name", "-n",
        help=(
            "Project name used in YAML files and README.  "
            "Defaults to the directory's basename."
        ),
    ),
    force: bool = typer.Option(
        False,
        "--force",
        help="Overwrite existing files in the target directory without prompting.",
    ),
) -> None:
    """Scaffold a new EconFlow project with config files and directory structure.

    Creates:

        config/   (config.yaml, models.yaml, outputs.yaml)
        data/     (raw/, processed/)
        outputs/  (tables/, figures/, provenance/)
        paper/    (sections/)
        scripts/  (01_download_data.py, 02_clean_data.py)
        docs/
        notebooks/
        README.md
        .gitignore

    Examples:

        econflow init                     # init in current directory

        econflow init my_study            # init in ./my_study/

        econflow init my_study --force    # overwrite existing files
    """
    from econflow.commands.init import run_init

    exit_code = run_init(
        directory=directory,
        name=name,
        force=force,
        console=console,
    )
    if exit_code != 0:
        raise typer.Exit(code=exit_code)


# ---------------------------------------------------------------------------
# doctor
# ---------------------------------------------------------------------------

@app.command()
def doctor() -> None:
    """Inspect the environment and produce a health report.

    Checks Python version, all required and optional packages,
    external tools (git, LaTeX, pandoc), and operating system.

    Exit code is 0 when all required checks pass (warnings are allowed).
    """
    from econflow.commands.doctor import run_doctor

    exit_code = run_doctor(console)
    if exit_code != 0:
        raise typer.Exit(code=exit_code)


# ---------------------------------------------------------------------------
# validate
# ---------------------------------------------------------------------------

@app.command()
def validate(
    config: Path = typer.Option(
        Path("config/config.yaml"),
        "--config", "-c",
        help="Path to config.yaml.",
        show_default=True,
    ),
    models: Path = typer.Option(
        Path("config/models.yaml"),
        "--models",
        help="Path to models.yaml.",
        show_default=True,
    ),
    outputs: Path = typer.Option(
        Path("config/outputs.yaml"),
        "--outputs",
        help="Path to outputs.yaml.",
        show_default=True,
    ),
    data: bool = typer.Option(
        False,
        "--data",
        help=(
            "Also validate the data file referenced in config.yaml.  "
            "Checks column presence and duplicate panel keys."
        ),
    ),
) -> None:
    """Validate configuration files, directory structure, and variables.

    Runs a suite of checks on the three YAML configuration files and
    reports pass / warn / fail for each.  Optionally validates the
    processed data CSV when --data is set.

    Exit code is 0 when no FAIL checks are found (warnings are allowed).

    Examples:

        # Validate configuration only (defaults to config/ sub-directory)
        econflow validate

        # Validate with explicit paths
        econflow validate \\
            --config  examples/getting_started/config/config.yaml \\
            --models  examples/getting_started/config/models.yaml \\
            --outputs examples/getting_started/config/outputs.yaml

        # Also validate the data CSV
        econflow validate --data
    """
    from econflow.commands.validate import run_validate

    exit_code = run_validate(
        config_path=config,
        models_path=models,
        outputs_path=outputs,
        check_data=data,
        console=console,
    )
    if exit_code != 0:
        raise typer.Exit(code=exit_code)


# ---------------------------------------------------------------------------
# info
# ---------------------------------------------------------------------------

@app.command()
def info(
    config: Path = typer.Option(
        Path("config/config.yaml"),
        "--config", "-c",
        help="Path to config.yaml.  Skipped if the file does not exist.",
        show_default=True,
    ),
    models: Path = typer.Option(
        Path("config/models.yaml"),
        "--models",
        help="Path to models.yaml.  Skipped if the file does not exist.",
        show_default=True,
    ),
    outputs: Path = typer.Option(
        Path("config/outputs.yaml"),
        "--outputs",
        help="Path to outputs.yaml.  Skipped if the file does not exist.",
        show_default=True,
    ),
) -> None:
    """Display project information, estimator registry, and provenance status.

    Always shows: EconFlow version, Python version, registered estimators,
    and registered data connectors.

    When configuration files are found, also shows: project metadata,
    model specification list, output paths, and last provenance record.

    Examples:

        # Show platform info + estimator registry (no project needed)
        econflow info

        # Show full project summary
        econflow info \\
            --config  config/config.yaml \\
            --models  config/models.yaml \\
            --outputs config/outputs.yaml
    """
    from econflow.commands.info import run_info

    exit_code = run_info(
        config_path=config,
        models_path=models,
        outputs_path=outputs,
        console=console,
    )
    if exit_code != 0:
        raise typer.Exit(code=exit_code)


# ---------------------------------------------------------------------------
# run
# ---------------------------------------------------------------------------

@app.command()
def run(
    config: Path = typer.Option(
        None,
        "--config", "-c",
        help=(
            "Path to config.yaml for a generic panel pipeline. "
            "When provided, --models and --outputs are also required. "
            "Ignores --data-path, --tables-dir, --figures-dir, --paper-dir."
        ),
    ),
    models: Path = typer.Option(
        None,
        "--models",
        help="Path to models.yaml (required when --config is set).",
    ),
    outputs: Path = typer.Option(
        None,
        "--outputs",
        help="Path to outputs.yaml (required when --config is set).",
    ),
    data_path: Path = typer.Option(
        Path("data/processed/panel_clean.csv"),
        "--data-path", "-d",
        help="Path to the processed panel CSV (legacy pipeline, used when --config is absent).",
        show_default=True,
    ),
    tables_dir: Path = typer.Option(
        Path("tables"),
        "--tables-dir",
        help="Output directory for tables (legacy pipeline).",
        show_default=True,
    ),
    figures_dir: Path = typer.Option(
        Path("figures"),
        "--figures-dir",
        help="Output directory for figures (legacy pipeline).",
        show_default=True,
    ),
    paper_dir: Path = typer.Option(
        Path("paper/sections"),
        "--paper-dir",
        help="Output directory for auto-generated LaTeX narrative (legacy pipeline).",
        show_default=True,
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose", "-v",
        help="Enable DEBUG-level logging.",
    ),
) -> None:
    """Run the analysis pipeline.

    Generic mode (recommended for new projects):

        econflow run \\
            --config  config/config.yaml \\
            --models  models.yaml \\
            --outputs outputs.yaml

    Legacy mode (AI & Productivity paper replication):

        econflow run --data-path data/processed/panel_clean.csv
    """
    import logging

    from econflow.exceptions import EconFlowError
    from econflow.logging import configure_logging

    configure_logging(level=logging.DEBUG if verbose else logging.INFO)

    console.print()
    console.rule(f"[bold]EconFlow {__version__}[/bold]")
    console.print()

    t0 = time.perf_counter()

    # ------------------------------------------------------------------ Generic mode
    if config is not None:
        from econflow.pipeline_generic import run_from_config

        missing_flags = []
        if models is None:
            missing_flags.append("--models")
        if outputs is None:
            missing_flags.append("--outputs")
        if missing_flags:
            console.print(
                f"[bold red]✘ --config requires:[/bold red] {', '.join(missing_flags)}"
            )
            raise typer.Exit(code=1)

        for label, path in [("config", config), ("models", models), ("outputs", outputs)]:
            if not path.exists():
                console.print(f"[bold red]✘ {label} file not found:[/bold red] {path}")
                raise typer.Exit(code=1)

        try:
            run_from_config(
                config_path=config,
                models_path=models,
                outputs_path=outputs,
            )
        except EconFlowError as exc:
            console.print()
            console.print(f"[bold red]✘ Pipeline error:[/bold red] {exc}")
            raise typer.Exit(code=1)
        except Exception as exc:
            console.print()
            console.print(f"[bold red]✘ Unexpected error:[/bold red] {exc}")
            if verbose:
                import traceback
                traceback.print_exc()
            raise typer.Exit(code=1)

        elapsed = time.perf_counter() - t0
        console.print()
        console.rule("[bold green]Pipeline complete[/bold green]")
        console.print(f"  Completed in [bold]{elapsed:.1f} s[/bold]")
        console.print()
        return

    # ------------------------------------------------------------------ Legacy mode
    from econflow.pipeline import run as _run

    if not data_path.exists():
        console.print(f"[bold red]✘ Data file not found:[/bold red] {data_path}")
        console.print(
            "  Run [bold]scripts/02_clean_data.py[/bold] to generate it, "
            "or check --data-path."
        )
        raise typer.Exit(code=1)

    try:
        _run(
            data_path=data_path,
            tables_dir=tables_dir,
            figures_dir=figures_dir,
            paper_dir=paper_dir,
            verbose=verbose,
        )
    except EconFlowError as exc:
        console.print()
        console.print(f"[bold red]✘ Pipeline error:[/bold red] {exc}")
        raise typer.Exit(code=1)
    except Exception as exc:
        console.print()
        console.print(f"[bold red]✘ Unexpected error:[/bold red] {exc}")
        if verbose:
            import traceback
            traceback.print_exc()
        raise typer.Exit(code=1)

    elapsed = time.perf_counter() - t0

    console.print()
    console.rule("[bold green]Pipeline complete[/bold green]")
    console.print()

    _output_summary(tables_dir, figures_dir, paper_dir, elapsed)


# ---------------------------------------------------------------------------
# report
# ---------------------------------------------------------------------------

@app.command()
def report(
    output_dir: Path = typer.Argument(
        None,
        help="Directory where output files are written.  "
             "Defaults to outputs/econflow/ inside the project directory.",
    ),
    formats: str = typer.Option(
        "csv,latex,markdown,html",
        "--formats",
        help="Comma-separated renderer ids to apply to tables.",
        show_default=True,
    ),
    overwrite: bool = typer.Option(
        True,
        "--overwrite/--no-overwrite",
        help="Overwrite an existing output directory.",
        show_default=True,
    ),
    config: Path = typer.Option(
        None,
        "--config", "-c",
        help="Path to project config.yaml.",
    ),
) -> None:
    """Render a PublicationBundle from the last pipeline run.

    Writes tables (CSV, LaTeX, Markdown, HTML) and figures (JSON) into
    a structured directory.  Run 'econflow run' first to generate
    estimation results.

    Examples:

        # Render with all default formats
        econflow report

        # Render to a custom directory with LaTeX + CSV only
        econflow report outputs/paper --formats csv,latex
    """
    from econflow.commands.report import run_report

    resolved_dir = output_dir or Path.cwd() / "outputs" / "econflow"
    exit_code = run_report(
        output_dir=resolved_dir,
        formats=formats,
        overwrite=overwrite,
        config_path=config,
        console=console,
    )
    if exit_code != 0:
        raise typer.Exit(code=exit_code)


def _output_summary(
    tables_dir: Path,
    figures_dir: Path,
    paper_dir: Path,
    elapsed: float,
) -> None:
    """Print a concise summary of what was written."""
    def _count_files(d: Path, suffix: str) -> int:
        return len(list(d.glob(f"*{suffix}"))) if d.exists() else 0

    tables_csv  = _count_files(tables_dir, ".csv")
    tables_tex  = _count_files(tables_dir, ".tex")
    tables_txt  = _count_files(tables_dir, ".txt")
    figures_png = _count_files(figures_dir, ".png")
    paper_tex   = _count_files(paper_dir, ".tex")

    console.print(
        f"  [dim]tables/[/dim]    {tables_txt} model summaries "
        f"· {tables_csv} CSV · {tables_tex} LaTeX"
    )
    console.print(f"  [dim]figures/[/dim]   {figures_png} PNG")
    console.print(f"  [dim]{paper_dir}/[/dim]   {paper_tex} LaTeX narrative(s)")
    console.print()
    console.print(f"  Completed in [bold]{elapsed:.1f} s[/bold]")
    console.print()
