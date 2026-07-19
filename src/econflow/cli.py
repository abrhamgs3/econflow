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
    [beta] Write an empty PublicationBundle scaffold (manifest.json).
    Results-loading is not yet implemented — use outputs/tables/
    (written by 'econflow run') for publication tables.

econflow certify
    Generate a reproducibility certificate for the current run.

econflow verify
    Compare two certificates and report environment / data drift.

econflow package
    Build a journal-ready replication package directory.

econflow reproduce [PROJECT_DIR]
    Reproduce a project from its configuration in an isolated subprocess.

econflow fetch <CONNECTOR_ID>
    Download a dataset using a registered connector.

econflow cache list|inspect|clear|purge
    Inspect and manage the local dataset cache.

econflow datasets
    List all registered data connectors.

econflow release-check
    Run the EconFlow Release Quality Gate (9 checks; exits 1 on any blocker).

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

    $ econflow certify \\
          --project-name "My Study" \\
          --data data/processed/panel.csv \\
          --config config/config.yaml

    $ econflow verify --baseline outputs/certificate.json

    $ econflow package --certificate outputs/certificate.json

    $ econflow reproduce examples/blind_replication/

    $ econflow fetch world_bank --param indicators=IT.NET.USER.ZS --param year_start=2000

    $ econflow cache list

    $ econflow datasets
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import typer
from rich.console import Console

from econflow import __version__

