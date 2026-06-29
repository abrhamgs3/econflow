"""
econflow.commands.fetch_cmd — ``econflow fetch`` command implementation.

Downloads a dataset using a registered connector and optionally runs
validation and records a manifest entry.

Usage (CLI)
-----------
::

    econflow fetch world_bank --param indicators=IT.NET.USER.ZS --param year_start=2000
    econflow fetch csv --param path=data/panel.csv
    econflow fetch fred --param series_ids=GDPPC,UNRATE --param start_date=2000-01-01

"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _parse_param_value(value: str) -> Any:
    """
    Attempt to parse a CLI param value into a typed Python object.

    Handles:
    * JSON arrays: ``[1,2,3]`` or ``["a","b"]``
    * Comma-separated strings treated as lists if value contains no spaces: ``a,b,c``
    * Integers
    * Floats
    * Booleans
    * Plain strings
    """
    # Try JSON first
    try:
        return json.loads(value)
    except (json.JSONDecodeError, ValueError):
        pass
    # Comma-separated → list of strings
    if "," in value and " " not in value:
        return [v.strip() for v in value.split(",")]
    # Integer
    try:
        return int(value)
    except ValueError:
        pass
    # Float
    try:
        return float(value)
    except ValueError:
        pass
    # Boolean
    if value.lower() == "true":
        return True
    if value.lower() == "false":
        return False
    return value


def run_fetch(
    *,
    connector_id: str,
    params: dict[str, Any],
    cache_dir: Path,
    force: bool = False,
    no_validate: bool = False,
    output_manifest: Path | None = None,
    project: str = "",
    console: Any = None,
) -> int:
    """
    Download a dataset using the named connector.

    Parameters
    ----------
    connector_id:
        Registry key (e.g. ``"world_bank"``, ``"csv"``, ``"fred"``).
    params:
        Connector parameters dict (parsed from CLI ``--param`` options).
    cache_dir:
        Root directory for the cache.
    force:
        If True, re-download even if cached.
    no_validate:
        If True, skip validation after download.
    output_manifest:
        If set, write / append a manifest entry to this JSON file.
    project:
        Project name for manifest.
    console:
        Rich Console instance, or None to use plain print.

    Returns
    -------
    int
        0 on success, 1 on error.
    """
    from rich.console import Console
    from rich.table import Table

    from econflow.ingestion.cache import CacheManager
    from econflow.ingestion.manifest import DatasetManifest
    from econflow.ingestion.registry import get_connector

    con = console or Console()

    # Resolve connector
    try:
        ConnClass = get_connector(connector_id)
    except KeyError as exc:
        con.print(f"[red]Error:[/red] {exc}")
        return 1

    cache = CacheManager(cache_dir)
    connector = ConnClass(params=params, cache_manager=cache)

    # Connect
    con.print(f"[cyan]Connecting to[/cyan] [bold]{connector_id}[/bold]…")
    try:
        connector.connect()
    except Exception as exc:
        con.print(f"[red]Connection failed:[/red] {exc}")
        return 1

    # Download
    con.print(f"[cyan]Downloading[/cyan] (force={force})…")
    try:
        path = connector.download(force=force)
    except Exception as exc:
        con.print(f"[red]Download failed:[/red] {exc}")
        return 1

    con.print(f"[green]✓[/green] Cached at: {path}")

    # Validate
    validation_passed = True
    n_errors = 0
    n_warnings = 0
    if not no_validate:
        try:
            report = connector.validate(path)
            n_errors = report.n_errors
            n_warnings = report.n_warnings
            validation_passed = not report.has_errors
            status_color = "green" if not report.has_errors else "red"
            status = "PASS" if not report.has_errors else "FAIL"
            con.print(
                f"[{status_color}]Validation {status}[/{status_color}] "
                f"— {n_errors} error(s), {n_warnings} warning(s)"
            )
            if report.issues:
                tbl = Table(title="Validation Issues", show_lines=False)
                tbl.add_column("Code", style="cyan", no_wrap=True)
                tbl.add_column("Level", no_wrap=True)
                tbl.add_column("Message")
                for issue in report.issues[:20]:
                    lvl_color = "red" if issue.level == "error" else "yellow"
                    tbl.add_row(
                        issue.code,
                        f"[{lvl_color}]{issue.level}[/{lvl_color}]",
                        issue.message,
                    )
                con.print(tbl)
        except Exception as exc:
            con.print(f"[yellow]Warning:[/yellow] Validation failed: {exc}")

    # Metadata summary
    try:
        meta = connector.metadata()
        tbl = Table(title="Dataset Metadata", show_lines=False)
        tbl.add_column("Field", style="bold cyan")
        tbl.add_column("Value")
        tbl.add_row("Source", meta.source)
        tbl.add_row("Version", meta.version)
        tbl.add_row("Rows", str(meta.row_count))
        tbl.add_row("Columns", str(meta.col_count))
        tbl.add_row("SHA-256", meta.sha256_hash[:16] + "…" if meta.sha256_hash else "—")
        tbl.add_row("Downloaded", meta.download_date)
        cit_str = meta.citation[:80] + "…" if len(meta.citation) > 80 else meta.citation
        tbl.add_row("Citation", cit_str)
        con.print(tbl)
    except Exception:
        meta = None

    # Manifest
    if output_manifest is not None and meta is not None:
        try:
            if output_manifest.exists():
                manifest = DatasetManifest.load(output_manifest)
            else:
                manifest = DatasetManifest(project=project)
            manifest.add_entry(
                connector_id=connector_id,
                cache_key=connector.cache_key(),
                params=params,
                metadata=meta,
                validation_passed=validation_passed,
                validation_errors=n_errors,
                validation_warnings=n_warnings,
                citation=connector.citation(),
                dataset_version=connector.version(),
            )
            manifest.save(output_manifest)
            con.print(f"[green]✓[/green] Manifest updated: {output_manifest}")
        except Exception as exc:
            con.print(f"[yellow]Warning:[/yellow] Could not update manifest: {exc}")

    return 0 if validation_passed else 1
