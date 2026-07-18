"""
econflow.outputs — Research output engine.

Public API
----------
Model objects::

    from econflow.outputs import ReportTable, ReportFigure, TableRow

Renderer registry and errors::

    from econflow.outputs import get_renderer, list_renderers, register_renderer, RendererError

Table builders::

    from econflow.outputs import (
        build_regression_table,
        build_summary_stats_table,
        build_balance_table,
        build_correlation_table,
        build_robustness_table,
        build_sensitivity_table,
        build_falsification_table,
        build_heterogeneity_table,
    )

Figure builders::

    from econflow.outputs import CoefficientPlot, CIPlot, FigureBuilder

Plugin base classes::

    from econflow.outputs import BaseRenderer, FigureBuilder

Diagnostics & bundling::

    from econflow.outputs import build_diagnostics_report, PublicationBundle
"""

# --- Renderer registry (triggers side-effect imports) -----------------------
import econflow.outputs.renderers  # noqa: F401  — registers all renderers

# --- Base classes and errors ------------------------------------------------
from econflow.outputs.base import BaseRenderer, RendererError

# --- Diagnostics + bundle ---------------------------------------------------
from econflow.outputs.bundle import PublicationBundle
from econflow.outputs.diagnostics_report import build_diagnostics_report

# --- Figure builders --------------------------------------------------------
from econflow.outputs.figures import CIPlot, CoefficientPlot
from econflow.outputs.figures.base import FigureBuilder
from econflow.outputs.model import ReportFigure, ReportTable, TableRow
from econflow.outputs.registry import (
    get_renderer,
    list_renderers,
    register_renderer,
    unregister_renderer,
)

# --- Table builders ---------------------------------------------------------
from econflow.outputs.tables import (
    build_balance_table,
    build_correlation_table,
    build_falsification_table,
    build_heterogeneity_table,
    build_regression_table,
    build_robustness_table,
    build_sensitivity_table,
    build_summary_stats_table,
)

__all__ = [
    # model
    "ReportTable",
    "ReportFigure",
    "TableRow",
    # base classes
    "BaseRenderer",
    "FigureBuilder",
    # errors
    "RendererError",
    # registry
    "get_renderer",
    "list_renderers",
    "register_renderer",
    "unregister_renderer",
    # table builders
    "build_regression_table",
    "build_summary_stats_table",
    "build_balance_table",
    "build_correlation_table",
    "build_robustness_table",
    "build_sensitivity_table",
    "build_falsification_table",
    "build_heterogeneity_table",
    # figure builders
    "CoefficientPlot",
    "CIPlot",
    # diagnostics + bundle
    "build_diagnostics_report",
    "PublicationBundle",
]
