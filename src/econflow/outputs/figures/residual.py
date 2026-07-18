"""
econflow.outputs.figures.residual — Residual figure builder (stub).

Not yet implemented.  See the module docstring for the planned interface.
"""

from __future__ import annotations

from typing import Any

from econflow.outputs.figures.base import FigureBuilder
from econflow.outputs.model import ReportFigure


class ResidualFigure(FigureBuilder):
    """Residual figure builder.  Not yet implemented."""

    figure_type = "residual"
    name = "Residual"

    def build(self, **kwargs: Any) -> ReportFigure:
        """Not yet implemented."""
        raise NotImplementedError(
            "ResidualFigure.build is not yet implemented."
        )
