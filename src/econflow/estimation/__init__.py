"""
econflow.estimation — Plugin-based estimation framework.

Public API
----------
Registry
~~~~~~~~
.. autofunction:: econflow.estimation.registry.register
.. autofunction:: econflow.estimation.registry.get_estimator
.. autofunction:: econflow.estimation.registry.list_estimators

Core abstractions
~~~~~~~~~~~~~~~~~
.. autoclass:: econflow.estimation.base.BaseEstimator
.. autoclass:: econflow.estimation.base.EstimatorError

Result objects
~~~~~~~~~~~~~~
.. autoclass:: econflow.estimation.result.EstimationResult
.. autoclass:: econflow.estimation.result.DiagnosticResult

Built-in estimators
~~~~~~~~~~~~~~~~~~~
.. autoclass:: econflow.estimation.ols.PooledOLS
.. autoclass:: econflow.estimation.fixed_effects.EntityFE
.. autoclass:: econflow.estimation.fixed_effects.TwoWayFE
.. autoclass:: econflow.estimation.random_effects.RandomEffects
.. autoclass:: econflow.estimation.first_difference.FirstDifference
.. autoclass:: econflow.estimation.iv.IV2SLS
.. autoclass:: econflow.estimation.gmm.SystemGMM
.. autoclass:: econflow.estimation.quantile.PanelQuantile
"""

from __future__ import annotations

import econflow.estimation.first_difference  # noqa: F401
import econflow.estimation.fixed_effects  # noqa: F401
import econflow.estimation.gmm  # noqa: F401
import econflow.estimation.iv  # noqa: F401

# Import all built-in estimators so they self-register via @register().
import econflow.estimation.ols  # noqa: F401
import econflow.estimation.quantile  # noqa: F401
import econflow.estimation.random_effects  # noqa: F401

# Core abstractions (also re-exports EstimationResult for backward compat)
from econflow.estimation.base import BaseEstimator, EstimatorError
from econflow.estimation.first_difference import FirstDifference
from econflow.estimation.fixed_effects import EntityFE, TwoWayFE
from econflow.estimation.gmm import SystemGMM
from econflow.estimation.iv import IV2SLS

# Convenience re-exports of concrete classes
from econflow.estimation.ols import PooledOLS
from econflow.estimation.quantile import PanelQuantile
from econflow.estimation.random_effects import RandomEffects

# Registry
from econflow.estimation.registry import get_estimator, list_estimators, register, unregister

# Result objects
from econflow.estimation.result import DiagnosticResult, EstimationResult

__all__ = [
    # Result objects
    "EstimationResult",
    "DiagnosticResult",
    # Abstractions
    "BaseEstimator",
    "EstimatorError",
    # Registry
    "register",
    "get_estimator",
    "list_estimators",
    "unregister",
    # Concrete estimators
    "PooledOLS",
    "EntityFE",
    "TwoWayFE",
    "RandomEffects",
    "FirstDifference",
    "IV2SLS",
    "SystemGMM",
    "PanelQuantile",
]
