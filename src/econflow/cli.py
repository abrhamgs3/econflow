"""
Command-line interface for the EconFlow panel econometrics platform.

Entry point: ``econflow`` (registered in pyproject.toml).

Commands
--------
econflow --version
    Print version and exit.

econflow doctor
    Verify environment before running the pipeline.

econflow run [OPTIONS]
    Execute the full analysis pipeline:
    validate → load → econometrics → tables → figures → narratives.

Examples
--------
    $ uv run econflow --version
    EconFlow 0.1.0

    $ uv run econflow doctor
    ✔ Ready

    $ uv run econflow run
    ════════════════════════════════════════
     EconFlow 0.1.0
    ════════════════════════════════════════
    ✔ Validation passed (193 countries, 15 years, 2 895 rows)
    ✔ Robustness suite   (4 models)
    ✔ Sensitivity suite  (4 models)
    ✔ Falsification suite (4 models)
    ✔ Tables written  → tables/
    ✔ Figures written → figures/
    ✔ Narratives written → paper/sections/
    ════════════════════════════════════════
     Pipeline complete in 18.3 s
    ════════════════════════════════════════
"""

from __future__ import annotations

import importlib.metadata
import sys
import time
from pathlib import Path

import typer
from rich.console import Console
from rich.text import Text

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
# Shared helper
# ---------------------------------------------------------------------------

def _check(label: str, ok: bool, detail: str = "") -> bool:
    icon = Text("✔", style="bold green") if ok else Text("✘", style="bold red")
    line = f"  {label}"
    if detail:
        line += f"  ({detail})"
    console.print(icon, line)
    return ok


def _count_rows(path: Path) -> int | None:
    try:
        with path.open(encoding="utf-8") as f:
            return sum(1 for _ in f) - 1
    except Exception:
        return None


# ---------------------------------------------------------------------------
# doctor command
# ---------------------------------------------------------------------------

_REQUIRED_PACKAGES = ["pandas", "numpy", "statsmodels", "linearmodels", "matplotlib", "scipy"]
_DATA_FILES = [
    Path("data/processed/panel_clean.csv"),
    Path("data/raw/wdi.csv"),
    Path("data/raw/pwt.csv"),
    Path("data/raw/ai_proxy.csv"),
]
_OUTPUT_DIRS = [Path("tables"), Path("figures"), Path("outputs")]


@app.command()
def doctor() -> None:
    """Verify that the environment is ready to run the pipeline."""
    console.print("\n[bold]EconFlow — environment check[/bold]\n")

    all_ok = True

    py_version = sys.version.split()[0]
    py_ok = sys.version_info >= (3, 10)
    all_ok &= _check(f"Python {py_version}", py_ok, "" if py_ok else "need ≥ 3.10")

    for pkg in _REQUIRED_PACKAGES:
        try:
            ver = importlib.metadata.version(pkg)
            all_ok &= _check(f"{pkg} {ver}", True)
        except importlib.metadata.PackageNotFoundError:
            all_ok &= _check(pkg, False, "not installed — run: uv pip install -e .")

    console.print()
    console.print("  [dim]Data files[/dim]")
    for path in _DATA_FILES:
        if path.exists():
            rows = _count_rows(path)
            detail = f"{rows:,} rows" if rows is not None else "found"
            all_ok &= _check(str(path), True, detail)
        else:
            all_ok &= _check(str(path), False, "missing — run scripts/01_download_data.py")

    console.print()
    console.print("  [dim]Output directories[/dim]")
    for out_dir in _OUTPUT_DIRS:
        try:
            out_dir.mkdir(parents=True, exist_ok=True)
            all_ok &= _check(str(out_dir) + "/", True, "writable")
        except OSError as exc:
            all_ok &= _check(str(out_dir) + "/", False, str(exc))

    console.print()
    if all_ok:
        console.print("[bold green]✔ Ready[/bold green]\n")
    else:
        console.print("[bold red]✘ Some checks failed.[/bold red]\n")
        raise typer.Exit(code=1)


# ---------------------------------------------------------------------------
# run command
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
            --config  config.yaml \\
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
