"""
econflow.estimation — Plugin-based estimation framework.

Public API
----------
Protocol (Milestone 3)
~~~~~~~~~~~~~~~~~~~~~~
.. autoclass:: econflow.estimation.protocol.EstimatorProtocol
.. autoclass:: econflow.estimation.protocol.BackendCapabilities

Registry
~~~~~~~~
.. autofunction:: econflow.estimation.registry.register
.. autofunction:: econflow.estimation.registry.get_estimator
.. autofunction:: econflow.estimation.registry.list_estimators
.. autofunction:: econflow.estimation.registry.list_by_backend

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

Pipeline integration (Phase 5C+)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
.. autoclass:: econflow.estimation.dispatcher.PipelineContext
.. autoclass:: econflow.estimation.dispatcher.EstimationDispatcher

EstimationDispatcher is the sole production path for running models via
``econflow run``.  All pipeline model dispatch goes through
``EstimationDispatcher.dispatch()``.
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
from econflow.estimation.backends import (
    DoubleMLMixin,
    LinearmodelsMixin,
    PyfixestMixin,
    PyMCMixin,
    StatsmodelsMixin,
)

# Core abstractions (also re-exports EstimationResult for backward compat)
from econflow.estimation.base import BaseEstimator, EstimatorError, ModelSpecificationError
from econflow.estimation.first_difference import FirstDifference
from econflow.estimation.fixed_effects import EntityFE, TwoWayFE
from econflow.estimation.gmm import SystemGMM
from econflow.estimation.iv import IV2SLS

# Convenience re-exports of concrete classes
from econflow.estimation.ols import PooledOLS
from econflow.estimation.protocol import (
    BACKEND_CUSTOM,
    BACKEND_DOUBLEML,
    BACKEND_LINEARMODELS,
    BACKEND_PYFIXEST,
    BACKEND_PYMC,
    BACKEND_STATSMODELS,
    KNOWN_BACKENDS,
    BackendCapabilities,
    EstimatorProtocol,
)
from econflow.estimation.quantile import PanelQuantile
from econflow.estimation.random_effects import RandomEffects

# Registry
from econflow.estimation.registry import (
    get_estimator,
    list_by_backend,
    list_estimators,
    register,
    register_estimator,
    unregister,
    unregister_estimator,
)

# Result objects
from econflow.estimation.result import DiagnosticResult, EstimationResult

# Pipeline integration — Phase 5C+: EstimationDispatcher is the sole production path
from econflow.estimation.dispatcher import EstimationDispatcher, PipelineContext

__all__ = [
    # Result objects
    "EstimationResult",
    "DiagnosticResult",
    # Abstractions
    "BaseEstimator",
    "EstimatorError",
    "ModelSpecificationError",
    # Protocol (Milestone 3)
    "EstimatorProtocol",
    "BackendCapabilities",
    "BACKEND_LINEARMODELS",
    "BACKEND_STATSMODELS",
    "BACKEND_PYFIXEST",
    "BACKEND_DOUBLEML",
    "BACKEND_PYMC",
    "BACKEND_CUSTOM",
    "KNOWN_BACKENDS",
    # Backend mixins (Milestone 3)
    "LinearmodelsMixin",
    "StatsmodelsMixin",
    "PyfixestMixin",
    "DoubleMLMixin",
    "PyMCMixin",
    # Registry — stable names (register_estimator, unregister_estimator)
    "register_estimator",
    "get_estimator",
    "list_estimators",
    "list_by_backend",
    "unregister_estimator",
    # Deprecated aliases kept for backward compat (will warn in v2.0)
    "register",
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
    # Pipeline integration — Phase 5C+
    "PipelineContext",
    "EstimationDispatcher",
]
