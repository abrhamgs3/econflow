"""econflow.outputs.renderers.json_renderer — JSON table renderer."""

from __future__ import annotations

from typing import Any

from econflow.outputs.base import BaseRenderer
from econflow.outputs.model import ReportTable
from econflow.outputs.registry import register_renderer


@register_renderer("json", label="JSON", file_extension=".json",
                   notes="Full table object serialised to JSON")
class JSONRenderer(BaseRenderer):
    """
    Render a :class:`ReportTable` as a JSON document.

    The output is the full :meth:`ReportTable.to_dict` serialisation,
    suitable for programmatic consumption.
    """

    renderer_id = "json"
    name = "JSON"
    file_extension = ".json"

    def render(self, table: ReportTable, *, indent: int = 2, **kwargs: Any) -> str:
        return table.to_json(indent=indent)