# ---------------------------------------------------------------------------
# Windows Unicode compatibility (F1 fix)
# ---------------------------------------------------------------------------
# On a stock Windows terminal (default cp1252 codepage), Rich's Unicode
# glyphs (✔, ✘, ─, …) raise UnicodeEncodeError when stdout is written.
# Reconfiguring stdout/stderr to UTF-8 before the first Console call fixes
# this transparently.  PYTHONIOENCODING=utf-8 achieves the same result but
# requires the user to know about the workaround; we handle it automatically.
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
        sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    except AttributeError:
        # Fallback for environments where reconfigure is unavailable
        import io
        sys.stdout = io.TextIOWrapper(
            sys.stdout.buffer, encoding="utf-8", errors="replace"
        )
        sys.stderr = io.TextIOWrapper(
            sys.stderr.buffer, encoding="utf-8", errors="replace"
        )

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
    """EconFlow — reproducible panel econometrics platform.

    Typical workflow for a new project:

    \b
        # 1. Check your environment
        econflow doctor

        # 2. Scaffold a new project
        econflow init my_study
        cd my_study

        # 3. Validate configuration before running
        econflow validate config/

        # 4. Run the analysis pipeline
        econflow run \\
            --config  config/config.yaml \\
            --models  config/models.yaml \\
            --outputs config/outputs.yaml

        # 5. Certify reproducibility
        econflow certify --project-name "My Study" \\
            --data data/processed/panel.csv \\
            --config config/config.yaml

    Run `econflow COMMAND --help` for full documentation on any command.
    See `docs/user/CLI_GUIDE.md` or `examples/getting_started/` to get started.
    """


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

    Common mistakes:

    \b
        * Forgetting to cd into the new directory before running other commands.
          Fix: cd my_study && econflow doctor

        * Using a name with spaces — YAML keys cannot contain spaces.
          Fix: econflow init my_study_2024  (use underscores, not spaces)

        * Running econflow init twice without --force causes a "not empty" error.
          Fix: econflow init my_study --force

    Expected output:

    \b
        EconFlow init — creating project my_study …
        ✔  config/config.yaml
        ✔  config/models.yaml
        ✔  config/outputs.yaml
        ✔  data/raw/          (empty, for raw downloads)
        ✔  data/processed/    (empty, place your panel.csv here)
        ✔  outputs/tables/
        ✔  README.md
        Project scaffold complete.
        Next: cd my_study && econflow doctor
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

    Checks performed:

    \b
        System          Python version, OS, CPU, RAM
        Core packages   pandas, numpy, linearmodels, statsmodels, …
        External tools  git, LaTeX (pdflatex/xelatex), pandoc, pip, uv
        Optional        pytest, ruff, pyarrow, jupyter, streamlit
        Project         config files present, data/outputs directories
        Configuration   YAML syntax valid, schema + semantic rules pass

    Exit code is 0 when all required checks pass (warnings are allowed).

    Examples:

    \b
        # Check environment from anywhere
        econflow doctor

        # Check environment inside a project
        cd my_study
        econflow doctor

    Common mistakes:

    \b
        * Running doctor before activating your virtual environment —
          package checks will fail even if the packages are installed.
          Fix: activate venv first, then re-run econflow doctor.

        * LaTeX showing WARN but tables still render to .tex — the .tex
          file is written regardless; WARN means you cannot *compile* it
          to PDF locally.  Install TeX Live to enable PDF compilation.

    Expected output (abbreviated):

    \b
        EconFlow — environment health check

        System
          ✔  SYS-01  Python 3.11.9
          ℹ  SYS-02  Operating system     Linux 6.5 (x86_64)

        Core packages
          ✔  PKG-01  pandas 2.2.2
          ✔  PKG-04  linearmodels 6.1

        External tools
          ✔  EXT-01  git                  git version 2.43.0
          ✔  EXT-02  LaTeX (pdflatex)     pdfTeX 3.141592653

        Project structure
          ✔  PRJ-01  config.yaml          config/config.yaml
          ✔  PRJ-02  models.yaml          config/models.yaml

        ✔ Ready  (24 passed, 2 warning(s))
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
    config_dir: Path | None = typer.Argument(
        None,
        help=(
            "Directory containing config.yaml, models.yaml, and outputs.yaml.  "
            "Defaults to ./config/ when omitted."
        ),
        show_default=False,
    ),
    config: Path = typer.Option(
        None,
        "--config", "-c",
        help=(
            "Explicit path to config.yaml.  "
            "When set, overrides the positional config_dir for this file."
        ),
        show_default=False,
    ),
    models: Path = typer.Option(
        None,
        "--models",
        help=(
            "Explicit path to models.yaml.  "
            "When set, overrides the positional config_dir for this file."
        ),
        show_default=False,
    ),
    outputs: Path = typer.Option(
        None,
        "--outputs",
        help=(
            "Explicit path to outputs.yaml.  "
            "When set, overrides the positional config_dir for this file."
        ),
        show_default=False,
    ),
    data: bool = typer.Option(
        False,
        "--data",
        help=(
            "Also validate the data file referenced in config.yaml.  "
            "Checks column presence and duplicate panel keys."
        ),
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose", "-v",
        help="Show passing checks as well as failures.",
    ),
) -> None:
    """Validate configuration files against schema and semantic rules.

    Runs three validation phases and prints a structured report:

        ✓ schema valid
        ✓ semantic validation passed
        ✓ cross-file validation passed

    Any errors are shown with an actionable Fix hint.

    CONFIG_DIR is the directory containing config.yaml, models.yaml, and
    outputs.yaml.  Defaults to ./config/ when omitted.

    Exit code is 0 when errors = 0 (warnings are allowed).

    Examples:

    \b
        # Validate config/ sub-directory (default)
        econflow validate

        # Validate an explicit directory
        econflow validate config/

        # Validate a project in a different location
        econflow validate examples/getting_started/config/

        # Also validate the data CSV referenced in config.yaml
        econflow validate --data

        # Explicit per-file overrides
        econflow validate \\
            --config  path/to/config.yaml \\
            --models  path/to/models.yaml \\
            --outputs path/to/outputs.yaml

    Common mistakes:

    \b
        * Running econflow run before econflow validate — validation errors
          surface as confusing runtime errors.
          Fix: always run econflow validate first.

        * Editing YAML with tabs instead of spaces — YAML parsers reject tabs.
          Fix: configure your editor to use 2- or 4-space indentation.

        * Specifying regressors that don't exist in the data file.
          Fix: econflow validate --data checks column presence.

    Expected output:

    \b
        EconFlow validate

        Schema validation
          ✔  CFG-01  config.yaml syntax valid
          ✔  CFG-02  models.yaml syntax valid
          ✔  CFG-03  outputs.yaml syntax valid

        Semantic validation
          ✔  L-01  project_name present
          ✔  L-04  dependent column present in data

        ✔ Validation passed  (0 errors, 0 warnings)
    """
    from econflow.commands.validate import run_validate

    # Resolve directory: positional arg > default of ./config/
    base_dir = Path(config_dir) if config_dir else Path("config")

    config_path  = config  if config  is not None else base_dir / "config.yaml"
    models_path  = models  if models  is not None else base_dir / "models.yaml"
    outputs_path = outputs if outputs is not None else base_dir / "outputs.yaml"

    exit_code = run_validate(
        config_path=config_path,
        models_path=models_path,
        outputs_path=outputs_path,
        check_data=data,
        console=console,
        verbose=verbose,
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

    \b
        # Show platform info + estimator registry (no project needed)
        econflow info

        # Show full project summary
        econflow info \\
            --config  config/config.yaml \\
            --models  config/models.yaml \\
            --outputs config/outputs.yaml

    Common mistakes:

    \b
        * Running econflow info from outside a project — config files will
          not be found.  This is fine; you still see the platform summary.

        * Stale provenance data — the "last run" section reflects the most
          recent outputs/provenance/ record; re-run to refresh.

    Expected output (abbreviated):

    \b
        EconFlow 0.1.0 · Python 3.11.9

        Platform
          Project   my_study
          Root      /home/user/my_study

        Estimators (8 registered)
          entity_fe  · ols  · two_way_fe  · …

        Models
          (1) investment ~ value + capital  [entity_fe]
          (2) investment ~ value + capital  [two_way_fe]
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
        help="Path to config.yaml.  Also requires --models and --outputs.",
    ),
    models: Path = typer.Option(
        None,
        "--models",
        help="Path to models.yaml.",
    ),
    outputs: Path = typer.Option(
        None,
        "--outputs",
        help="Path to outputs.yaml.",
    ),
    # ------------------------------------------------------------------
    # Deprecated legacy options (AI & Productivity paper replication path).
    # These remain functional until v0.3.0 to preserve backward compatibility.
    # Use `econflow run --config` instead.
    # ------------------------------------------------------------------
    data_path: Path = typer.Option(
        None,
        "--data-path", "-d",
        help=(
            "[DEPRECATED v0.3.0] Run the AI & Productivity legacy pipeline against "
            "a raw panel CSV.  Use --config / --models / --outputs for all new projects."
        ),
        hidden=True,
    ),
    tables_dir: Path = typer.Option(
        Path("tables"),
        "--tables-dir",
        help="[DEPRECATED] Output directory for tables (legacy pipeline).",
        show_default=True,
        hidden=True,
    ),
    figures_dir: Path = typer.Option(
        Path("figures"),
        "--figures-dir",
        help="[DEPRECATED] Output directory for figures (legacy pipeline).",
        show_default=True,
        hidden=True,
    ),
    paper_dir: Path = typer.Option(
        Path("paper/sections"),
        "--paper-dir",
        help="[DEPRECATED] Output directory for LaTeX narrative (legacy pipeline).",
        show_default=True,
        hidden=True,
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose", "-v",
        help="Enable DEBUG-level logging.",
    ),
) -> None:
    """Run the EconFlow analysis pipeline.

    Requires three YAML configuration files produced by ``econflow init``.
    Run ``econflow validate`` first to catch configuration errors before
    the pipeline starts.

    Examples:

    \b
        # Standard run (config-driven)
        econflow run \\
            --config  config/config.yaml \\
            --models  config/models.yaml \\
            --outputs config/outputs.yaml

        # Getting-started example (bundled)
        econflow run \\
            --config  examples/getting_started/config/config.yaml \\
            --models  examples/getting_started/config/models.yaml \\
            --outputs examples/getting_started/config/outputs.yaml

        # With verbose logging
        econflow run \\
            --config  config/config.yaml \\
            --models  config/models.yaml \\
            --outputs config/outputs.yaml \\
            --verbose

    Common mistakes:

    \b
        * Passing config files in the wrong order — each flag has a specific
          role: --config is the project config, --models is the estimator
          list, --outputs controls where files are written.

        * Missing or misnamed data file — if the path in config.yaml does
          not match an existing file the pipeline exits immediately.
          Fix: econflow validate --data to check all paths before running.

        * Omitting one of the three required flags — econflow run will print
          an actionable error and exit with code 1.

    Expected output (abbreviated):

    \b
        ──────────────── EconFlow 0.1.0 ────────────────

        INFO  [1/5] Loading data: data/processed/panel.csv
        INFO  [2/5] Validating panel structure
        INFO  [3/5] Running models
        INFO  [3.5/5] Writing diagnostics
        INFO  [4/5] Exporting tables
        INFO  [5/5] Recording provenance

        ────────────────── Pipeline complete ──────────────────
          Completed in 3.2 s
    """
    import logging

    from econflow.exceptions import EconFlowError
    from econflow.logging import configure_logging

    configure_logging(level=logging.DEBUG if verbose else logging.INFO)

    console.print()
    console.rule(f"[bold]EconFlow {__version__}[/bold]")
    console.print()

    t0 = time.perf_counter()

    # ------------------------------------------------------------------
    # Legacy mode guard — --data-path was provided explicitly.
    # Emit a deprecation warning and route to the AI&P pipeline for
    # backward compatibility.  This path is removed in v0.3.0.
    # ------------------------------------------------------------------
    if data_path is not None:
        import warnings
        warnings.warn(
            "econflow run --data-path is deprecated and will be removed in "
            "EconFlow v0.3.0.  Use --config / --models / --outputs instead.  "
            "See: econflow run --help",
            DeprecationWarning,
            stacklevel=2,
        )
        console.print()
        console.print(
            "[bold yellow]⚠  Deprecation warning[/bold yellow]: "
            "--data-path invokes the legacy AI & Productivity pipeline.  "
            "This mode is removed in v0.3.0."
        )
        console.print(
            "   For new projects use the config-driven pipeline:\n"
            "   [dim]econflow run --config config/config.yaml "
            "--models config/models.yaml --outputs config/outputs.yaml[/dim]"
        )
        console.print()

        from econflow.pipeline import run as _run  # type: ignore[import]

        if not data_path.exists():
            console.print(f"[bold red]✘ Data file not found:[/bold red] {data_path}")
            console.print(
                "  Provide the path to a processed panel CSV with --data-path."
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
        return

    # ------------------------------------------------------------------
    # Generic pipeline — the canonical path for all new projects.
    # ------------------------------------------------------------------
    if config is None:
        console.print(
            "[bold red]✘  econflow run requires --config, --models, and --outputs.[/bold red]"
        )
        console.print()
        console.print("  Run [bold]econflow init[/bold] to create a project skeleton, then:")
        console.print(
            "  [dim]econflow run \\\n"
            "      --config  config/config.yaml \\\n"
            "      --models  config/models.yaml \\\n"
            "      --outputs config/outputs.yaml[/dim]"
        )
        console.print()
        console.print(
            "  Or try the Getting Started example:\n"
            "  [dim]econflow run \\\n"
            "      --config  examples/getting_started/config/config.yaml \\\n"
            "      --models  examples/getting_started/config/models.yaml \\\n"
            "      --outputs examples/getting_started/config/outputs.yaml[/dim]"
        )
        raise typer.Exit(code=1)

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

    # Pre-flight: validate config before touching any output files.
    from econflow.config.validator import ConfigValidator as _ConfigValidator
    from econflow.core.exceptions import ConfigValidationError as _ConfigValidationError
    try:
        _validator = _ConfigValidator()
        _validator.validate_strict(
            config_path=config,
            models_path=models,
            outputs_path=outputs,
            check_data=True,
        )
    except _ConfigValidationError as _exc:
        console.print()
        console.print(
            f"[bold red]✘ Configuration validation failed "
            f"({_exc.error_count} error(s)).[/bold red]"
        )
        for _issue in _exc.errors[:20]:
            console.print(
                f"  [red]·[/red] [{_issue.stage}] "
                f"[bold]{_issue.source}[/bold] "
                f"[dim]{_issue.location}[/dim]"
            )
            console.print(f"      {_issue.message}")
            if _issue.fix:
                console.print(f"      [dim]Fix: {_issue.fix}[/dim]")
        if len(_exc.errors) > 20:
            console.print(
                f"  [dim]… and {len(_exc.errors) - 20} more error(s).  "
                "Run `econflow validate` for the full report.[/dim]"
            )
        console.print()
        console.print(
            "[dim]Run [bold]econflow validate[/bold] for the full "
            "validation report.[/dim]"
        )
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


# ---------------------------------------------------------------------------
# report
# ---------------------------------------------------------------------------

@app.command()
def report(
    output_dir: Path = typer.Argument(
        None,
        help="Directory where output files are written.  "
             "Defaults to outputs/econflow/ relative to the current working directory.  "
             "Note: the canonical publication tables are in outputs/tables/ (written by "
             "'econflow run'); this command produces an additional bundle.",
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
    """[beta] Write an empty PublicationBundle scaffold (results-loading not yet implemented).

    NOTE: This command is a beta feature.  'econflow run' already writes
    tables to the outputs/tables/ directory defined in outputs.yaml.
    Use those files for publication tables.

    As currently implemented, this command does NOT load or render your
    estimation results, regardless of whether 'econflow run' has already
    been executed: the step that would deserialise saved results and feed
    them to the table/figure builders is an unimplemented placeholder
    (see econflow/commands/report.py).  Every invocation writes a bundle
    directory containing only an empty manifest.json (0 tables, 0 figures)
    — this is not an error, and the command exits 0.  Loading real results
    is planned for a future release.

    Examples:

    \b
        # Write an empty bundle scaffold with all default formats
        econflow report

        # Write to a custom directory with LaTeX + CSV renderer ids selected
        # (still produces 0 tables/figures today — see note above)
        econflow report outputs/paper --formats csv,latex

        # Render from an explicit config
        econflow report --config config/config.yaml

    Common mistakes:

    \b
        * Expecting 'econflow report' to render your regression tables.
          It does not yet — for publication tables, use the files
          'econflow run' already wrote to outputs/tables/.

        * Specifying an unknown format ID — valid IDs are:
          csv, latex, markdown, html, json.

    Expected output (current behaviour, verbatim):

    \b
        EconFlow — Reporting Engine
          Output dir : outputs/econflow
          Formats    : csv, latex, markdown, html
          Overwrite  : True

          ⚠  No saved results found in outputs/results.
               Run econflow run first, then re-run econflow report.

          ✔  Bundle written — 0 table(s), 0 figure(s)
               Directory : outputs/econflow
               Manifest  : outputs/econflow/manifest.json
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


# ---------------------------------------------------------------------------
# certify
# ---------------------------------------------------------------------------

@app.command()
def certify(
    project_name: str = typer.Option(
        "",
        "--project-name", "-p",
        help="Human-readable project name stored in the certificate.",
    ),
    data: list[Path] = typer.Option(
        [],
        "--data", "-d",
        help="Input dataset path(s) to fingerprint.  Repeat for multiple files.",
    ),
    config: Path = typer.Option(
        None,
        "--config", "-c",
        help="Path to project config.yaml (SHA-256 is recorded).",
    ),
    output: Path = typer.Option(
        Path("outputs/certificate.json"),
        "--output", "-o",
        help="Destination for the JSON certificate.",
        show_default=True,
    ),
    checks: bool = typer.Option(
        False,
        "--checks/--no-checks",
        help="Run integrity checks (requires --results).  Off by default.",
        show_default=True,
    ),
    repo_root: Path = typer.Option(
        None,
        "--repo-root",
        help="Git repository root.  Defaults to the current directory.",
    ),
) -> None:
    """Generate a reproducibility certificate for the current pipeline run.

    Records the git commit, Python version, package versions, SHA-256
    fingerprints of all input datasets, and the config file checksum.
    Optionally runs all registered integrity checks.

    Examples:

        # Minimal certificate
        econflow certify --project-name "My Study"

        # With data and config fingerprints
        econflow certify \\
            --project-name "Panel Growth Study" \\
            --data data/processed/panel.csv \\
            --config config/config.yaml \\
            --output outputs/certificate.json

        # Include data fingerprints for multiple datasets
        econflow certify \\
            --project-name "Multi-source Study" \\
            --data data/processed/panel_a.csv \\
            --data data/processed/panel_b.csv \\
            --config config/config.yaml

    Common mistakes:

    \b
        * Certifying before committing changes — the git SHA recorded in
          the certificate will differ from the published commit.
          Fix: git commit first, then econflow certify.

        * Forgetting --data — the certificate omits data fingerprints and
          a reviewer cannot verify the inputs.
          Fix: always pass --data for every input dataset.

    Expected output:

    \b
        EconFlow certify

        ✔  Git SHA         4f3b2af
        ✔  Python          3.11.9
        ✔  pandas          2.2.2
        ✔  data/processed/panel.csv  sha256: a1b2c3…
        ✔  config/config.yaml        sha256: d4e5f6…

        Certificate written: outputs/certificate.json
    """
    from econflow.commands.certify import run_certify

    if not project_name:
        console.print(
            "[bold yellow]⚠  Warning:[/bold yellow] --project-name is empty.  "
            "The certificate will not identify the study."
        )
        console.print(
            "  Tip: [dim]econflow certify --project-name \"My Study\" ...[/dim]"
        )
        console.print()

    exit_code = run_certify(
        project_name=project_name,
        data_paths=list(data),
        config_path=config,
        output_path=output,
        run_checks=checks,
        estimator_results=None,
        repo_root=repo_root,
        console=console,
    )
    if exit_code != 0:
        raise typer.Exit(code=exit_code)


# ---------------------------------------------------------------------------
# verify
# ---------------------------------------------------------------------------

@app.command()
def verify(
    baseline: Path = typer.Option(
        ...,
        "--baseline", "-b",
        help="Path to the baseline certificate JSON.",
    ),
    current: Path = typer.Option(
        None,
        "--current",
        help=(
            "Path to the current certificate JSON.  "
            "When omitted, the live environment is captured and compared."
        ),
    ),
    output: Path = typer.Option(
        None,
        "--output", "-o",
        help="Optional destination for the JSON drift report.",
    ),
) -> None:
    """Compare two reproducibility certificates and report drift.

    When --current is omitted, the live environment is captured and
    compared against the baseline.

    Exit code is 0 when status is 'pass' or 'warn'; 1 when 'fail'.

    Examples:

        # Compare live environment against a stored certificate
        econflow verify --baseline outputs/certificate.json

        # Compare two stored certificates
        econflow verify \\
            --baseline outputs/baseline_cert.json \\
            --current outputs/current_cert.json \\
            --output outputs/drift_report.json

    Common mistakes:

    \b
        * Comparing certificates from different projects — version and
          package drift will be flagged; data drift will be meaningless.
          Fix: always compare certificates from the same project.

        * Treating "warn" exit code (0) as a pass without reviewing the
          report — warnings indicate package version changes that may
          affect numeric results.

    Expected output:

    \b
        EconFlow verify

        Drift report
          ✔  Git SHA      match   4f3b2af
          ✔  Python       match   3.11.9
          ⚠  pandas       drift   2.1.4 → 2.2.2
          ✔  data inputs  match   (SHA-256 identical)

        Status: warn  (1 package version changed)
        Exit code: 0
    """
    from econflow.commands.verify import run_verify

    exit_code = run_verify(
        baseline_path=baseline,
        current_path=current,
        output_path=output,
        console=console,
    )
    if exit_code != 0:
        raise typer.Exit(code=exit_code)


# ---------------------------------------------------------------------------
# package
# ---------------------------------------------------------------------------

@app.command(name="package")
def package_cmd(
    certificate: Path = typer.Option(
        None,
        "--certificate", "--cert",
        help="Path to the reproducibility certificate to include.",
    ),
    config: list[Path] = typer.Option(
        [],
        "--config", "-c",
        help="Config file(s) to copy into config/.  Repeat for multiple files.",
    ),
    script: list[Path] = typer.Option(
        [],
        "--script", "-s",
        help="Replication script(s) to copy into scripts/.  Repeat for multiple.",
    ),
    output_dir: Path = typer.Option(
        Path("replication_package"),
        "--output-dir", "-o",
        help="Destination directory for the replication package.",
        show_default=True,
    ),
    overwrite: bool = typer.Option(
        True,
        "--overwrite/--no-overwrite",
        help="Overwrite an existing output directory.",
        show_default=True,
    ),
    data_readme: str = typer.Option(
        "",
        "--data-readme",
        help="Data availability note included in the package README.",
    ),
) -> None:
    """Build a journal-ready replication package.

    Collects the reproducibility certificate, configuration files, and
    replication scripts into a structured directory suitable for archival
    or journal submission.

    Output layout:

        replication_package/
            README.md
            certificate.json
            environment.txt
            config/
            scripts/
            manifest.json

    Examples:

        # Minimal package
        econflow package --certificate outputs/certificate.json

        # Full package with configs and scripts
        econflow package \\
            --certificate outputs/certificate.json \\
            --config config/config.yaml \\
            --config config/models.yaml \\
            --script scripts/01_download.py \\
            --script scripts/02_run.py \\
            --output-dir replication_package/

    Common mistakes:

    \b
        * Omitting --certificate — the package README will note that no
          certificate was provided, reducing reproducibility guarantees.

        * Not including all config files — a reviewer cannot reproduce
          the analysis without config.yaml, models.yaml, and outputs.yaml.
          Fix: pass all three with --config.

    Expected output:

    \b
        EconFlow package

        Building replication package …
          ✔  README.md
          ✔  certificate.json
          ✔  environment.txt
          ✔  config/config.yaml
          ✔  config/models.yaml
          ✔  scripts/01_download.py
          ✔  manifest.json

        Package written to: replication_package/  (7 files)
    """
    from econflow.commands.package_cmd import run_package

    exit_code = run_package(
        certificate_path=certificate,
        config_paths=list(config),
        script_paths=list(script),
        output_dir=output_dir,
        overwrite=overwrite,
        data_readme=data_readme,
        console=console,
    )
    if exit_code != 0:
        raise typer.Exit(code=exit_code)


# ---------------------------------------------------------------------------
# fetch
# ---------------------------------------------------------------------------

@app.command()
def fetch(
    connector_id: str = typer.Argument(
        ...,
        help="Connector registry ID (e.g. 'world_bank', 'csv', 'fred', 'oecd', 'pwt').",
    ),
    param: list[str] = typer.Option(
        [],
        "--param", "-p",
        help=(
            "Connector parameter as key=value.  Repeat for multiple params.  "
            "Values are auto-parsed: comma-separated strings become lists, "
            "integers and booleans are coerced.  "
            "Examples: --param indicators=IT.NET.USER.ZS  "
            "--param year_start=2000  --param series_ids=GDPPC,UNRATE"
        ),
    ),
    cache_dir: Path = typer.Option(
        Path(".cache/econflow"),
        "--cache-dir",
        help="Root directory for the dataset cache.",
        show_default=True,
    ),
    force: bool = typer.Option(
        False,
        "--force",
        help="Re-download even if a cached copy exists.",
    ),
    no_validate: bool = typer.Option(
        False,
        "--no-validate",
        help="Skip validation after download.",
    ),
    manifest: Path = typer.Option(
        None,
        "--manifest", "-m",
        help="Write/update a dataset manifest JSON file.",
    ),
    project: str = typer.Option(
        "",
        "--project",
        help="Project name recorded in the manifest.",
    ),
) -> None:
    """Download a dataset using a registered connector.

    Connects to the data source, downloads to the local cache, runs
    validation, prints metadata, and optionally records a manifest entry.

    Examples:

        # Download World Bank internet usage indicator
        econflow fetch world_bank \\
            --param indicators=IT.NET.USER.ZS \\
            --param year_start=2000 \\
            --param year_end=2022

        # Download FRED series
        econflow fetch fred \\
            --param series_ids=GDPPC,UNRATE \\
            --param start_date=2000-01-01 \\
            --param frequency=a

        # Download local CSV (no network)
        econflow fetch csv --param path=data/raw/panel.csv

        # Force re-download and update manifest
        econflow fetch world_bank \\
            --param indicators=NY.GDP.MKTP.CD \\
            --force \\
            --manifest outputs/manifest.json

    Common mistakes:

    \b
        * Misspelling the connector ID — use econflow datasets to see
          all registered IDs.

        * Omitting required parameters — each connector has mandatory
          params; the error message lists them when any are missing.

        * Passing a list as a single --param string: use comma separation
          (--param series_ids=A,B) not multiple equals signs.

    Expected output:

    \b
        EconFlow fetch — world_bank

        Connector  World Bank Open Data
        Indicators IT.NET.USER.ZS
        Years      2000 – 2022

        ✔  Downloaded  1 indicator × 45 countries × 23 years
        ✔  Validated   no missing entity-year keys
        ✔  Cached      .cache/econflow/a1b2c3…/

        Metadata
          Source     World Bank Open Data API
          Retrieved  2024-01-15
          Rows       1035
          Columns    country, year, IT.NET.USER.ZS
    """
    from econflow.commands.fetch_cmd import _parse_param_value, run_fetch

    # Parse --param key=value pairs
    params: dict = {}
    for kv in param:
        if "=" not in kv:
            console.print(f"[red]Error:[/red] --param must be key=value, got: {kv!r}")
            raise typer.Exit(code=1)
        k, _, v = kv.partition("=")
        params[k.strip()] = _parse_param_value(v.strip())

    exit_code = run_fetch(
        connector_id=connector_id,
        params=params,
        cache_dir=cache_dir,
        force=force,
        no_validate=no_validate,
        output_manifest=manifest,
        project=project,
        console=console,
    )
    if exit_code != 0:
        raise typer.Exit(code=exit_code)


# ---------------------------------------------------------------------------
# cache
# ---------------------------------------------------------------------------

cache_app = typer.Typer(
    name="cache",
    help="Inspect and manage the local dataset cache.",
    no_args_is_help=True,
)
app.add_typer(cache_app)


@cache_app.command("list")
def cache_list(
    cache_dir: Path = typer.Option(
        Path(".cache/econflow"),
        "--cache-dir",
        help="Root cache directory.",
        show_default=True,
    ),
) -> None:
    """List all cached datasets.

    Shows cache key, connector ID, retrieval date, row count, and size
    for every slot in the cache directory.

    Examples:

    \b
        econflow cache list

        econflow cache list --cache-dir /data/.cache/econflow

    Expected output:

    \b
        EconFlow cache — 3 slot(s)

        Key       Connector    Date        Rows   Size
        a1b2c3…   world_bank   2024-01-15  1035   128 KB
        d4e5f6…   fred         2024-01-10   480    42 KB
        a7b8c9…   csv          2024-01-08   200     8 KB
    """
    from econflow.commands.cache_cmd import run_cache_list

    exit_code = run_cache_list(cache_dir=cache_dir, console=console)
    if exit_code != 0:
        raise typer.Exit(code=exit_code)


@cache_app.command("inspect")
def cache_inspect(
    key: str = typer.Argument(..., help="Cache key (hex string from 'econflow cache list')."),
    cache_dir: Path = typer.Option(
        Path(".cache/econflow"),
        "--cache-dir",
        help="Root cache directory.",
        show_default=True,
    ),
) -> None:
    """Show detailed metadata for one cache slot.

    Prints the full metadata record stored alongside the cached dataset,
    including connector parameters, validation results, and file paths.

    Examples:

    \b
        # Get the key from: econflow cache list
        econflow cache inspect a1b2c3def456

    Expected output:

    \b
        Cache slot: a1b2c3def456

        Connector    world_bank
        Retrieved    2024-01-15T10:23:45
        Rows         1035
        Columns      country, year, IT.NET.USER.ZS
        Parameters   indicators=IT.NET.USER.ZS year_start=2000 year_end=2022
        Validated    True
        File         .cache/econflow/a1b2c3…/data.parquet
    """
    from econflow.commands.cache_cmd import run_cache_inspect

    exit_code = run_cache_inspect(key=key, cache_dir=cache_dir, console=console)
    if exit_code != 0:
        raise typer.Exit(code=exit_code)


@cache_app.command("clear")
def cache_clear(
    cache_dir: Path = typer.Option(
        Path(".cache/econflow"),
        "--cache-dir",
        help="Root cache directory.",
        show_default=True,
    ),
    yes: bool = typer.Option(
        False,
        "--yes",
        help="Confirm deletion without prompt.",
    ),
) -> None:
    """Delete all cached datasets.

    Requires --yes to confirm.  This action is irreversible — datasets
    will need to be re-downloaded on the next econflow fetch call.

    Examples:

    \b
        econflow cache clear --yes

        econflow cache clear --cache-dir /data/.cache/econflow --yes

    Common mistakes:

    \b
        * Running without --yes — the command exits immediately without
          deleting anything.  This is intentional.

    Expected output:

    \b
        Deleted 3 cache slot(s) from .cache/econflow/
    """
    from econflow.commands.cache_cmd import run_cache_clear

    exit_code = run_cache_clear(cache_dir=cache_dir, confirm=yes, console=console)
    if exit_code != 0:
        raise typer.Exit(code=exit_code)


@cache_app.command("purge")
def cache_purge(
    key: str = typer.Argument(..., help="Cache key to delete."),
    cache_dir: Path = typer.Option(
        Path(".cache/econflow"),
        "--cache-dir",
        help="Root cache directory.",
        show_default=True,
    ),
) -> None:
    """Delete one cache slot by key.

    Use ``econflow cache list`` to find the key for the slot to delete.

    Examples:

    \b
        econflow cache purge a1b2c3def456

    Expected output:

    \b
        Deleted cache slot: a1b2c3def456
    """
    from econflow.commands.cache_cmd import run_cache_purge

    exit_code = run_cache_purge(key=key, cache_dir=cache_dir, console=console)
    if exit_code != 0:
        raise typer.Exit(code=exit_code)


# ---------------------------------------------------------------------------
# datasets
# ---------------------------------------------------------------------------

@app.command()
def datasets(
    filter_id: str = typer.Option(
        "",
        "--filter", "-f",
        help="Filter connector list by ID substring.",
    ),
) -> None:
    """List all registered data connectors.

    Shows connector ID, label, implementation status, and notes.

    Examples:

    \b
        econflow datasets                # list all connectors
        econflow datasets --filter world # show only connectors matching 'world'

    Common mistakes:

    \b
        * Confusing the connector ID (used with econflow fetch) with the
          connector label (human-readable name shown in this table).
          Fix: use the ID column value with econflow fetch.

    Expected output:

    \b
        EconFlow data connectors (5 registered)

        ID           Label                  Status    Notes
        world_bank   World Bank Open Data   ready     WDI API
        fred         FRED (St. Louis Fed)   ready     requires API key
        oecd         OECD.Stat              ready     SDMX API
        pwt          Penn World Tables      ready     direct download
        csv          Local CSV              ready     path= required
    """
    from econflow.commands.datasets_cmd import run_datasets

    exit_code = run_datasets(filter_str=filter_id, console=console)
    if exit_code != 0:
        raise typer.Exit(code=exit_code)



# ---------------------------------------------------------------------------
# inspect
# ---------------------------------------------------------------------------


@app.command()
def inspect(
    project_dir: Path = typer.Argument(
        Path("."),
        help="EconFlow project directory to inspect.",
        show_default=True,
    ),
    output: Path = typer.Option(
        None,
        "--output", "-o",
        help="Write InspectionReport JSON to this path.",
    ),
    strict: bool = typer.Option(
        False,
        "--strict",
        help="Treat warnings as failures.",
    ),
) -> None:
    """Run pre-flight checks on a project directory.

    Verifies that a project can be reproduced: checks configuration files,
    data file presence and integrity, estimator registration, and installed
    dependencies.

    Examples:

    \b
        econflow inspect .
        econflow inspect examples/my_study/ --strict
        econflow inspect examples/my_study/ --output inspection.json

    Common mistakes:

    \b
        * Using --strict in CI when the project has known warnings — every
          warning becomes a failure.  Reserve --strict for final release
          verification.

        * Running inspect on a directory without a config/ subdirectory —
          it will report missing configuration files rather than erroring out.

    Expected output:

    \b
        EconFlow inspect: examples/my_study/

        Configuration  ✔  config.yaml · models.yaml · outputs.yaml
        Data           ✔  data/processed/panel.csv  (200 rows)
        Estimators     ✔  entity_fe · two_way_fe  (both registered)
        Dependencies   ✔  all required packages present

        ✔ Ready to reproduce  (0 errors, 0 warnings)
    """
    from econflow.commands.inspect import run_inspect

    exit_code = run_inspect(
        project_dir=project_dir,
        output_path=output,
        strict=strict,
        console=console,
    )
    if exit_code != 0:
        raise typer.Exit(code=exit_code)


# ---------------------------------------------------------------------------
# reproduce
# ---------------------------------------------------------------------------


@app.command()
def reproduce(
    project_dir: Path = typer.Argument(
        Path("."),
        help="EconFlow project directory to reproduce.",
        show_default=True,
    ),
    output_dir: Path = typer.Option(
        None,
        "--output-dir", "-o",
        help="Destination for reproduced outputs (default: <project_dir>/replication_outputs/).",
    ),
    skip_inspect: bool = typer.Option(
        False,
        "--skip-inspect",
        help="Skip pre-flight checks.",
    ),
    no_compare: bool = typer.Option(
        False,
        "--no-compare",
        help="Skip output comparison even if original_outputs/ exists.",
    ),
    tolerance: float = typer.Option(
        1e-6,
        "--tolerance",
        help="Absolute tolerance for numeric output comparison.",
    ),
    timeout: int = typer.Option(
        600,
        "--timeout",
        help="Per-step subprocess timeout in seconds.",
    ),
    report_dir: Path = typer.Option(
        None,
        "--report-dir",
        help="Where to write the reproducibility report (default: output-dir).",
    ),
) -> None:
    """Reproduce an EconFlow project from its configuration.

    Runs the full analysis pipeline in an isolated subprocess and optionally
    compares outputs against original_outputs/ if present.  Produces a
    reproducibility report (Markdown + JSON).

    Examples:

    \b
        econflow reproduce .
        econflow reproduce examples/blind_replication/
        econflow reproduce examples/my_study/ --output-dir /tmp/replica/
        econflow reproduce examples/my_study/ --tolerance 1e-4
        econflow reproduce examples/my_study/ --skip-inspect --no-compare

    Common mistakes:

    \b
        * Missing original_outputs/ — if the directory does not exist the
          comparison step is skipped automatically (this is not an error).
          To enable comparison: copy your expected outputs there first.

        * Numeric comparison failures from floating-point platform drift —
          try a looser tolerance: econflow reproduce --tolerance 1e-4.

        * Subprocess timeout on large datasets — increase with --timeout 1200.

    Expected output:

    \b
        EconFlow reproduce: examples/my_study/

        Pre-flight (inspect) … ✔
        Pipeline run …         ✔  (3.2 s)
        Output comparison …    ✔  3/3 files match (tolerance 1e-6)

        ✔ Reproduction successful
        Report: examples/my_study/replication_outputs/report.md
    """
    from econflow.commands.reproduce import run_reproduce

    exit_code = run_reproduce(
        project_dir=project_dir,
        output_dir=output_dir,
        skip_inspect=skip_inspect,
        compare=not no_compare,
        tolerance=tolerance,
        timeout=timeout,
        report_dir=report_dir,
        console=console,
    )
    if exit_code != 0:
        raise typer.Exit(code=exit_code)


# ---------------------------------------------------------------------------
# compare
# ---------------------------------------------------------------------------


@app.command()
def compare(
    baseline_dir: Path = typer.Argument(
        ...,
        help="Directory containing the original (baseline) outputs.",
    ),
    replica_dir: Path = typer.Argument(
        ...,
        help="Directory containing the reproduced outputs.",
    ),
    tolerance: float = typer.Option(
        1e-6,
        "--tolerance",
        help="Absolute tolerance for floating-point comparison.",
    ),
    output: Path = typer.Option(
        None,
        "--output", "-o",
        help="Write ComparisonReport JSON to this path.",
    ),
) -> None:
    """Compare two output directories and report differences.

    Performs toleranced comparison of CSV, LaTeX, and JSON files.  Reports
    per-file status (match / mismatch / missing) and overall pass/fail.

    Examples:

    \b
        econflow compare examples/my_study/original_outputs/ /tmp/replica/tables/
        econflow compare baseline/ replica/ --tolerance 1e-4
        econflow compare baseline/ replica/ --output comparison.json

    Common mistakes:

    \b
        * Comparing directories with different file sets — a missing file
          is reported as "missing", not "match".  Both directories should
          contain the same filenames.

        * Using too tight a tolerance across machines — floating-point
          results differ slightly between OS/BLAS versions.
          Fix: econflow compare --tolerance 1e-4 for cross-platform runs.

    Expected output:

    \b
        EconFlow compare

        baseline/   3 files
        replica/    3 files

        table_fe_investment.csv   ✔  match
        table_fe_investment.tex   ✔  match
        table_ols_results.csv     ✔  match

        ✔ All 3 file(s) match  (tolerance 1e-6)
    """
    from econflow.commands.compare import run_compare

    exit_code = run_compare(
        baseline_dir=baseline_dir,
        replica_dir=replica_dir,
        tolerance=tolerance,
        output_path=output,
        console=console,
    )
    if exit_code != 0:
        raise typer.Exit(code=exit_code)


# ---------------------------------------------------------------------------
# release-check
# ---------------------------------------------------------------------------


@app.command(name="release-check")
def release_check(
    quick: bool = typer.Option(
        False,
        "--quick",
        help=(
            "Skip slow checks: QG-01 (package build), QG-06 (integration tests), "
            "QG-07 (blind replication).  Useful for fast pre-flight verification."
        ),
    ),
    checks: str = typer.Option(
        "",
        "--checks",
        help=(
            "Comma-separated list of check IDs to run, e.g. QG-02,QG-03,QG-05.  "
            "Defaults to all checks."
        ),
    ),
    output: Path = typer.Option(
        None,
        "--output", "-o",
        help="Write a Markdown release report to this path.",
    ),
    json_output: Path = typer.Option(
        None,
        "--json",
        help="Write a machine-readable JSON report to this path.",
    ),
) -> None:
    """Run the EconFlow Release Quality Gate.

    Executes 9 checks and produces a structured release report:

    \b
      QG-01  package_build       Wheel builds from source
      QG-02  package_import      All public sub-packages import cleanly
      QG-03  cli_smoke           --version and doctor both pass
      QG-04  schema_validation   ConfigValidator passes on blind_replication example
      QG-05  plugin_registry     All registries meet minimum thresholds
      QG-06  integration_tests   pytest tests/integration/ exits 0
      QG-07  blind_replication   econflow reproduce examples/blind_replication/
      QG-08  doc_api_examples    Documented import patterns work in-process
      QG-09  api_consistency     Every __all__ entry is importable

    Exit code is 0 when no blockers exist; 1 when one or more checks fail.

    Examples:

        # Full gate (may take several minutes)
        econflow release-check

        # Fast pre-flight (skips build, integration tests, replication)
        econflow release-check --quick

        # Run specific checks only
        econflow release-check --checks QG-02,QG-05,QG-08

        # Save a full report
        econflow release-check --output docs/release/gate_report.md --json gate.json

    Common mistakes:

    \b
        * Running release-check without the package installed in editable
          mode — QG-01 (package build) and QG-02 (imports) may fail.
          Fix: pip install -e ".[dev]" first.

        * Using --quick for a final release gate — --quick skips QG-01
          (build), QG-06 (integration tests), and QG-07 (blind replication),
          which are required for a genuine release pass.

    Expected output (abbreviated):

    \b
        EconFlow Release Quality Gate

          ✔  QG-01  package_build       Wheel built successfully
          ✔  QG-02  package_import      All 12 sub-packages import cleanly
          ✔  QG-03  cli_smoke           --version and doctor pass
          ✔  QG-04  schema_validation   blind_replication config validates
          ✔  QG-05  plugin_registry     8 estimators · 6 diagnostics
          ✔  QG-06  integration_tests   pytest tests/integration/ 0 failures
          ✔  QG-07  blind_replication   reproduce passed (tol 1e-6)
          ✔  QG-08  doc_api_examples    all import patterns work
          ✔  QG-09  api_consistency     all __all__ entries importable

        ✔ Gate passed  (9/9 checks)  — safe to release
    """
    from econflow.commands.release_check import run_release_check

    checks_filter: set[str] | None = None
    if checks:
        checks_filter = {c.strip().upper() for c in checks.split(",") if c.strip()}

    exit_code = run_release_check(
        quick=quick,
        checks_filter=checks_filter,
        output_md=output,
        output_json=json_output,
        console=console,
    )
    if exit_code != 0:
        raise typer.Exit(code=exit_code)


# ---------------------------------------------------------------------------
# docs
# ---------------------------------------------------------------------------


@app.command()
def docs(
    topic: str = typer.Argument(
        "config",
        help="Documentation topic.  Currently only 'config' is supported.",
    ),
    output: Path | None = typer.Option(
        None,
        "--output", "-o",
        help=(
            "Write to this file instead of the default location "
            "(docs/reference/configuration.md)."
        ),
        show_default=False,
    ),
    stdout: bool = typer.Option(
        False,
        "--stdout",
        help="Print to stdout instead of writing a file.",
    ),
    text: bool = typer.Option(
        False,
        "--text",
        help="Use plain-text format instead of Markdown.",
    ),
) -> None:
    """Generate reference documentation from the live Pydantic schema.

    Writes docs/reference/configuration.md (or prints to stdout).

    The generated document lists every configuration option with its type,
    default value, allowed values, description, and examples.

    Examples:

    \b
        econflow docs config

        econflow docs config --text --stdout

        econflow docs config --output path/to/config_reference.md

    Common mistakes:

    \b
        * Passing an unknown topic — only 'config' is currently supported.
          Additional topics (models, outputs) are planned for a future release.

    Expected output:

    \b
        ✓ Written: docs/reference/configuration.md
    """
    if topic != "config":
        console.print(
            f"[red]Unknown topic {topic!r}.  Only 'config' is supported.[/red]"
        )
        raise typer.Exit(code=1)

    from econflow.config.docs import (
        generate_config_reference,
        write_config_reference,
    )

    fmt = "text" if text else "markdown"

    if stdout:
        content = generate_config_reference(format=fmt)
        console.print(content, highlight=False)
        return

    written = write_config_reference(path=output, format=fmt)
    console.print(f"[green]✓[/green] Written: {written}")

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# ``python -m econflow.cli`` entry point
# ---------------------------------------------------------------------------
# Without this guard, `python -m econflow.cli <command>` silently imports
# this module and exits 0 without dispatching to any Typer command — the
# module defines `app` but nothing ever calls it. This is not a hypothetical:
# `econflow.replication.planner._econflow_cmd()` invokes the CLI exactly this
# way (`[sys.executable, "-m", "econflow.cli"]`), specifically so `econflow
# reproduce`'s subprocess steps work even when the `econflow` console-script
# is not on PATH (e.g. on Windows). Without this guard, every subprocess step
# `reproduce` runs (`validate`, `run`) exits 0 having done nothing, and
# `reproduce` reports a false "successful" reproduction.
if __name__ == "__main__":
    app()
