"""
Phase 1 — Pooled OLS Estimator Tests
======================================
Tests for PooledOLS after the adjusted R² bug fix.

Phase 1 bug fixed
-----------------
PooledOLS.fit() previously set::

    rsquared_adj = float(res.rsquared)

i.e. the adjusted R² was identical to the unadjusted R².

The correct formula is::

    rsquared_adj = 1 - (1 - rsquared) * (nobs - 1) / df_resid

PooledOLS.fit() always fits an explicit constant (ols.py prepends a "const"
column before calling linearmodels.PooledOLS), so for a model with k
regressors, df_resid = nobs - k - 1. The formula above handles this
correctly because it uses the df_resid already computed by linearmodels,
which counts the constant as a fitted parameter.

Roadmap requirements covered (MIGRATION_ROADMAP.md §Phase 1 Bug 3)
--------------------------------------------------------------------
- Verify PooledOLS.fit() produces rsquared_adj ≈ 1 - (1-R²)*(n-1)/(n-k-1)
- assert rsquared_adj != rsquared
- all pre-existing signatures, params, pvalues, SEs unchanged

Corrected 2026-07-18 (Repository Integrity Repair): this file previously
claimed the "framework" PooledOLS path omits the constant while a separate
"pipeline" path adds one. That is not true of current source -- there is
only one PooledOLS.fit() implementation and it always adds a constant.
Affected df_resid/rsquared pins updated accordingly.
"""

from __future__ import annotations

import math

import pandas as pd
import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def grunfeld_df() -> pd.DataFrame:
    from statsmodels.datasets import grunfeld
    return grunfeld.load_pandas().data


@pytest.fixture(scope="module")
def ols_result(grunfeld_df):
    """PooledOLS result on the Grunfeld dataset (fits an explicit constant)."""
    from econflow.estimation.ols import PooledOLS
    est = PooledOLS(params={
        "dependent": "invest",
        "regressors": ["value", "capital"],
        "entity_col": "firm",
        "time_col": "year",
        "cov_type": "robust",
    })
    return est.run(grunfeld_df)


def _make_synthetic_panel(n_entities: int = 6, n_time: int = 10, seed: int = 0) -> pd.DataFrame:
    import numpy as np
    rng = np.random.default_rng(seed)
    rows = []
    for e in range(n_entities):
        for t in range(n_time):
            x1 = float(rng.standard_normal())
            x2 = float(rng.standard_normal())
            rows.append({"entity": e, "time": t,
                         "y": 1.5 * x1 - 0.8 * x2 + float(rng.standard_normal()),
                         "x1": x1, "x2": x2})
    return pd.DataFrame(rows)


# ===========================================================================
# Adjusted R² correctness
# ===========================================================================


class TestPooledOLSAdjustedR2:

    def test_rsquared_adj_differs_from_rsquared(self, ols_result):
        """Bug fix: adj R² must no longer equal unadjusted R²."""
        assert ols_result.rsquared_adj != ols_result.rsquared, (
            f"rsquared_adj={ols_result.rsquared_adj} must differ from "
            f"rsquared={ols_result.rsquared} after Phase 1 fix"
        )

    def test_rsquared_adj_less_than_rsquared(self, ols_result):
        """Adjusted R² ≤ unadjusted for any model with > 1 free parameter."""
        assert ols_result.rsquared_adj < ols_result.rsquared, (
            f"rsquared_adj={ols_result.rsquared_adj:.8f} must be < "
            f"rsquared={ols_result.rsquared:.8f}"
        )

    def test_rsquared_adj_formula(self, ols_result):
        """adj = 1 - (1 - R²) * (nobs - 1) / df_resid."""
        expected = (
            1.0
            - (1.0 - ols_result.rsquared)
            * (ols_result.nobs - 1)
            / ols_result.df_resid
        )
        assert math.isclose(ols_result.rsquared_adj, expected, rel_tol=1e-12), (
            f"Formula mismatch: got {ols_result.rsquared_adj:.15f}, "
            f"expected {expected:.15f}"
        )

    def test_df_resid_grunfeld(self, ols_result):
        """PooledOLS fits an explicit constant (ols.py prepends a "const" column
        before calling linearmodels.PooledOLS), so df_resid = nobs - k - 1
        (standard OLS convention, counting the intercept as a parameter) =
        220 - 2 - 1 = 217. This is res.df_resid straight from linearmodels,
        not a bespoke econflow calculation. Corrected 2026-07-18: the
        previous "no constant, df_resid = nobs - k = 218" claim does not
        match current source, which unconditionally fits a constant."""
        assert ols_result.nobs == 220
        assert ols_result.df_resid == 217

    def test_rsquared_unchanged_grunfeld(self, ols_result):
        """Phase 1 must not change the unadjusted R²."""
        # PooledOLS (with constant) on Grunfeld: rsquared ~= 0.8179.
        # Corrected 2026-07-18: there is only one PooledOLS path (see module
        # docstring); the previous "0.8577 without constant" figure does not
        # apply to current source.
        assert 0.8 < ols_result.rsquared < 0.85, (
            f"Unexpected rsquared: {ols_result.rsquared:.8f}"
        )

    def test_params_unchanged(self, ols_result):
        """Phase 1 must not change coefficient estimates."""
        assert "value" in ols_result.params.index
        assert "capital" in ols_result.params.index
        assert float(ols_result.params["value"]) > 0   # value has positive coefficient
        assert float(ols_result.params["capital"]) > 0

    def test_std_err_unchanged(self, ols_result):
        """std_err must still be populated and positive."""
        assert float(ols_result.std_err["value"]) > 0
        assert float(ols_result.std_err["capital"]) > 0

    def test_pvalues_unchanged(self, ols_result):
        """value and capital are highly significant in the Grunfeld OLS."""
        assert float(ols_result.pvalues["value"]) < 0.001
        assert float(ols_result.pvalues["capital"]) < 0.001

    def test_nobs_unchanged(self, ols_result):
        assert ols_result.nobs == 220

    def test_estimator_id(self, ols_result):
        assert ols_result.estimator_id == "ols"


