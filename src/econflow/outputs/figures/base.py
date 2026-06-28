"""
econflow.outputs.figures.base — FigureBuilder abstract base class.
"""

from __future__ import annotations

import abc
from typing import Any

from econflow.outputs.model import ReportFigure


class FigureBuilder(abc.ABC):
    """
    Abstract base class for figure builders.

    Subclasses implement :meth:`build` and return a :class:`ReportFigure`
    that is then consumed by a renderer or serialised directly to JSON.
    """

    figure_type: str = "base"
    name: str = "FigureBuilder"

    @abc.abstractmethod
    def build(self, **kwargs: Any) -> ReportFigure:
        """
        Build and return a :class:`ReportFigure`.

        Subclasses receive all inputs as keyword arguments and must
        return a fully populated :class:`ReportFigure`.
        """
        ...
