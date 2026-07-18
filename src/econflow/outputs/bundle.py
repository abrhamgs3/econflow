"""
econflow.outputs.bundle — Publication bundle builder.

A :class:`PublicationBundle` collects :class:`~econflow.outputs.model.ReportTable`
and :class:`~econflow.outputs.model.ReportFigure` objects and renders them into
a structured output directory suitable for submission or archival.

Output layout::

    <output_dir>/
        tables/
            <slug>.csv
            <slug>.tex
            <slug>.md
            <slug>.html
        figures/
            <slug>.json
        diagnostics/
            diagnostics.md
            diagnostics.tex
        manifest.json

The bundle is pure Python — it has no LaTeX compiler or PDF dependency.
"""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from econflow.core.exceptions import RegistryError
from econflow.outputs.model import ReportFigure, ReportTable
from econflow.outputs.registry import get_renderer

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _slugify(text: str) -> str:
    """Return a filesystem-safe slug from *text*."""
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "_", text)
    return text or "table"


# ---------------------------------------------------------------------------
# Bundle entry types
# ---------------------------------------------------------------------------

@dataclass
class TableEntry:
    """Internal record pairing a table with its publication slug and format list.

    Attributes
    ----------
    table : ReportTable
        The table data model to render.
    slug : str
        Unique filename stem used as the base name for all rendered output files
        (e.g. ``"table_fe_results"`` → ``table_fe_results.csv``, ``.tex``, …).
    formats : list[str]
        Renderer IDs to apply.  Defaults to ``["csv", "latex", "markdown", "html"]``.
    """
    table: ReportTable
    slug: str
    formats: list[str] = field(default_factory=lambda: ["csv", "latex", "markdown", "html"])


@dataclass
class FigureEntry:
    """Internal record pairing a figure with its publication slug.

    Attributes
    ----------
    figure : ReportFigure
        The figure data model to render.
    slug : str
        Unique filename stem used as the base name for all rendered figure files.
    """
    figure: ReportFigure
    slug: str


# ---------------------------------------------------------------------------
# PublicationBundle
# ---------------------------------------------------------------------------

