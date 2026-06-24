"""
econflow.diagnostics.serial — Arellano-Bond AR tests for serial correlation.

Tests for first- and second-order serial correlation in the first-differenced
residuals of a dynamic panel GMM model (Arellano & Bond, 1991).

* **AR(1)**: expected to reject (serially correlated differences given
  levels MA(0) errors is consistent with the model).
* **AR(2)**: should NOT reject; rejection implies the error process in levels
  has MA(1) or higher structure, invalidating the standard GMM instruments.

Usage (once implemented)
-------------------------
    from econflow.diagnostics.serial import arellano_bond_test
    ab = arellano_bond_test(gmm_result, panel, order=2)
    print(ab.ar1.pvalue, ab.ar2.pvalue)
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from econflow.estimation.base import EstimationResult


@dataclass
class ARTestResult:
    """Single-order Arellano-Bond serial correlation test result."""

    order: int
    statistic: float
    pvalue: float
    conclusion: str  # e.g. "AR(2) not rejected — instruments likely valid"


@dataclass
class ArellanoAbondResult:
    """Combined AR(1) and AR(2) test output."""

    ar1: ARTestResult
    ar2: ARTestResult


def arellano_bond_test(
    result: EstimationResult,
    df: pd.DataFrame,
    entity_col: str = "iso3",
    time_col: str = "year",
    order: int = 2,
) -> ArellanoAbondResult:
    """
    Compute Arellano-Bond AR tests up to *order* from a GMM result.

    Parameters
    ----------
    result:
        :class:`~econflow.estimation.base.EstimationResult` from
        :class:`~econflow.estimation.gmm.GMMEstimator`.
    df:
        The panel DataFrame used for estimation (needed to recover residuals).
    entity_col / time_col:
        Panel dimension identifiers.
    order:
        Maximum order to test (1 or 2).

    Returns
    -------
    ArellanoAbondResult
        AR(1) and AR(2) test statistics and p-values.
    """
    raise NotImplementedError
