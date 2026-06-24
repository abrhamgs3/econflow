"""
econflow.sensitivity.runner — Sensitivity analysis runner.

Executes multiple model specifications defined in ``models.yaml`` and
collects results for side-by-side comparison.  Supports:

* Varying the AI proxy index construction method.
* Swapping estimators (OLS / FE / RE / IV / GMM).
* Restricting the country/year sample.
* Alternative control variable sets.
* Alternative instrument sets.

Specifications are defined as a list of :class:`SpecificationConfig` dicts
and can be run sequentially or (future) in parallel using ``concurrent.futures``.

Usage (once implemented)
-------------------------
    from econflow.sensitivity.runner import SensitivityRunner
    runner = SensitivityRunner.from_models_yaml("projects/example/models.yaml")
    results = runner.run(panel)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

from econflow.estimation.base import EstimationResult


@dataclass
class SpecificationConfig:
    """
    Configuration for a single model specification in the sensitivity analysis.

    Attributes
    ----------
    name:
        Unique identifier for this specification (used in tables/figures).
    estimator:
        Estimator class name (e.g. ``"TwoWayFE"``, ``"IVEstimator"``).
    dependent:
        Dependent variable column name.
    regressors:
        List of regressor column names.
    extra:
        Estimator-specific keyword arguments (e.g. ``endog``, ``instruments``).
    sample_filter:
        Optional dict of ``{column: value}`` filters to apply to the panel.
    """

    name: str
    estimator: str
    dependent: str
    regressors: list[str]
    extra: dict[str, Any] = field(default_factory=dict)
    sample_filter: dict[str, Any] = field(default_factory=dict)


class SensitivityRunner:
    """
    Runs a battery of specifications and collects :class:`EstimationResult` objects.

    Parameters
    ----------
    specifications:
        Ordered list of :class:`SpecificationConfig` instances.
    """

    def __init__(self, specifications: list[SpecificationConfig]) -> None:
        self.specifications = specifications
        self._results: dict[str, EstimationResult] = {}

    # ------------------------------------------------------------------
    # Construction helpers
    # ------------------------------------------------------------------

    @classmethod
    def from_models_yaml(cls, path: str | Path) -> "SensitivityRunner":
        """
        Parse a ``models.yaml`` file and build a :class:`SensitivityRunner`.
        """
        raise NotImplementedError

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    def run(self, panel: pd.DataFrame) -> dict[str, EstimationResult]:
        """
        Fit all specifications on *panel* and return a mapping of
        ``spec_name → EstimationResult``.
        """
        raise NotImplementedError

    def run_one(self, spec: SpecificationConfig, panel: pd.DataFrame) -> EstimationResult:
        """
        Fit a single :class:`SpecificationConfig` on *panel*.
        """
        raise NotImplementedError
