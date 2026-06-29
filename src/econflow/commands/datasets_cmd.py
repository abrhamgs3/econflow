"""
econflow.commands.datasets_cmd — ``econflow datasets`` command implementation.

Lists all registered data connectors with their status, label, and notes.

Usage
-----
::

    econflow datasets                 # list all connectors
    econflow datasets --filter world  # filter by connector ID substring
"""

from __future__ import annotations

from typing import Any


def run_datasets(
    *,
    filter_str: str = "",
    console: Any = None,
) -> int:
    """
    List all registered connectors.

    Parameters
    ----------
    filter_str:
        If non-empty, only show connectors whose ID contains this string.
    console:
        Rich Console instance, or None.

    Returns
    -------
    int
        Exit code (always 0).
    """
    from rich.console import Console
    from rich.table import Table

    # Force connector registration by importing the package
    import econflow.ingestion  # noqa: F401
    from econflow.ingestion.registry import list_connectors

    con = console or Console()
    connectors = list_connectors()

    if filter_str:
        connectors = [c for c in connectors if filter_str.lower() in c["id"].lower()]

    if not connectors:
        msg = (
            f"No connectors matching {filter_str!r}."
            if filter_str
            else "No connectors registered."
        )
        con.print(f"[yellow]{msg}[/yellow]")
        return 0

    tbl = Table(
        title=f"Registered Connectors ({len(connectors)})",
        show_lines=True,
    )
    tbl.add_column("ID", style="bold cyan", no_wrap=True)
    tbl.add_column("Label")
    tbl.add_column("Status", no_wrap=True)
    tbl.add_column("Notes")

    for c in connectors:
        status = c.get("status", "unknown")
        status_color = "green" if status == "implemented" else "yellow"
        tbl.add_row(
            c["id"],
            c.get("label", ""),
            f"[{status_color}]{status}[/{status_color}]",
            c.get("notes", ""),
        )

    con.print(tbl)
    con.print(
        "\n[dim]Use [bold]econflow fetch <connector_id>[/bold] to download a dataset.[/dim]"
    )
    return 0
