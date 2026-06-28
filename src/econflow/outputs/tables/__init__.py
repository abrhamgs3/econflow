"""
econflow.outputs.tables — Table builder registry.

Import all builders so callers can do::

    from econflow.outputs.tables import build_regression_table
    from econflow.outputs.tables import build_summary_stats_table
"""

from econflow.outputs.tables.balance import build_balance_table
from econflow.outputs.tables.correlation import build_correlation_table
from econflow.outputs.tables.falsification import build_falsification_table
from econflow.outputs.tables.heterogeneity import build_heterogeneity_table
from econflow.outputs.tables.regression import build_regression_table
from econflow.outputs.tables.robustness import build_robustness_table
from econflow.outputs.tables.sensitivity import build_sensitivity_table
from econflow.outputs.tables.summary_stats import build_summary_stats_table

__all__ = [
    "build_regression_table",
    "build_summary_stats_table",
    "build_balance_table",
    "build_correlation_table",
    "build_robustness_table",
    "build_sensitivity_table",
    "build_falsification_table",
    "build_heterogeneity_table",
]
