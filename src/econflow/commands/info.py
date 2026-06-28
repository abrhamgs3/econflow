"""
econflow.commands.info — ``econflow info`` command implementation.

Displays a comprehensive summary of the current EconFlow installation and
(when config files are present) the active project configuration.

Sections rendered
-----------------
Platform
    EconFlow version, Python version, install path.

Registered estimators
    All estimators available in the generic pipeline, with implementation
    status (implemented / stub).  Driven by the real estimator registry —
    no hard-coded list.

Registered data connectors
    All data source adapters, with implementation status.  Driven by the
    real connector registry.

Project configuration  (only if --config is resolvable)
    Project name, data file, entity/time dimensions, dependent variable,
    regressors, number of model specifications.

Model specifications  (only if --models is resolvable)
    Table of all models: ID, label, estimator, FE flags, cluster.

Output configuration  (only if --outputs is resolvable)
    Base directory, table formats, comparison table filename.

Provenance status  (only if outputs directory exists)
    Whether run_metadata.json exists and its timestamp.
"""

from __future__ import annotations

import importlib.metadata
import json
import platform
from pathlib import Path

from rich.console import Console
from rich.table import Table

from econflow import __version__
from econflow.commands._shared import deep_get, load_yaml_safe

# ---------------------------------------------------------------------------
# Live registries
# ---------------------------------------------------------------------------
# Both registries are populated at import time by the respective __init__.py
# modules (which trigger @register() / @register_diagnostic() calls).
#
# If either import fails (e.g. optional dependency missing), we degrade
# gracefully to an empty list rather than crashing the whole ``info`` command.

def _load_estimator_registry() -> list[dict]:
    """Return live list from the estimator plugin registry."""
    try:
        import econflow.estimation  # noqa: F401 — triggers @register() calls
        from econflow.estimation.registry import list_estimators
        return list_estimators()
    except Exception:
        return []


def _load_connector_registry() -> list[dict]:
    """Return live list from the connector plugin registry."""
    try:
        import econflow.ingestion  # noqa: F401 — triggers @register() calls
        from econflow.ingestion.registry import list_connectors
        return list_connectors()
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Backward-compatibility alias
# ---------------------------------------------------------------------------
# validate.py (and any external code) does:
#   from econflow.commands.info import ESTIMATOR_REGISTRY
# Keep this name importable; it now reflects the live registry.

ESTIMATOR_REGISTRY: list[dict] = _load_estimator_registry()


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _load_yaml(path: Path) -> dict | None:
    """Load YAML file; return dict or None on any error."""
    data, _ = load_yaml_safe(path)
    return data


# deep_get imported from ._shared
_deep_get = deep_get


def _status_icon(status: str) -> str:
    return {
        "implemented": "[bold green]✔[/bold green]",
        "stub":        "[bold yellow]⚠[/bold yellow]  [dim]stub[/dim]",
        "deprecated":  "[dim]✘ deprecated[/dim]",
    }.get(status, status)


# ---------------------------------------------------------------------------
# Section renderers
# ---------------------------------------------------------------------------

def _render_platform(console: Console) -> None:
    console.rule("[bold]Platform[/bold]")
    console.print()

    # EconFlow version
    console.print(f"  [bold]EconFlow[/bold]   {__version__}")

    # Python
    py_ver = platform.python_version()
    py_impl = platform.python_implementation()
    console.print(f"  [bold]Python[/bold]     {py_impl} {py_ver}")

    # OS
    os_str = f"{platform.system()} {platform.release()} ({platform.machine()})"
    console.print(f"  [bold]Platform[/bold]   {os_str}")

    # Install path
    try:
        dist = importlib.metadata.distribution("econflow")
        loc = dist.locate_file("")
        console.print(f"  [bold]Installed[/bold]  {loc}")
    except Exception:
        console.print("  [bold]Installed[/bold]  [dim](editable install or unknown)[/dim]")

    # Project path (current working directory)
    console.print(f"  [bold]Project[/bold]    {Path.cwd()}")

    console.print()


def _render_estimators(console: Console) -> None:
    console.rule("[bold]Registered estimators[/bold]")
    console.print()

    estimators = _load_estimator_registry()

    if not estimators:
        console.print("  [dim]No estimators registered.[/dim]\n")
        return

    table = Table(show_header=True, header_style="bold", box=None, padding=(0, 2, 0, 0))
    table.add_column("ID",     style="bold cyan", width=12)
    table.add_column("Label",  min_width=36)
    table.add_column("Status", width=20)
    table.add_column("Notes",  style="dim")

    for est in estimators:
        table.add_row(
            est.get("id", ""),
            est.get("label", est.get("id", "")),
            _status_icon(est.get("status", "stub")),
            est.get("notes", ""),
        )

    console.print(table)
    console.print()


def _render_connectors(console: Console) -> None:
    console.rule("[bold]Registered data connectors[/bold]")
    console.print()

    connectors = _load_connector_registry()

    if not connectors:
        console.print("  [dim]No connectors registered.[/dim]\n")
        return

    table = Table(show_header=True, header_style="bold", box=None, padding=(0, 2, 0, 0))
    table.add_column("ID",     style="bold cyan", width=14)
    table.add_column("Label",  min_width=28)
    table.add_column("Status", width=20)
    table.add_column("Notes",  style="dim")

    for conn in connectors:
        table.add_row(
            conn.get("id", ""),
            conn.get("label", conn.get("id", "")),
            _status_icon(conn.get("status", "stub")),
            conn.get("notes", ""),
        )

    console.print(table)
    console.print()