class PublicationBundle:
    """
    Collects tables and figures, then renders them into a structured directory.

    Parameters
    ----------
    output_dir:
        Root directory for the bundle.  Created on :meth:`write`.
    table_formats:
        Default list of renderer ids to apply to every table.
    overwrite:
        If ``False`` and *output_dir* already exists, :meth:`write` raises
        :class:`FileExistsError`.
    metadata:
        Arbitrary key-value pairs written into ``manifest.json``.

    Examples
    --------
    >>> bundle = PublicationBundle("outputs/paper")
    >>> bundle.add_table(reg_table)
    >>> bundle.add_table(sumstat_table)
    >>> bundle.add_figure(coef_figure)
    >>> manifest = bundle.write()
    """

    def __init__(
        self,
        output_dir: str | Path,
        *,
        table_formats: list[str] | None = None,
        overwrite: bool = True,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self.output_dir = Path(output_dir)
        self.table_formats = table_formats or ["csv", "latex", "markdown", "html"]
        self.overwrite = overwrite
        self.metadata = metadata or {}

        self._tables: list[TableEntry] = []
        self._table_slugs: set[str] = set()
        self._figures: list[FigureEntry] = []
        self._figure_slugs: set[str] = set()
        self._diagnostics: ReportTable | None = None

    # ------------------------------------------------------------------
    # Add items
    # ------------------------------------------------------------------

    def add_table(
        self,
        table: ReportTable,
        *,
        slug: str | None = None,
        formats: list[str] | None = None,
    ) -> PublicationBundle:
        """
        Add a :class:`ReportTable` to the bundle.

        Parameters
        ----------
        table:
            Table to include.
        slug:
            Filename stem.  Derived from ``table.title`` if omitted.
        formats:
            Renderer ids to apply.  Overrides ``self.table_formats``.

        Returns
        -------
        PublicationBundle
            *self*, for chaining.

        Raises
        ------
        ValueError
            If the resolved slug is already in use.
        """
        resolved_slug = slug or _slugify(table.title)
        if resolved_slug in self._table_slugs:
            raise ValueError(
                f"Duplicate table slug: {resolved_slug!r}. "
                "Provide an explicit slug= to distinguish tables with the same title."
            )
        self._table_slugs.add(resolved_slug)
        self._tables.append(TableEntry(
            table=table,
            slug=resolved_slug,
            formats=formats or self.table_formats,
        ))
        return self

    def add_figure(
        self,
        figure: ReportFigure,
        *,
        slug: str | None = None,
    ) -> PublicationBundle:
        """
        Add a :class:`ReportFigure` to the bundle.

        Figures are serialised as JSON; rendering to image formats is left
        to downstream tools (matplotlib, plotly, vega-cli, etc.).

        Returns
        -------
        PublicationBundle
            *self*, for chaining.

        Raises
        ------
        ValueError
            If the resolved slug is already in use.
        """
        resolved_slug = slug or _slugify(figure.title)
        if resolved_slug in self._figure_slugs:
            raise ValueError(
                f"Duplicate figure slug: {resolved_slug!r}. "
                "Provide an explicit slug= to distinguish figures with the same title."
            )
        self._figure_slugs.add(resolved_slug)
        self._figures.append(FigureEntry(
            figure=figure,
            slug=resolved_slug,
        ))
        return self

    def set_diagnostics(self, table: ReportTable) -> PublicationBundle:
        """
        Set the diagnostics summary table (produced by
        :func:`~econflow.outputs.diagnostics_report.build_diagnostics_report`).

        Returns
        -------
        PublicationBundle
            *self*, for chaining.
        """
        self._diagnostics = table
        return self

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def write(self) -> dict[str, Any]:
        """
        Render all items and write the bundle to ``output_dir``.

        Returns
        -------
        dict
            Manifest dict (also written as ``manifest.json``).

        Raises
        ------
        FileExistsError
            If ``output_dir`` already exists and ``overwrite=False``.
        ValueError
            If any renderer id in the bundle is not registered.  Raised
            before any files are written so no partial output is created.
        """
        if self.output_dir.exists() and not self.overwrite:
            raise FileExistsError(
                f"output_dir already exists: {self.output_dir}. "
                "Pass overwrite=True to allow overwriting."
            )

        # --- Pre-validate all renderer IDs before touching the filesystem ---
        all_formats: set[str] = set()
        for entry in self._tables:
            all_formats.update(entry.formats)
        if self._diagnostics is not None:
            all_formats.update(("markdown", "latex"))
        unknown: list[str] = []
        for fmt in sorted(all_formats):
            try:
                get_renderer(fmt)
            except RegistryError:
                unknown.append(fmt)
        if unknown:
            raise ValueError(
                f"Unknown renderer id(s): {unknown!r}. "
                "Register them with @register_renderer() before calling write()."
            )

        tables_dir = self.output_dir / "tables"
        figures_dir = self.output_dir / "figures"
        diag_dir = self.output_dir / "diagnostics"

        tables_dir.mkdir(parents=True, exist_ok=True)
        figures_dir.mkdir(parents=True, exist_ok=True)
        diag_dir.mkdir(parents=True, exist_ok=True)

        manifest: dict[str, Any] = {
            "econflow_bundle": True,
            "created_utc": datetime.now(tz=timezone.utc).isoformat(),
            "metadata": self.metadata,
            "tables": [],
            "figures": [],
            "diagnostics": None,
        }

        # ---- Tables --------------------------------------------------------
        _renderer_ext = {
            "csv": ".csv", "latex": ".tex", "markdown": ".md",
            "html": ".html", "json": ".json",
        }
        for entry in self._tables:
            files: dict[str, str] = {}
            for fmt in entry.formats:
                renderer_cls = get_renderer(fmt)
                renderer = renderer_cls()
                ext = _renderer_ext.get(fmt, f".{fmt}")
                out_path = tables_dir / f"{entry.slug}{ext}"
                renderer.render_to_file(entry.table, out_path)
                files[fmt] = str(out_path.relative_to(self.output_dir))
            manifest["tables"].append({
                "title": entry.table.title,
                "slug": entry.slug,
                "table_type": entry.table.table_type,
                "files": files,
            })

        # ---- Figures -------------------------------------------------------
        for entry in self._figures:
            out_path = figures_dir / f"{entry.slug}.json"
            out_path.write_text(entry.figure.to_json(indent=2), encoding="utf-8")
            manifest["figures"].append({
                "title": entry.figure.title,
                "slug": entry.slug,
                "figure_type": entry.figure.figure_type,
                "file": str(out_path.relative_to(self.output_dir)),
            })

        # ---- Diagnostics ---------------------------------------------------
        if self._diagnostics is not None:
            diag_files: dict[str, str] = {}
            for fmt in ("markdown", "latex"):
                renderer_cls = get_renderer(fmt)
                renderer = renderer_cls()
                ext = _renderer_ext[fmt]
                out_path = diag_dir / f"diagnostics{ext}"
                renderer.render_to_file(self._diagnostics, out_path)
                diag_files[fmt] = str(out_path.relative_to(self.output_dir))
            manifest["diagnostics"] = {
                "title": self._diagnostics.title,
                "files": diag_files,
            }

        # ---- Manifest ------------------------------------------------------
        manifest_path = self.output_dir / "manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

        return manifest

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        return (
            f"PublicationBundle("
            f"tables={len(self._tables)}, "
            f"figures={len(self._figures)}, "
            f"diagnostics={'yes' if self._diagnostics else 'no'}, "
            f"output_dir={str(self.output_dir)!r})"
        )
