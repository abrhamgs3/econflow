"""econflow.outputs.renderers.html_renderer — HTML table renderer."""

from __future__ import annotations

import html
from typing import Any

from econflow.outputs.base import BaseRenderer
from econflow.outputs.model import ReportTable
from econflow.outputs.registry import register_renderer


@register_renderer("html", label="HTML", file_extension=".html",
                   notes="Standalone HTML table with inline styles")
class HTMLRenderer(BaseRenderer):
    """
    Render a :class:`ReportTable` as a self-contained HTML snippet.

    Produces a ``<table>`` element with a caption and optional footer.
    The output is a fragment (no ``<html>`` or ``<body>`` wrapper),
    suitable for embedding in a larger HTML document.
    """

    renderer_id = "html"
    name = "HTML"
    file_extension = ".html"

    def render(self, table: ReportTable, **kwargs: Any) -> str:
        e = html.escape
        lines: list[str] = ["<table>"]

        if table.title:
            caption = e(table.title)
            if table.subtitle:
                caption += f"<br><em>{e(table.subtitle)}</em>"
            lines.append(f"  <caption>{caption}</caption>")

        # Header
        lines.append("  <thead>")
        lines.append("    <tr>")
        lines.append("      <th></th>")
        for col in table.columns:
            lines.append(f"      <th>{e(col)}</th>")
        lines.append("    </tr>")
        lines.append("  </thead>")

        lines.append("  <tbody>")
        for row in table.rows:
            if row.row_type == "separator":
                lines.append('    <tr class="separator"><td colspan="'
                             + str(len(table.columns) + 1) + '"></td></tr>')
                continue

            label = f"<strong>{e(row.label)}</strong>" if row.bold else e(row.label)
            if row.italic:
                label = f"<em>{label}</em>"

            lines.append("    <tr>")
            lines.append(f"      <td>{label}</td>")
            for col in table.columns:
                primary = e(row.cells.get(col, ""))
                if row.sub_cells:
                    secondary = e(row.sub_cells.get(col, ""))
                    cell = f"{primary}<br><small>{secondary}</small>" if secondary else primary
                else:
                    cell = primary
                lines.append(f"      <td>{cell}</td>")
            lines.append("    </tr>")

        lines.append("  </tbody>")

        if table.footer or table.notes:
            lines.append("  <tfoot>")
            for note in table.footer:
                lines.append(f'    <tr><td colspan="{len(table.columns) + 1}">'
                             f"<small>{e(note)}</small></td></tr>")
            if table.notes:
                lines.append(f'    <tr><td colspan="{len(table.columns) + 1}">'
                             f"<small>{e(table.notes)}</small></td></tr>")
            lines.append("  </tfoot>")

        lines.append("</table>")
        return "\n".join(lines) + "\n"
