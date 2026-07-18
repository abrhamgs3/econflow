"""
econflow.integrity.checks.plugins — Built-in integrity check plugins.

Importing this package registers all built-in checks in the integrity
check registry.  This side-effect import is triggered automatically when
:mod:`econflow.integrity.checks` is imported.
"""

from econflow.integrity.checks.plugins import (
    coefficient_stability,
    pvalue_distribution,
    sample_size,
)

__all__ = [
    "coefficient_stability",
    "pvalue_distribution",
    "sample_size",
]
