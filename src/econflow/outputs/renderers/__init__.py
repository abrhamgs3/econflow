"""
econflow.outputs.renderers — Built-in table renderers.

Importing this package registers all five built-in renderers via
``@register_renderer()``.  Third-party renderers register themselves
on import.
"""

from __future__ import annotations

from econflow.outputs.renderers import (  # noqa: F401
    csv_renderer,
    html_renderer,
    json_renderer,
    latex_renderer,
    markdown_renderer,
)
