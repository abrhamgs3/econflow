"""
econflow.outputs.figures.event_study — Event Study figure builder (stub).

Not yet implemented.  See the module docstring for the planned interface.
"""

from __future__ import annotations

from typing import Any

from econflow.outputs.figures.base import FigureBuilder
from econflow.outputs.model import ReportFigure


class EventStudyFigure(FigureBuilder):
    """Event Study figure builder.  Not yet implemented."""

    figure_type = "event_study"
    name = "Event Study"

    def build(self, **kwargs: Any) -> ReportFigure:
        """Not yet implemented."""
        raise NotImplementedError(
            "Event StudyFigure.build is not yet implemented."
        )