def _render_project_config(cfg: dict, config_path: Path, console: Console) -> None:
    console.rule("[bold]Project configuration[/bold]")
    console.print(f"  [dim]Source:[/dim] {config_path}\n")

    proj = cfg.get("project", {})
    console.print(f"  [bold]Name[/bold]        {proj.get('name', '[dim]not set[/dim]')}")
    console.print(f"  [bold]Description[/bold] {proj.get('description', '[dim]not set[/dim]')}")
    console.print(f"  [bold]Version[/bold]     {proj.get('version', '[dim]not set[/dim]')}")

    data = cfg.get("data", {})
    console.print(f"\n  [bold]Data file[/bold]   {data.get('path', '[dim]not set[/dim]')}")
    console.print(f"  [bold]Entity col[/bold]  {data.get('entity_col', '[dim]not set[/dim]')}")
    console.print(f"  [bold]Time col[/bold]    {data.get('time_col', '[dim]not set[/dim]')}")

    variables = cfg.get("variables", {})
    dep = variables.get("dependent", "[dim]not set[/dim]")
    regs = variables.get("regressors", [])
    console.print(f"\n  [bold]Dependent[/bold]   {dep}")
    if regs:
        console.print(f"  [bold]Regressors[/bold]  {', '.join(str(r) for r in regs)}")
    else:
        console.print("  [bold]Regressors[/bold]  [dim]none defined[/dim]")

    console.print()


def _render_models(models_cfg: dict, models_path: Path, console: Console) -> None:
    console.rule("[bold]Model specifications[/bold]")
    console.print(f"  [dim]Source:[/dim] {models_path}\n")

    specs = models_cfg.get("models", [])
    if not specs:
        console.print("  [dim]No models defined.[/dim]\n")
        return

    table = Table(show_header=True, header_style="bold", box=None, padding=(0, 2, 0, 0))
    table.add_column("#",         style="dim", width=3)
    table.add_column("ID",        style="bold cyan", width=16)
    table.add_column("Label",     width=18)
    table.add_column("Estimator", width=8)
    table.add_column("Entity FE", width=10, justify="center")
    table.add_column("Time FE",   width=8, justify="center")
    table.add_column("Cluster",   width=8)

    for i, spec in enumerate(specs, start=1):
        efe = "[green]Yes[/green]" if spec.get("entity_effects") else "No"
        tfe = "[green]Yes[/green]" if spec.get("time_effects") else "No"
        table.add_row(
            str(i),
            str(spec.get("id", "")),
            str(spec.get("label", "")),
            str(spec.get("estimator", "FE")),
            efe,
            tfe,
            str(spec.get("cluster", "—")),
        )

    console.print(table)
    console.print()


def _render_outputs(out_cfg: dict, outputs_path: Path, console: Console) -> None:
    console.rule("[bold]Output configuration[/bold]")
    console.print(f"  [dim]Source:[/dim] {outputs_path}\n")

    out = out_cfg.get("outputs", {})
    base = out.get("base_dir", "[dim]not set[/dim]")
    console.print(f"  [bold]Base directory[/bold]  {base}")

    tables = out.get("tables", {})
    formats = tables.get("formats", [])
    if formats:
        console.print(f"  [bold]Table formats[/bold]   {', '.join(formats)}")

    ct = tables.get("comparison_table", {})
    filename = ct.get("filename", "[dim]not set[/dim]")
    console.print(f"  [bold]Table filename[/bold]  {filename}")

    console.print()


def _render_provenance(out_cfg: dict, console: Console) -> None:
    console.rule("[bold]Provenance status[/bold]")
    console.print()

    out = out_cfg.get("outputs", {})
    base_dir = out.get("base_dir")
    if not base_dir:
        console.print("  [dim]No output base_dir configured.[/dim]\n")
        return

    prov_file = Path(base_dir) / "provenance" / "run_metadata.json"
    if prov_file.exists():
        try:
            meta = json.loads(prov_file.read_text(encoding="utf-8"))
            run_id   = meta.get("run_id", "unknown")
            ts       = meta.get("timestamp", "unknown")
            version  = meta.get("econflow_version", "unknown")
            models   = meta.get("models_run", [])
            console.print("  [green]✔[/green]  Last run found")
            console.print(f"     Run ID:   {run_id}")
            console.print(f"     Time:     {ts}")
            console.print(f"     Version:  EconFlow {version}")
            console.print(f"     Models:   {', '.join(models) if models else '(none)'}")
        except Exception as exc:
            console.print(
                f"  [yellow]⚠[/yellow]  Provenance file exists but could not be parsed: {exc}"
            )
    else:
        console.print(
            f"  [dim]–[/dim]  No provenance record found at [dim]{prov_file}[/dim].\n"
            "     Run the pipeline to generate one."
        )

    console.print()


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def run_info(
    config_path: Path,
    models_path: Path,
    outputs_path: Path,
    console: Console,
) -> int:
    """
    Display EconFlow project information.

    Parameters
    ----------
    config_path, models_path, outputs_path:
        Paths to the three configuration files.  Sections that depend on a
        file are silently skipped if the file does not exist.
    console:
        Rich console for output.

    Returns
    -------
    int
        Always 0.
    """
    console.print()

    # Platform info is always shown
    _render_platform(console)
    _render_estimators(console)
    _render_connectors(console)

    # Project-specific sections depend on config files
    cfg = _load_yaml(config_path)
    if cfg is not None:
        _render_project_config(cfg, config_path, console)
    else:
        console.print(
            f"  [dim]No config.yaml found at {config_path} — "
            "skipping project-specific sections.[/dim]\n"
        )

    models_cfg = _load_yaml(models_path)
    if models_cfg is not None:
        _render_models(models_cfg, models_path, console)

    out_cfg = _load_yaml(outputs_path)
    if out_cfg is not None:
        _render_outputs(out_cfg, outputs_path, console)
        _render_provenance(out_cfg, console)

    return 0
