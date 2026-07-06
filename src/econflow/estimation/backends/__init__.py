"""
econflow.estimation.backends — Library-specific estimator mixin classes.

Each mixin provides helpers that are specific to one underlying estimation
library.  Concrete estimators inherit from the appropriate mixin *in addition*
to :class:`~econflow.estimation.base.BaseEstimator` so that library-specific
data-preparation utilities are co-located with the library that needs them.

Available mixins
----------------
LinearmodelsMixin
    ``linearmodels`` panel-data estimators (PooledOLS, PanelOLS, etc.).
    Provides ``_to_panel()`` for (entity, time) MultiIndex construction.
StatsmodelsMixin
    ``statsmodels`` estimators. Planned — Milestone 4.
PyfixestMixin
    ``pyfixest`` fixed-effects estimators. Planned — Milestone 4.
DoubleMLMixin
    ``DoubleML`` causal-inference estimators. Planned — Milestone 5.
PyMCMixin
    ``PyMC`` Bayesian estimators. Planned — Milestone 6.

Backward compatibility
-----------------------
``BaseEstimator._to_panel()`` still exists for estimators that were written
before the mixin split.  New estimators should inherit from the appropriate
mixin instead of relying on the base-class helper.
"""

from __future__ import annotations

from econflow.estimation.backends.doubleml import DoubleMLMixin
from econflow.estimation.backends.linearmodels import LinearmodelsMixin
from econflow.estimation.backends.pyfixest import PyfixestMixin
from econflow.estimation.backends.pymc import PyMCMixin
from econflow.estimation.backends.statsmodels import StatsmodelsMixin

__all__ = [
    "LinearmodelsMixin",
    "StatsmodelsMixin",
    "PyfixestMixin",
    "DoubleMLMixin",
    "PyMCMixin",
]
