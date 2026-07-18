"""econflow.outputs.renderers.markdown_renderer — GitHub-flavoured Markdown renderer."""

from __future__ import annotations

from typing import Any

from econflow.outputs.base import BaseRenderer
from econflow.outputs.model import ReportTable
from econflow.outputs.registry import register_renderer


@register_renderer("markdown", label="Markdown", file_extension=".md",
                   notes="GitHub-flavoured Markdown table")
class MarkdownRenderer(BaseRenderer):
    """
    Render a :class:`ReportTable` as a GitHub-flavoured Markdown table.

    Sub-cells appear in the same cell, separated by a ``<br>`` tag.
    """

    renderer_id = "markdown"
    name = "Markdown"
    file_extension = ".md"

    def render(self, table: ReportTable, **kwargs: Any) -> str:
        lines: list[str] = []

        if table.title:
            lines.append(f"## {table.title}")
            if table.subtitle:
                lines.append(f"*{table.subtitle}*")
            lines.append("")

        # Header
        header = [""] + table.columns
        lines.append("| " + " | ".join(header) + " |")
        lines.append("| " + " | ".join(["---"] * len(header)) + " |")

        for row in table.rows:
            if row.row_type == "separator":
                lines.append("| " + " | ".join(["---"] * len(header)) + " |")
                continue

            cells: list[str] = []
            for col in table.columns:
                primary = row.cells.get(col, "")
                if row.sub_cells:
                    secondary = row.sub_cells.get(col, "")
                    cell = f"{primary}<br>{secondary}" if secondary else primary
                else:
                    cell = primary
                cells.append(cell)

            label = f"**{row.label}**" if row.bold else row.label
            lines.append("| " + " | ".join([label] + cells) + " |")

        if table.footer or table.notes:
            lines.append("")
            for note in table.footer:
                lines.append(f"*{note}*")
            if table.notes:
                lines.append(f"*{table.notes}*")

        return "\n".join(lines) + "\n"
