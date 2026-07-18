"""econflow.outputs.renderers.csv_renderer — CSV table renderer."""

from __future__ import annotations

import csv
import io
from typing import Any

from econflow.outputs.base import BaseRenderer
from econflow.outputs.model import ReportTable
from econflow.outputs.registry import register_renderer


@register_renderer("csv", label="CSV", file_extension=".csv",
                   notes="Comma-separated values; one row per table row")
class CSVRenderer(BaseRenderer):
    """
    Render a :class:`ReportTable` as comma-separated values.

    The rendered output has a header row followed by one data row per
    :class:`TableRow`.  Sub-cells (e.g. standard errors) appear on a
    separate row with an empty label.  Separator rows are omitted.
    """

    renderer_id = "csv"
    name = "CSV"
    file_extension = ".csv"

    def render(self, table: ReportTable, **kwargs: Any) -> str:
        buf = io.StringIO()
        writer = csv.writer(buf, lineterminator="\n")

        # Header
        writer.writerow([""] + table.columns)

        for row in table.rows:
            if row.row_type == "separator":
                continue
            cells = [row.cells.get(col, "") for col in table.columns]
            writer.writerow([row.label] + cells)
            if row.sub_cells:
                sub = [row.sub_cells.get(col, "") for col in table.columns]
                writer.writerow([""] + sub)

        # Footer
        for note in table.footer:
            writer.writerow([note])
        if table.notes:
            writer.writerow([table.notes])

        return buf.getvalue()
