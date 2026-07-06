"""
econflow.outputs.figures — Figure builder exports.
"""

from econflow.outputs.figures.ci_plot import CIPlot
from econflow.outputs.figures.coefficient_plot import CoefficientPlot
from econflow.outputs.figures.distribution import DistributionFigure
from econflow.outputs.figures.event_study import EventStudyFigure
from econflow.outputs.figures.residual import ResidualFigure
from econflow.outputs.figures.robustness_comparison import RobustnessComparisonFigure

__all__ = [
    "CoefficientPlot",
    "CIPlot",
    "ResidualFigure",
    "DistributionFigure",
    "EventStudyFigure",
    "RobustnessComparisonFigure",
]