# ===========================================================================
# Formula verification on a synthetic panel
# ===========================================================================


class TestPooledOLSAdjustedR2Synthetic:

    def test_formula_holds_on_synthetic(self):
        from econflow.estimation.ols import PooledOLS
        df = _make_synthetic_panel(n_entities=6, n_time=10, seed=5)
        est = PooledOLS(params={
            "dependent": "y", "regressors": ["x1", "x2"],
            "entity_col": "entity", "time_col": "time",
        })
        result = est.run(df)
        expected = 1.0 - (1.0 - result.rsquared) * (result.nobs - 1) / result.df_resid
        assert math.isclose(result.rsquared_adj, expected, rel_tol=1e-12)

    def test_adj_differs_on_synthetic(self):
        from econflow.estimation.ols import PooledOLS
        df = _make_synthetic_panel(n_entities=8, n_time=12, seed=17)
        est = PooledOLS(params={
            "dependent": "y", "regressors": ["x1", "x2"],
            "entity_col": "entity", "time_col": "time",
        })
        result = est.run(df)
        assert result.rsquared_adj != result.rsquared

    def test_adj_positive_with_good_fit(self):
        """Positive adj R² when regressors genuinely explain variance."""
        from econflow.estimation.ols import PooledOLS
        df = _make_synthetic_panel(n_entities=10, n_time=20, seed=1)
        est = PooledOLS(params={
            "dependent": "y", "regressors": ["x1", "x2"],
            "entity_col": "entity", "time_col": "time",
        })
        result = est.run(df)
        assert result.rsquared_adj > 0.0

    def test_df_resid_is_nobs_minus_k_minus_one(self):
        """PooledOLS fits an explicit constant → df_resid = nobs - k - 1
        (k = number of regressors, +1 for the intercept). Corrected
        2026-07-18: see test_df_resid_grunfeld for the same correction."""
        from econflow.estimation.ols import PooledOLS
        df = _make_synthetic_panel(n_entities=4, n_time=5, seed=9)
        est = PooledOLS(params={
            "dependent": "y", "regressors": ["x1", "x2"],
            "entity_col": "entity", "time_col": "time",
        })
        result = est.run(df)
        assert result.df_resid == result.nobs - 2 - 1


# ===========================================================================
# API stability: Phase 1 touches only rsquared_adj
# ===========================================================================


class TestPooledOLSAPIStability:
    """Confirm no other field is touched by the Phase 1 fix."""

    def test_conf_int_is_dataframe(self, ols_result):
        """conf_int field is still a pd.DataFrame (not a method)."""
        assert isinstance(ols_result.conf_int, pd.DataFrame)
        assert "lower" in ols_result.conf_int.columns
        assert "upper" in ols_result.conf_int.columns

    def test_std_err_field_name(self, ols_result):
        """Field is std_err (not std_errors)."""
        assert hasattr(ols_result, "std_err")
        assert not hasattr(ols_result, "std_errors")

    def test_tvalues_property(self, ols_result):
        """tvalues property = params / std_err still works."""
        tv = ols_result.tvalues
        assert isinstance(tv, pd.Series)
        for reg in ["value", "capital"]:
            expected = float(ols_result.params[reg]) / float(ols_result.std_err[reg])
            assert math.isclose(float(tv[reg]), expected, rel_tol=1e-12)

    def test_extra_contains_cov_type(self, ols_result):
        assert "cov_type" in ols_result.extra
