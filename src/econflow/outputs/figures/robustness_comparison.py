"""
econflow.outputs.figures.robustness_comparison — Robustness Comparison figure builder (stub).

Not yet implemented.  See the module docstring for the planned interface.
"""

from __future__ import annotations

from typing import Any

from econflow.outputs.figures.base import FigureBuilder
from econflow.outputs.model import ReportFigure


class RobustnessComparisonFigure(FigureBuilder):
    """Robustness Comparison figure builder.  Not yet implemented."""

    figure_type = "robustness_comparison"
    name = "Robustness Comparison"

    def build(self, **kwargs: Any) -> ReportFigure:
        """Not yet implemented."""
        raise NotImplementedError(
            "Robustness ComparisonFigure.build is not yet implemented."
        )
