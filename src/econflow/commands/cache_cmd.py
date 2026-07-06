"""
econflow.commands.cache_cmd — ``econflow cache`` command implementation.

Inspect and manage the EconFlow dataset cache.

Subcommands
-----------
* ``econflow cache list``     — list cached datasets
* ``econflow cache inspect <key>`` — show metadata for one cache slot
* ``econflow cache clear``    — delete all cached datasets
* ``econflow cache purge <key>`` — delete one cache slot
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


def run_cache_list(
    *,
    cache_dir: Path,
    console: Any = None,
) -> int:
    """List all cached datasets."""
    from rich.console import Console
    from rich.table import Table

    from econflow.ingestion.cache import CacheManager
    from econflow.ingestion.metadata import DatasetMetadata

    con = console or Console()
    cache = CacheManager(cache_dir)
    keys = cache.list_cached()

    if not keys:
        con.print(f"[yellow]Cache is empty.[/yellow]  (cache_dir: {cache_dir})")
        return 0

    tbl = Table(title=f"Cached Datasets ({len(keys)})", show_lines=True)
    tbl.add_column("Cache Key", style="cyan", no_wrap=True, max_width=16)
    tbl.add_column("Connector", style="bold")
    tbl.add_column("Source")
    tbl.add_column("Downloaded", no_wrap=True)
    tbl.add_column("Rows", justify="right")
    tbl.add_column("SHA-256 (prefix)", no_wrap=True)

    for key in keys:
        try:
            meta_path = cache.meta_path(key)
            meta = DatasetMetadata.from_json(meta_path.read_text(encoding="utf-8"))
            tbl.add_row(
                key[:14] + "…",
                meta.connector_id,
                meta.source[:40],
                meta.download_date[:19],
                str(meta.row_count),
                meta.sha256_hash[:12] + "…" if meta.sha256_hash else "—",
            )
        except Exception as exc:
            tbl.add_row(key[:14] + "…", "?", f"Error: {exc}", "—", "—", "—")

    con.print(tbl)
    return 0


def run_cache_inspect(
    *,
    key: str,
    cache_dir: Path,
    console: Any = None,
) -> int:
    """Show detailed metadata for one cache slot."""
    from rich.console import Console
    from rich.table import Table

    from econflow.ingestion.cache import CacheManager
    from econflow.ingestion.metadata import DatasetMetadata

    con = console or Console()
    cache = CacheManager(cache_dir)

    if not cache.is_cached(key):
        con.print(f"[red]Error:[/red] Cache key {key!r} not found.")
        return 1

    try:
        meta = DatasetMetadata.from_json(
            cache.meta_path(key).read_text(encoding="utf-8")
        )
    except Exception as exc:
        con.print(f"[red]Error reading metadata:[/red] {exc}")
        return 1

    # Verify hash
    try:
        ok = cache.verify_hash(key)
        hash_status = "[green]✓ OK[/green]" if ok else "[yellow]⚠ no hash stored[/yellow]"
    except Exception as exc:
        hash_status = f"[red]✗ CORRUPT: {exc}[/red]"

    tbl = Table(title=f"Cache Slot: {key[:16]}…", show_lines=False)
    tbl.add_column("Field", style="bold cyan", no_wrap=True)
    tbl.add_column("Value")

    tbl.add_row("Cache Key", key)
    tbl.add_row("Data Path", str(cache.data_path(key)))
    tbl.add_row("Connector", meta.connector_id)
    tbl.add_row("Source", meta.source)
    tbl.add_row("Version", meta.version)
    tbl.add_row("Downloaded", meta.download_date)
    tbl.add_row("URL", meta.url)
    tbl.add_row("Rows", str(meta.row_count))
    tbl.add_row("Columns", str(meta.col_count))
    col_names = ", ".join(meta.columns[:10]) + ("…" if len(meta.columns) > 10 else "")
    tbl.add_row("Column Names", col_names)
    tbl.add_row("SHA-256", meta.sha256_hash)
    tbl.add_row("Hash Check", hash_status)
    tbl.add_row("Citation", meta.citation)

    con.print(tbl)

    if meta.params:
        import json
        con.print(f"\n[bold]Parameters:[/bold] {json.dumps(meta.params, indent=2)}")

    return 0


def run_cache_clear(
    *,
    cache_dir: Path,
    confirm: bool = False,
    console: Any = None,
) -> int:
    """Delete all cached datasets."""
    from rich.console import Console

    from econflow.ingestion.cache import CacheManager

    con = console or Console()
    cache = CacheManager(cache_dir)
    keys = cache.list_cached()

    if not keys:
        con.print("[yellow]Cache is already empty.[/yellow]")
        return 0

    if not confirm:
        con.print(
            f"[yellow]This will delete {len(keys)} cached dataset(s) in {cache_dir}.[/yellow]\n"
            f"Re-run with [bold]--yes[/bold] to confirm."
        )
        return 0

    count = cache.clear()
    con.print(f"[green]✓[/green] Deleted {count} cache slot(s).")
    return 0


def run_cache_purge(
    *,
    key: str,
    cache_dir: Path,
    console: Any = None,
) -> int:
    """Delete one cache slot by key."""
    from rich.console import Console

    from econflow.ingestion.cache import CacheManager

    con = console or Console()
    cache = CacheManager(cache_dir)

    if cache.invalidate(key):
        con.print(f"[green]✓[/green] Purged cache slot: {key}")
        return 0
    else:
        con.print(f"[yellow]Cache slot {key!r} not found.[/yellow]")
        return 0
