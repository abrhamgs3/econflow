"""
econflow.outputs.figures.distribution — Distribution figure builder (stub).

Not yet implemented.  See the module docstring for the planned interface.
"""

from __future__ import annotations

from typing import Any

from econflow.outputs.figures.base import FigureBuilder
from econflow.outputs.model import ReportFigure


class DistributionFigure(FigureBuilder):
    """Distribution figure builder.  Not yet implemented."""

    figure_type = "distribution"
    name = "Distribution"

    def build(self, **kwargs: Any) -> ReportFigure:
        """Not yet implemented."""
        raise NotImplementedError(
            "DistributionFigure.build is not yet implemented."
        )
