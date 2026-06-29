"""
econflow.outputs.model — Standard table and figure model objects.

Every table builder produces a :class:`ReportTable`.
Every renderer consumes a :class:`ReportTable`.
The two sides are decoupled: renderers do not know which builder produced the
table, and builders do not know which renderer will consume it.

Similarly, every figure builder produces a :class:`ReportFigure`, which
carries enough data for any figure renderer to materialise the plot.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

# ---------------------------------------------------------------------------
# Table model
# ---------------------------------------------------------------------------

@dataclass
class TableRow:
    """
    A single row in a :class:`ReportTable`.

    Parameters
    ----------
    label:
        Row header displayed in the leftmost column.
    cells:
        Mapping of column name to pre-formatted string value.
        Renderers display these strings verbatim.
    sub_cells:
        Optional secondary row (e.g. standard errors in parentheses).
        Displayed directly below the primary cells with an empty label.
    row_type:
        Semantic type — controls renderer formatting:
        ``"data"`` (default), ``"separator"``, ``"stats"``, ``"header"``.
    bold:
        Whether the row label is rendered in bold.
    italic:
        Whether the row label is rendered in italic.
    """

    label: str
    cells: dict[str, str] = field(default_factory=dict)
    sub_cells: dict[str, str] | None = None
    row_type: str = "data"
    bold: bool = False
    italic: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "cells": self.cells,
            "sub_cells": self.sub_cells,
            "row_type": self.row_type,
            "bold": self.bold,
            "italic": self.italic,
        }


@dataclass
class ReportTable:
    """
    Standard table model consumed by all renderers.

    All content is pre-formatted by the builder.  Renderers handle only
    structural formatting (alignment, borders, LaTeX environments, etc.).

    Parameters
    ----------
    title:
        Table title (used as caption in LaTeX, heading in Markdown/HTML).
    table_type:
        Semantic type: ``"regression"``, ``"summary_stats"``,
        ``"correlation"``, ``"balance"``, ``"robustness"``,
        ``"sensitivity"``, ``"falsification"``, ``"heterogeneity"``.
    columns:
        Ordered list of column header strings (excluding the row-label
        column).
    rows:
        Ordered list of :class:`TableRow` objects.
    footer:
        List of footnote strings appended below the table body.
    subtitle:
        Optional subtitle displayed below the title.
    notes:
        Free-text methodological note appended after the footer.
    metadata:
        Arbitrary key-value pairs for provenance and downstream use.
    """

    title: str
    table_type: str
    columns: list[str]
    rows: list[TableRow] = field(default_factory=list)
    footer: list[str] = field(default_factory=list)
    subtitle: str = ""
    notes: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    # ------------------------------------------------------------------
    # Convenience
    # ------------------------------------------------------------------

    def add_row(self, row: TableRow) -> None:
        self.rows.append(row)

    def add_separator(self) -> None:
        self.rows.append(TableRow(label="", row_type="separator"))

    def n_data_rows(self) -> int:
        return sum(1 for r in self.rows if r.row_type == "data")

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "table_type": self.table_type,
            "columns": self.columns,
            "rows": [r.to_dict() for r in self.rows],
            "footer": self.footer,
            "subtitle": self.subtitle,
            "notes": self.notes,
            "metadata": self.metadata,
        }

    def to_json(self, *, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, default=str)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ReportTable:
        rows = [
            TableRow(
                label=r.get("label", ""),
                cells=dict(r.get("cells", {})),
                sub_cells=dict(r["sub_cells"]) if r.get("sub_cells") is not None else None,
                row_type=r.get("row_type", "data"),
                bold=bool(r.get("bold", False)),
                italic=bool(r.get("italic", False)),
            )
            for r in data.get("rows", [])
        ]
        return cls(
            title=data["title"],
            table_type=data["table_type"],
            columns=data["columns"],
            rows=rows,
            footer=data.get("footer", []),
            subtitle=data.get("subtitle", ""),
            notes=data.get("notes", ""),
            metadata=data.get("metadata", {}),
        )

    def __repr__(self) -> str:
        return (
            f"<ReportTable type={self.table_type!r} "
            f"cols={len(self.columns)} rows={len(self.rows)}>"
        )


# ---------------------------------------------------------------------------
# Figure model
# ---------------------------------------------------------------------------

@dataclass
class ReportFigure:
    """
    Standard figure model produced by figure builders.

    The ``data`` payload carries everything a renderer needs to materialise
    the figure.  Its schema is defined per ``figure_type``.

    Parameters
    ----------
    title:
        Figure title / caption.
    figure_type:
        Semantic type: ``"coefficient_plot"``, ``"ci_plot"``,
        ``"residual"``, ``"distribution"``, ``"event_study"``,
        ``"prediction"``, ``"robustness_comparison"``.
    data:
        Figure data payload (schema depends on ``figure_type``).
    config:
        Rendering configuration (colours, DPI, size, etc.).
    metadata:
        Arbitrary key-value pairs for provenance.
    """

    title: str
    figure_type: str
    data: dict[str, Any] = field(default_factory=dict)
    config: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "figure_type": self.figure_type,
            "data": self.data,
            "config": self.config,
            "metadata": self.metadata,
        }

    def to_json(self, *, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, default=str)

    def __repr__(self) -> str:
        return f"<ReportFigure type={self.figure_type!r} title={self.title!r}>"
