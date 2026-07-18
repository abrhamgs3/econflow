"""
Unit tests for Phase 3 — diagnostics() on EntityFE, TwoWayFE, PooledOLS.

Roadmap reference: MIGRATION_ROADMAP.md §Phase 3.

Coverage
--------
* Successful diagnostics with Grunfeld cross-checks (FE, TWFE, OLS).
* Missing ``result.extra`` keys (pre-Phase-3 EstimationResult).
* VIF edge cases: single regressor, insufficient observations, perfectly
  collinear regressors (singular matrix), constant-term stripping.
* Breusch-Pagan edge cases: insufficient observations.
* Durbin-Watson edge cases: fewer than 3 residuals, zero residuals.
* Clustered covariance — diagnostics are cov-type-independent.
* Unsupported estimators (result produced without Phase-3 extra keys).
* DiagnosticResult structure: correct IDs, levels, JSON serializability.
* Determinism: calling diagnostics() twice returns byte-identical output.

Design rules
------------
* Each test is independent; no shared mutable state.
* Numerical cross-checks against the baseline use ``pytest.approx`` with
  ``rel=1e-3`` (0.1% relative tolerance, coarser than the 1e-4 absolute
  tolerance in the baseline CSV to survive minor statsmodels version diffs).
* PooledOLS diagnostic values differ from the pipeline baseline because the
  framework does NOT add a constant column (see §PooledOLS Mismatch note in
  MIGRATION_ROADMAP.md and in the sandbox numerical verification). Tests pin
  against framework-computed values, not the pipeline CSV baseline.
* All calls are to the public ``diagnostics(self, result)`` API or to
  ``compute_standard_diagnostics()`` directly; no private-function coverage
  of internals beyond what is needed to exercise edge cases.
"""

from __future__ import annotations

import json
import math

import numpy as np
import pandas as pd
import pytest

from econflow.estimation._diagnostics import (
    _diag_breusch_pagan,
    _diag_durbin_watson,
    _diag_vif,
    compute_standard_diagnostics,
)
from econflow.estimation.fixed_effects import EntityFE, TwoWayFE
from econflow.estimation.ols import PooledOLS
from econflow.estimation.result import DiagnosticResult, EstimationResult


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def _grunfeld_df() -> pd.DataFrame:
    """Grunfeld (balanced panel 11 firms × 20 years = 220 obs)."""
    from statsmodels.datasets import grunfeld  # noqa: PLC0415

    return grunfeld.load_pandas().data  # columns: invest, value, capital, firm, year


def _grunfeld_spec_fe() -> dict:
    return {
        "dependent": "invest",
        "regressors": ["value", "capital"],
        "entity_col": "firm",
        "time_col": "year",
        "cov_type": "clustered",
        "cluster_entity": True,
    }


def _grunfeld_spec_ols() -> dict:
    return {
        "dependent": "invest",
        "regressors": ["value", "capital"],
        "entity_col": "firm",
        "time_col": "year",
        "cov_type": "robust",
    }


def _minimal_estimation_result(**extra_override) -> EstimationResult:
    """
    Synthetic EstimationResult whose extra dict is fully under test control.
    The statistical fields are dummies; only extra matters for diagnostics().
    """
    # Three-row dataset: 2 regressors, 3 obs
    resids = [1.0, -0.5, 0.25]
    X = [[1.0, 2.0], [1.5, 3.0], [2.0, 4.5]]
    extra = {
        "residuals": resids,
        "X_vif_values": X,
        "X_vif_columns": ["x1", "x2"],
    }
    extra.update(extra_override)
    return EstimationResult(
        estimator_id="fe",
        estimator_name="Test",
        params=pd.Series({"x1": 0.1, "x2": 0.2}),
        std_err=pd.Series({"x1": 0.01, "x2": 0.02}),
        conf_int=pd.DataFrame({"lower": [0.08, 0.16], "upper": [0.12, 0.24]},
                              index=["x1", "x2"]),
        pvalues=pd.Series({"x1": 0.01, "x2": 0.02}),
        nobs=3,
        ngroups=1,
        df_resid=1,
        rsquared=0.9,
        rsquared_adj=0.8,
        f_statistic=None,
        f_pvalue=None,
        entity_col="entity",
        time_col="time",
        entities=["e1"],
        time_periods=[1, 2, 3],
        provenance={},
        extra=extra,
    )


# ---------------------------------------------------------------------------
# Baseline pins (verified via sandbox, not pipeline CSV)
# ---------------------------------------------------------------------------

# FE / TWFE pins match pipeline baseline exactly (within-transformation absorbs
# the constant column that the pipeline adds, so residuals are identical).
_VIF_MAX_GRUNFELD = 1.3561562146291226
_BP_FE_GRUNFELD = 77.87137086492372
# Sprint S1: DW values updated to BFN within-entity panel formula.
# Old cross-entity DW values (now deprecated):
#   _DW_FE_GRUNFELD   was 0.9718254058239162
#   _DW_TWFE_GRUNFELD was 0.9161226607249299
#   _DW_OLS_FRAMEWORK was 0.38147491200599487
_DW_FE_GRUNFELD = 0.6845429500159578
_BP_TWFE_GRUNFELD = 68.7759862370838
_DW_TWFE_GRUNFELD = 0.6849717134941167

# Corrected 2026-07-18 (Repository Integrity Repair): the previous claim that
# the estimator-level path differs from the pipeline CSV baseline due to
# constant-column handling does not hold under current source. Calling
# PooledOLS(...).run(df); PooledOLS(...).diagnostics(result) directly --
# i.e. exactly the "estimator-level diagnostic path" this file exercises --
# on the same statsmodels Grunfeld fixture used below reproduces the pipeline
# CSV baseline exactly: BP=65.22800988589293, DW=0.2076399576583588 (BFN
# panel formula, Sprint S1). The 82.20/0.1883 values below could not be
# reproduced from any current code path and are stale.
_BP_OLS_FRAMEWORK = 65.22800988589293
# Sprint S1: BFN panel DW (was 0.3707 with cross-entity formula)
_DW_OLS_FRAMEWORK = 0.2076399576583588


# ---------------------------------------------------------------------------
# 1. _diag_vif — unit tests
# ---------------------------------------------------------------------------


class TestDiagVIF:
    """Unit tests for the private _diag_vif() helper."""

    def test_returns_diagnostic_result(self):
        X = [[1.0, 2.0], [3.0, 1.0], [2.0, 5.0], [0.5, 3.0]]
        result = _diag_vif(X, ["a", "b"])
        assert isinstance(result, DiagnosticResult)
        assert result.diagnostic_id == "vif"

    def test_single_regressor_returns_info(self):
        X = [[1.0], [2.0], [3.0]]
        result = _diag_vif(X, ["x"])
        assert result.level == "info"
        assert "fewer than 2" in result.conclusion

    def test_empty_columns_returns_info(self):
        X = [[1.0], [2.0]]
        result = _diag_vif(X, [])
        assert result.level == "info"

    def test_insufficient_observations(self):
        # 2 obs, 2 regressors → n <= k, should bail
        X = [[1.0, 2.0], [3.0, 4.0]]
        result = _diag_vif(X, ["a", "b"])
        assert result.level == "info"
        assert "insufficient" in result.conclusion.lower()

    def test_normal_case_no_collinearity(self):
        rng = np.random.default_rng(42)
        n = 50
        X = rng.standard_normal((n, 2)).tolist()
        result = _diag_vif(X, ["a", "b"])
        assert result.statistic is not None
        assert result.statistic < 10.0
        assert result.level == "info"
        assert "No multicollinearity" in result.conclusion

    def test_high_collinearity_warning(self):
        # x2 = x1 + tiny noise → near-perfect collinearity
        rng = np.random.default_rng(7)
        n = 100
        x1 = rng.standard_normal(n)
        x2 = x1 + rng.standard_normal(n) * 1e-6
        X = np.column_stack([x1, x2]).tolist()
        result = _diag_vif(X, ["x1", "x2"])
        assert result.level == "warning"
        assert result.statistic is None or result.statistic > 10.0

    def test_constant_columns_stripped(self):
        # "const" in column names should be ignored in VIF computation
        rng = np.random.default_rng(1)
        n = 40
        x1 = rng.standard_normal(n)
        x2 = rng.standard_normal(n)
        ones = np.ones(n)
        X = np.column_stack([ones, x1, x2]).tolist()
        result = _diag_vif(X, ["const", "x1", "x2"])
        # const stripped → only x1, x2 enter VIF; should succeed
        assert isinstance(result, DiagnosticResult)
        assert result.statistic is not None

    def test_singular_matrix_does_not_raise(self):
        # Perfectly collinear: x2 = 2 * x1
        x1 = [1.0, 2.0, 3.0, 4.0, 5.0]
        x2 = [2.0, 4.0, 6.0, 8.0, 10.0]
        X = [[a, b] for a, b in zip(x1, x2)]
        result = _diag_vif(X, ["x1", "x2"])
        # Must not raise; level must be "info" or "warning"
        assert isinstance(result, DiagnosticResult)
        assert result.level in ("info", "warning")

    def test_extra_contains_vif_values(self):
        rng = np.random.default_rng(99)
        X = rng.standard_normal((30, 2)).tolist()
        result = _diag_vif(X, ["a", "b"])
        assert "vif_values" in result.extra
        assert "threshold" in result.extra
        assert result.extra["threshold"] == 10.0

    def test_statistic_matches_max_vif(self):
        rng = np.random.default_rng(3)
        X = rng.standard_normal((50, 2)).tolist()
        result = _diag_vif(X, ["a", "b"])
        if result.statistic is not None:
            assert math.isclose(result.statistic, result.extra["max_vif"], rel_tol=1e-9)

    def test_grunfeld_vif_pin(self):
        """VIF on Grunfeld value/capital must match baseline to 4 dp."""
        df = _grunfeld_df()
        panel = df.set_index(["firm", "year"]).sort_index()
        X = panel[["value", "capital"]].values.tolist()
        result = _diag_vif(X, ["value", "capital"])
        assert result.statistic == pytest.approx(_VIF_MAX_GRUNFELD, rel=1e-3)


# ---------------------------------------------------------------------------
# 2. _diag_breusch_pagan — unit tests
# ---------------------------------------------------------------------------


class TestDiagBreuschPagan:
    """Unit tests for the private _diag_breusch_pagan() helper."""

    def test_returns_diagnostic_result(self):
        resids = [0.1, -0.2, 0.15, -0.05, 0.3, -0.1, 0.2, 0.0, -0.3, 0.1]
        X = [[float(i), float(i) ** 0.5] for i in range(1, 11)]
        result = _diag_breusch_pagan(resids, X)
        assert isinstance(result, DiagnosticResult)
        assert result.diagnostic_id == "breusch_pagan"

    def test_insufficient_observations(self):
        # 2 obs, 2 regressors: n <= k + 1 → bail
        resids = [0.1, -0.1]
        X = [[1.0, 2.0], [3.0, 4.0]]
        result = _diag_breusch_pagan(resids, X)
        assert result.level == "info"
        assert "insufficient" in result.conclusion.lower()

    def test_statistic_and_pvalue_populated(self):
        rng = np.random.default_rng(42)
        n = 50
        X = rng.standard_normal((n, 2)).tolist()
        resids = rng.standard_normal(n).tolist()
        result = _diag_breusch_pagan(resids, X)
        assert result.statistic is not None
        assert result.pvalue is not None
        assert 0.0 <= result.pvalue <= 1.0

    def test_high_heteroskedasticity_warning(self):
        # Heteroskedastic residuals: variance proportional to X
        rng = np.random.default_rng(5)
        n = 200
        x = rng.uniform(0.1, 10.0, n)
        X = np.column_stack([x, x ** 2]).tolist()
        # Residuals scale with x: strong heteroskedasticity
        resids = (rng.standard_normal(n) * x).tolist()
        result = _diag_breusch_pagan(resids, X)
        assert result.level == "warning"
        assert "Heteroskedasticity detected" in result.conclusion

    def test_homoskedastic_info_level(self):
        # Homoskedastic residuals: constant variance
        rng = np.random.default_rng(17)
        n = 300
        X = rng.standard_normal((n, 2)).tolist()
        resids = rng.standard_normal(n).tolist()
        result = _diag_breusch_pagan(resids, X)
        # May or may not reject — just assert no crash and correct structure
        assert result.level in ("info", "warning")
        assert result.statistic is not None

    def test_extra_contains_lm_stat(self):
        rng = np.random.default_rng(8)
        n = 40
        X = rng.standard_normal((n, 2)).tolist()
        resids = rng.standard_normal(n).tolist()
        result = _diag_breusch_pagan(resids, X)
        if result.statistic is not None:
            assert "lm_stat" in result.extra
            assert "lm_pvalue" in result.extra


# ---------------------------------------------------------------------------
# 3. _diag_durbin_watson — unit tests
# ---------------------------------------------------------------------------


class TestDiagDurbinWatson:
    """Unit tests for the private _diag_durbin_watson() helper."""

    def test_returns_diagnostic_result(self):
        result = _diag_durbin_watson([0.1, -0.2, 0.3, -0.1, 0.2])
        assert isinstance(result, DiagnosticResult)
        assert result.diagnostic_id == "durbin_watson"

    def test_fewer_than_3_residuals(self):
        result = _diag_durbin_watson([0.1, -0.1])
        assert result.level == "info"
        assert "insufficient" in result.conclusion.lower()

    def test_single_residual(self):
        result = _diag_durbin_watson([0.5])
        assert result.level == "info"

    def test_empty_residuals(self):
        result = _diag_durbin_watson([])
        assert result.level == "info"

    def test_zero_residuals(self):
        result = _diag_durbin_watson([0.0, 0.0, 0.0, 0.0])
        assert result.level == "info"
        assert "zero" in result.conclusion.lower()

    def test_positive_autocorrelation_warning(self):
        # Trending residuals → low DW (Δe small relative to e)
        resids = [10.0, 9.5, 9.0, 8.5, 8.0, 7.5, 7.0, 6.5]
        result = _diag_durbin_watson(resids)
        assert result.level == "warning"
        assert result.statistic < 1.5
        assert "Positive serial correlation" in result.conclusion

    def test_no_autocorrelation_info(self):
        # Alternating residuals with moderate magnitude → DW near 2
        resids = [1.0, -1.0, 1.0, -1.0, 1.0, -1.0, 1.0, -1.0]
        result = _diag_durbin_watson(resids)
        # DW = Σ(Δe²) / Σ(e²); Δe = [-2,2,-2,2,...], Δe² = 4 each
        # Σ(Δe²) = 7*4 = 28, Σ(e²) = 8*1 = 8 → DW = 3.5 > 2.5
        # So this actually triggers negative-autocorrelation warning.
        assert result.statistic is not None

    def test_dw_formula_matches_manual_calculation(self):
        resids = [1.0, 2.0, 3.0, 1.5]
        result = _diag_durbin_watson(resids)
        diffs = np.diff(np.array(resids))
        expected = float(np.sum(diffs ** 2) / np.sum(np.array(resids) ** 2))
        assert result.statistic == pytest.approx(expected, rel=1e-12)

    def test_extra_contains_dw(self):
        resids = [0.1, -0.2, 0.3, 0.15, -0.1]
        result = _diag_durbin_watson(resids)
        if result.statistic is not None:
            assert "dw" in result.extra
            assert result.extra["dw"] == result.statistic


# ---------------------------------------------------------------------------
# 4. compute_standard_diagnostics — unit tests
# ---------------------------------------------------------------------------


class TestComputeStandardDiagnostics:
    """Unit tests for the public compute_standard_diagnostics() entry point."""

    def test_full_extra_returns_three_results(self):
        result = _minimal_estimation_result()
        diags = compute_standard_diagnostics(result)
        assert len(diags) == 3

    def test_result_order_vif_bp_dw(self):
        result = _minimal_estimation_result()
        diags = compute_standard_diagnostics(result)
        assert diags[0].diagnostic_id == "vif"
        assert diags[1].diagnostic_id == "breusch_pagan"
        assert diags[2].diagnostic_id == "durbin_watson"

    def test_missing_residuals_skips_bp_and_dw(self):
        # Without residuals, only VIF is computed
        result = _minimal_estimation_result()
        del result.extra["residuals"]
        diags = compute_standard_diagnostics(result)
        ids = [d.diagnostic_id for d in diags]
        assert "vif" in ids
        assert "breusch_pagan" not in ids
        assert "durbin_watson" not in ids

    def test_missing_x_vif_values_skips_vif_and_bp(self):
        # Without X, VIF and BP are skipped; DW still runs
        result = _minimal_estimation_result()
        del result.extra["X_vif_values"]
        diags = compute_standard_diagnostics(result)
        ids = [d.diagnostic_id for d in diags]
        assert "vif" not in ids
        assert "breusch_pagan" not in ids
        assert "durbin_watson" in ids

    def test_empty_extra_returns_empty_list(self):
        result = _minimal_estimation_result()
        result.extra.clear()
        diags = compute_standard_diagnostics(result)
        assert diags == []

    def test_missing_x_columns_key_skips_vif(self):
        # X_vif_columns missing (None default from .get()) → no VIF
        result = _minimal_estimation_result()
        del result.extra["X_vif_columns"]
        # X_vif_values present, X_vif_columns absent
        # compute_standard_diagnostics uses .get("X_vif_columns", [])
        # so it gets [] → passes as `x_cols=[]` → _diag_vif gets empty columns
        # single-reg or < 2 regs path → "VIF not meaningful" info result
        diags = compute_standard_diagnostics(result)
        vif_diags = [d for d in diags if d.diagnostic_id == "vif"]
        assert len(vif_diags) == 1
        assert vif_diags[0].level == "info"

    def test_never_raises_on_garbage_residuals(self):
        # Residuals contain NaN — should not propagate an exception
        result = _minimal_estimation_result()
        result.extra["residuals"] = [float("nan"), float("nan"), float("nan")]
        diags = compute_standard_diagnostics(result)
        # Function must return a list, not raise
        assert isinstance(diags, list)

    def test_all_results_are_diagnostic_result_instances(self):
        result = _minimal_estimation_result()
        diags = compute_standard_diagnostics(result)
        for d in diags:
            assert isinstance(d, DiagnosticResult)

    def test_pre_phase3_result_returns_empty_list(self):
        """
        An EstimationResult produced before Phase 3 (no diagnostic keys in
        extra) must silently return [].  This prevents regressions when
        diagnostics() is called on cached or legacy results.

        Sprint S2 note: cov_type is NOT set here (only effects is set), so the
        cluster-count diagnostic is not triggered.  A legacy result with no
        residuals, no X data, and no cov_type still returns [].
        """
        result = _minimal_estimation_result()
        result.extra.clear()
        result.extra["effects"] = "entity"
        # No cov_type, no residuals, no X data → all diagnostics skipped → []
        diags = compute_standard_diagnostics(result)
        assert diags == []


# ---------------------------------------------------------------------------
# 5. EntityFE.diagnostics() — integration against Grunfeld
# ---------------------------------------------------------------------------


class TestEntityFEDiagnostics:
    """
    Integration tests for EntityFE.diagnostics() on the Grunfeld dataset.
    Values are cross-checked against the Phase 0 baseline
    (tests/integration/fixtures/baseline/diagnostics.csv).
    """

    @pytest.fixture(scope="class")
    def fe_result(self):
        df = _grunfeld_df()
        estimator = EntityFE(params=_grunfeld_spec_fe())
        return estimator.run(df)

    def test_returns_five_diagnostics(self, fe_result):
        # Sprint S2: EntityFE with cov_type="clustered" (Grunfeld, 11 firms)
        # now returns 5 diagnostics: VIF, BP, DW, cluster_count, vif_within.
        assert len(fe_result.diagnostic_results) == 5

    def test_diagnostic_ids(self, fe_result):
        ids = [d.diagnostic_id for d in fe_result.diagnostic_results]
        assert ids == ["vif", "breusch_pagan", "durbin_watson",
                       "cluster_count", "vif_within"]

    def test_all_are_diagnostic_result(self, fe_result):
        for d in fe_result.diagnostic_results:
            assert isinstance(d, DiagnosticResult)

    def test_vif_pin(self, fe_result):
        vif = next(d for d in fe_result.diagnostic_results if d.diagnostic_id == "vif")
        assert vif.statistic == pytest.approx(_VIF_MAX_GRUNFELD, rel=1e-3)

    def test_vif_no_multicollinearity_conclusion(self, fe_result):
        vif = next(d for d in fe_result.diagnostic_results if d.diagnostic_id == "vif")
        assert "No multicollinearity" in vif.conclusion
        assert vif.level == "info"

    def test_bp_pin(self, fe_result):
        bp = next(d for d in fe_result.diagnostic_results
                  if d.diagnostic_id == "breusch_pagan")
        assert bp.statistic == pytest.approx(_BP_FE_GRUNFELD, rel=1e-3)

    def test_bp_heteroskedasticity_warning(self, fe_result):
        bp = next(d for d in fe_result.diagnostic_results
                  if d.diagnostic_id == "breusch_pagan")
        assert bp.level == "warning"
        assert bp.pvalue is not None
        assert bp.pvalue < 0.05

    def test_dw_pin(self, fe_result):
        dw = next(d for d in fe_result.diagnostic_results
                  if d.diagnostic_id == "durbin_watson")
        assert dw.statistic == pytest.approx(_DW_FE_GRUNFELD, rel=1e-3)

    def test_dw_serial_correlation_warning(self, fe_result):
        dw = next(d for d in fe_result.diagnostic_results
                  if d.diagnostic_id == "durbin_watson")
        assert dw.level == "warning"
        assert dw.statistic < 1.5

    def test_diagnostic_results_are_json_serializable(self, fe_result):
        for d in fe_result.diagnostic_results:
            raw = d.to_json()
            parsed = json.loads(raw)
            assert parsed["diagnostic_id"] == d.diagnostic_id

    def test_diagnostics_deterministic(self):
        """Calling diagnostics() twice on the same result produces identical output."""
        df = _grunfeld_df()
        estimator = EntityFE(params=_grunfeld_spec_fe())
        result = estimator.run(df)
        run1 = estimator.diagnostics(result)
        run2 = estimator.diagnostics(result)
        for d1, d2 in zip(run1, run2):
            assert d1.statistic == d2.statistic
            assert d1.pvalue == d2.pvalue
            assert d1.conclusion == d2.conclusion

    def test_clustered_cov_same_diagnostics_as_robust(self):
        """
        Residuals are identical regardless of cov_type (cov_type only affects
        standard errors, not point estimates or residuals).  VIF/BP/DW/within-VIF
        must be the same for clustered vs. robust.

        Sprint S2 note: clustered returns 5 diagnostics (adds cluster_count);
        robust returns 4 (adds within-VIF but not cluster_count).  Compare by
        diagnostic ID rather than position to avoid false mismatches.
        """
        df = _grunfeld_df()
        spec_clust = dict(_grunfeld_spec_fe(), cov_type="clustered")
        spec_robust = dict(_grunfeld_spec_fe(), cov_type="robust")
        res_clust = EntityFE(params=spec_clust).run(df)
        res_robust = EntityFE(params=spec_robust).run(df)
        # Build lookup by diagnostic_id for each run
        clust_by_id = {d.diagnostic_id: d for d in res_clust.diagnostic_results}
        robust_by_id = {d.diagnostic_id: d for d in res_robust.diagnostic_results}
        # Diagnostics that must be identical across cov_type choices
        for did in ("vif", "breusch_pagan", "durbin_watson", "vif_within"):
            if did in clust_by_id and did in robust_by_id:
                d_c, d_r = clust_by_id[did], robust_by_id[did]
                if d_c.statistic is not None and d_r.statistic is not None:
                    assert d_c.statistic == pytest.approx(d_r.statistic, rel=1e-10)


# ---------------------------------------------------------------------------
# 6. TwoWayFE.diagnostics() — integration against Grunfeld
# ---------------------------------------------------------------------------


class TestTwoWayFEDiagnostics:
    """
    Integration tests for TwoWayFE.diagnostics() on the Grunfeld dataset.
    VIF must match the FE/OLS value (same regressors); BP and DW differ
    because TWFE within-transformation also removes time effects.
    """

    @pytest.fixture(scope="class")
    def twfe_result(self):
        df = _grunfeld_df()
        estimator = TwoWayFE(params=_grunfeld_spec_fe())
        return estimator.run(df)

    def test_returns_five_diagnostics(self, twfe_result):
        # Sprint S2: TwoWayFE with cov_type="clustered" (Grunfeld, 11 firms)
        # now returns 5 diagnostics: VIF, BP, DW, cluster_count, vif_within.
        assert len(twfe_result.diagnostic_results) == 5

    def test_diagnostic_ids(self, twfe_result):
        ids = [d.diagnostic_id for d in twfe_result.diagnostic_results]
        assert ids == ["vif", "breusch_pagan", "durbin_watson",
                       "cluster_count", "vif_within"]

    def test_vif_pin(self, twfe_result):
        vif = next(d for d in twfe_result.diagnostic_results if d.diagnostic_id == "vif")
        assert vif.statistic == pytest.approx(_VIF_MAX_GRUNFELD, rel=1e-3)

    def test_bp_pin(self, twfe_result):
        bp = next(d for d in twfe_result.diagnostic_results
                  if d.diagnostic_id == "breusch_pagan")
        assert bp.statistic == pytest.approx(_BP_TWFE_GRUNFELD, rel=1e-3)

    def test_dw_pin(self, twfe_result):
        dw = next(d for d in twfe_result.diagnostic_results
                  if d.diagnostic_id == "durbin_watson")
        assert dw.statistic == pytest.approx(_DW_TWFE_GRUNFELD, rel=1e-3)

    def test_bp_differs_from_entity_fe(self, twfe_result):
        """TWFE and EntityFE must produce different BP statistics."""
        bp_twfe = next(d for d in twfe_result.diagnostic_results
                       if d.diagnostic_id == "breusch_pagan").statistic
        assert bp_twfe is not None
        assert bp_twfe != pytest.approx(_BP_FE_GRUNFELD, rel=1e-6)

    def test_diagnostics_deterministic(self):
        df = _grunfeld_df()
        estimator = TwoWayFE(params=_grunfeld_spec_fe())
        result = estimator.run(df)
        run1 = estimator.diagnostics(result)
        run2 = estimator.diagnostics(result)
        for d1, d2 in zip(run1, run2):
            assert d1.statistic == d2.statistic


# ---------------------------------------------------------------------------
# 7. PooledOLS.diagnostics() — integration against Grunfeld
# ---------------------------------------------------------------------------


class TestPooledOLSDiagnostics:
    """
    Integration tests for PooledOLS.diagnostics() on the Grunfeld dataset.

    The framework PooledOLS estimator's BP and DW statistics match the
    pipeline baseline CSV values (verified 2026-07-18 by calling this
    estimator-level path directly and comparing against a fresh
    `econflow run` of the getting_started example). Tests pin against
    the framework-computed values.
    """

    @pytest.fixture(scope="class")
    def ols_result(self):
        df = _grunfeld_df()
        estimator = PooledOLS(params=_grunfeld_spec_ols())
        return estimator.run(df)

    def test_returns_three_diagnostics(self, ols_result):
        # PooledOLS uses cov_type="robust" and does not store X_within_vif_values,
        # so it still returns exactly 3 diagnostics (VIF, BP, DW) in Sprint S2.
        assert len(ols_result.diagnostic_results) == 3

    def test_diagnostic_ids(self, ols_result):
        ids = [d.diagnostic_id for d in ols_result.diagnostic_results]
        assert ids == ["vif", "breusch_pagan", "durbin_watson"]

    def test_vif_pin(self, ols_result):
        """VIF uses raw regressors identical to FE/TWFE → same value."""
        vif = next(d for d in ols_result.diagnostic_results if d.diagnostic_id == "vif")
        assert vif.statistic == pytest.approx(_VIF_MAX_GRUNFELD, rel=1e-3)

    def test_bp_pin_framework_value(self, ols_result):
        """
        BP stat matches the pipeline CSV baseline (65.228) -- the
        estimator-level and pipeline diagnostic paths agree under current
        source (corrected 2026-07-18; see comment above _BP_OLS_FRAMEWORK).
        """
        bp = next(d for d in ols_result.diagnostic_results
                  if d.diagnostic_id == "breusch_pagan")
        assert bp.statistic == pytest.approx(_BP_OLS_FRAMEWORK, rel=1e-3)
        # Verify it matches the pipeline baseline (see correction note above)
        assert abs(bp.statistic - 65.228) < 0.01, (
            f"OLS BP ({bp.statistic}) no longer matches the pipeline baseline "
            f"(65.228) — investigate before re-diverging these pins."
        )

    def test_dw_pin_framework_value(self, ols_result):
        """DW stat is ~0.1883 (Sprint S1 BFN panel formula).
        Previously 0.3815 with the cross-entity formula; 0.3707 in pipeline CSV."""
        dw = next(d for d in ols_result.diagnostic_results
                  if d.diagnostic_id == "durbin_watson")
        assert dw.statistic == pytest.approx(_DW_OLS_FRAMEWORK, rel=1e-3)

    def test_all_diagnostic_results_are_instances(self, ols_result):
        for d in ols_result.diagnostic_results:
            assert isinstance(d, DiagnosticResult)

    def test_diagnostics_deterministic(self):
        df = _grunfeld_df()
        estimator = PooledOLS(params=_grunfeld_spec_ols())
        result = estimator.run(df)
        run1 = estimator.diagnostics(result)
        run2 = estimator.diagnostics(result)
        for d1, d2 in zip(run1, run2):
            assert d1.statistic == d2.statistic


# ---------------------------------------------------------------------------
# 8. Edge cases: missing data, insufficient observations
# ---------------------------------------------------------------------------


class TestEdgeCaseMissingData:
    """
    Diagnostics must work correctly when the input DataFrame has NaN rows.
    fit() calls dropna() before building the panel; diagnostics() then
    receives residuals / X from the cleaned data only.
    """

    def test_nan_rows_dropped_diagnostics_still_run(self):
        df = _grunfeld_df()
        # Inject NaN into first 5 rows of "value"
        df = df.copy()
        df.loc[df.index[:5], "value"] = float("nan")
        result = EntityFE(params=_grunfeld_spec_fe()).run(df)
        # Sprint S2: EntityFE with cov_type="clustered" now returns 5 diagnostics.
        # All 11 firms still present after NaN drop (only some obs removed).
        assert len(result.diagnostic_results) == 5
        assert all(isinstance(d, DiagnosticResult) for d in result.diagnostic_results)

    def test_nan_rows_dropped_vif_still_valid(self):
        df = _grunfeld_df()
        df = df.copy()
        df.loc[df.index[:5], "capital"] = float("nan")
        result = PooledOLS(params=_grunfeld_spec_ols()).run(df)
        vif = next(d for d in result.diagnostic_results if d.diagnostic_id == "vif")
        assert vif.statistic is not None


# ---------------------------------------------------------------------------
# 9. Edge cases: insufficient observations
# ---------------------------------------------------------------------------


class TestEdgeCaseInsufficientObservations:
    """
    With fewer observations than regressors, VIF and BP fall through to their
    "insufficient observations" paths rather than crashing.
    """

    def test_vif_insufficient_obs(self):
        # Only 1 obs, 2 regressors
        result = _diag_vif([[1.0, 2.0]], ["a", "b"])
        assert result.level == "info"
        assert "insufficient" in result.conclusion.lower()

    def test_bp_insufficient_obs(self):
        # 3 obs, 3 regressors → n <= k + 1
        resids = [0.1, -0.1, 0.05]
        X = [[1.0, 2.0, 3.0], [4.0, 5.0, 6.0], [7.0, 8.0, 9.0]]
        result = _diag_breusch_pagan(resids, X)
        assert result.level == "info"
        assert "insufficient" in result.conclusion.lower()

    def test_dw_insufficient_obs(self):
        result = _diag_durbin_watson([0.5])
        assert result.level == "info"

    def test_compute_on_minimal_dataset(self):
        """
        diagnostics() must not raise when data has fewer observations than
        regressors (roadmap requirement §Phase 3 cross-check #6).
        """
        # Build a 1-obs result manually
        result = _minimal_estimation_result(
            **{
                "residuals": [0.1],
                "X_vif_values": [[1.0, 2.0]],
                "X_vif_columns": ["x1", "x2"],
            }
        )
        diags = compute_standard_diagnostics(result)
        assert isinstance(diags, list)
        assert all(isinstance(d, DiagnosticResult) for d in diags)


# ---------------------------------------------------------------------------
# 10. Clustered covariance does not affect diagnostic statistics
# ---------------------------------------------------------------------------


class TestClusteredCovariance:
    """
    cov_type="clustered" affects only standard errors, not residuals.
    Diagnostic statistics must be identical across cov_type choices.
    """

    def test_twfe_clustered_vs_robust_identical_diagnostics(self):
        """
        Sprint S2 note: clustered returns 5 diagnostics (adds cluster_count);
        robust returns 4 (adds within-VIF but not cluster_count).  Compare
        by diagnostic ID so cross-type pairing doesn't produce false failures.
        """
        df = _grunfeld_df()
        res_clust = TwoWayFE(
            params=dict(_grunfeld_spec_fe(), cov_type="clustered")
        ).run(df)
        res_robust = TwoWayFE(
            params=dict(_grunfeld_spec_fe(), cov_type="robust")
        ).run(df)
        clust_by_id = {d.diagnostic_id: d for d in res_clust.diagnostic_results}
        robust_by_id = {d.diagnostic_id: d for d in res_robust.diagnostic_results}
        for did in ("vif", "breusch_pagan", "durbin_watson", "vif_within"):
            if did in clust_by_id and did in robust_by_id:
                d_c, d_r = clust_by_id[did], robust_by_id[did]
                if d_c.statistic is not None and d_r.statistic is not None:
                    assert d_c.statistic == pytest.approx(d_r.statistic, rel=1e-10)

    def test_ols_clustered_vs_robust_identical_diagnostics(self):
        df = _grunfeld_df()
        res_clust = PooledOLS(
            params=dict(_grunfeld_spec_ols(), cov_type="clustered", cluster_entity=True)
        ).run(df)
        res_robust = PooledOLS(params=_grunfeld_spec_ols()).run(df)
        for d_c, d_r in zip(res_clust.diagnostic_results, res_robust.diagnostic_results):
            if d_c.statistic is not None and d_r.statistic is not None:
                assert d_c.statistic == pytest.approx(d_r.statistic, rel=1e-10)


# ---------------------------------------------------------------------------
# 11. DiagnosticResult structural guarantees
# ---------------------------------------------------------------------------


class TestDiagnosticResultStructure:
    """
    Structural guarantees on every DiagnosticResult returned by diagnostics().
    """

    @pytest.fixture(scope="class")
    def all_diags(self):
        df = _grunfeld_df()
        fe_diags = EntityFE(params=_grunfeld_spec_fe()).run(df).diagnostic_results
        twfe_diags = TwoWayFE(params=_grunfeld_spec_fe()).run(df).diagnostic_results
        ols_diags = PooledOLS(params=_grunfeld_spec_ols()).run(df).diagnostic_results
        # Sprint S2: EntityFE=5, TwoWayFE=5, PooledOLS=3 → 13 total
        # (OLS uses cov_type="robust" so no cluster_count; no X_within_vif_values)
        return fe_diags + twfe_diags + ols_diags  # 13 total

    def test_count(self, all_diags):
        assert len(all_diags) == 13

    def test_ids_are_strings(self, all_diags):
        for d in all_diags:
            assert isinstance(d.diagnostic_id, str)
            assert len(d.diagnostic_id) > 0

    def test_names_are_strings(self, all_diags):
        for d in all_diags:
            assert isinstance(d.diagnostic_name, str)

    def test_levels_valid(self, all_diags):
        for d in all_diags:
            assert d.level in ("info", "warning", "error")

    def test_statistic_is_float_or_none(self, all_diags):
        for d in all_diags:
            assert d.statistic is None or isinstance(d.statistic, float)

    def test_pvalue_is_float_or_none(self, all_diags):
        for d in all_diags:
            assert d.pvalue is None or isinstance(d.pvalue, float)

    def test_pvalue_in_unit_interval(self, all_diags):
        for d in all_diags:
            if d.pvalue is not None:
                assert 0.0 <= d.pvalue <= 1.0

    def test_conclusion_is_non_empty_string(self, all_diags):
        for d in all_diags:
            assert isinstance(d.conclusion, str)
            assert len(d.conclusion) > 0

    def test_json_round_trip(self, all_diags):
        for d in all_diags:
            raw = d.to_json()
            parsed = json.loads(raw)
            assert parsed["diagnostic_id"] == d.diagnostic_id
            assert parsed["level"] == d.level

    def test_to_dict_no_nan_values(self, all_diags):
        """to_dict() must not return float NaN (breaks JSON serialization)."""
        for d in all_diags:
            data = d.to_dict()
            # statistic and pvalue must be None or a normal float (no NaN)
            stat = data.get("statistic")
            pval = data.get("pvalue")
            if stat is not None:
                assert not (isinstance(stat, float) and math.isnan(stat))
            if pval is not None:
                assert not (isinstance(pval, float) and math.isnan(pval))


# ---------------------------------------------------------------------------
# 12. Sprint S1 — BFN panel DW, ModelSpecificationError, FE within-R²
# ---------------------------------------------------------------------------


class TestSprintS1BFNDurbinWatson:
    """
    Sprint S1: Bhargava-Franzini-Narendranathan (1982) within-entity DW.

    Verifies:
    - Time-series fallback (no entity_index) is unchanged.
    - Panel path activates when entity_index with >1 entities is supplied.
    - BFN formula matches manual computation exactly.
    - ``extra["formula"]`` discriminates the two paths.
    - ``compute_standard_diagnostics`` extracts entity_index from
      ``result.extra["residuals_index"]`` and uses BFN automatically.
    """

    def test_time_series_path_unchanged(self):
        """No entity_index → time-series formula (backward compat)."""
        resids = [1.0, 2.0, 3.0, 1.5]
        result = _diag_durbin_watson(resids)
        diffs = np.diff(np.array(resids))
        expected = float(np.sum(diffs ** 2) / np.sum(np.array(resids) ** 2))
        assert result.statistic == pytest.approx(expected, rel=1e-12)
        assert result.extra.get("formula") == "time_series"

    def test_panel_path_with_entity_index(self):
        """With entity_index the BFN formula is used and differs from naive np.diff."""
        # 2 entities, 3 obs each: e1=[1,2,3], e2=[4,5,6]
        resids = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]
        entity_index = ["A", "A", "A", "B", "B", "B"]
        result = _diag_durbin_watson(resids, entity_index=entity_index)

        arr = np.array(resids)
        ss = float(np.sum(arr ** 2))
        # BFN: within-entity diffs only
        diffs_A = np.diff(arr[:3])
        diffs_B = np.diff(arr[3:])
        bfn_expected = float((np.sum(diffs_A ** 2) + np.sum(diffs_B ** 2)) / ss)
        # naive time-series (incorrect for panel): includes A[2]→B[0] jump
        naive_expected = float(np.sum(np.diff(arr) ** 2) / ss)

        assert result.statistic == pytest.approx(bfn_expected, rel=1e-12)
        assert result.statistic != pytest.approx(naive_expected, rel=1e-6)
        assert result.extra.get("formula") == "bfn_panel"

    def test_bfn_formula_matches_manual(self):
        """BFN DW exactly equals sum(within-entity diffs²) / sum(resids²)."""
        resids = [0.3, -0.1, 0.5, 0.2, -0.4, 0.1, 0.6, -0.2]
        entity_index = ["X", "X", "X", "X", "Y", "Y", "Y", "Y"]
        result = _diag_durbin_watson(resids, entity_index=entity_index)

        arr = np.array(resids)
        ss = float(np.sum(arr ** 2))
        x_diffs = np.diff(arr[:4]) ** 2
        y_diffs = np.diff(arr[4:]) ** 2
        expected = float((np.sum(x_diffs) + np.sum(y_diffs)) / ss)
        assert result.statistic == pytest.approx(expected, rel=1e-12)

    def test_single_entity_falls_back_to_time_series(self):
        """Only one unique entity → panel path has no within-entity diffs → info."""
        resids = [1.0, -0.5, 0.25, 0.1]
        entity_index = ["A", "A", "A", "A"]
        result_panel = _diag_durbin_watson(resids, entity_index=entity_index)
        result_ts = _diag_durbin_watson(resids)
        # Single entity: BFN is valid (same formula as time-series for one entity)
        # Both should produce same statistic
        assert result_panel.statistic == pytest.approx(result_ts.statistic, rel=1e-10)

    def test_formula_key_in_extra(self):
        """extra["formula"] distinguishes time_series vs bfn_panel."""
        ts_result = _diag_durbin_watson([1.0, 2.0, 3.0])
        panel_result = _diag_durbin_watson(
            [1.0, 2.0, 3.0, 4.0, 5.0, 6.0],
            entity_index=["A", "A", "A", "B", "B", "B"],
        )
        assert ts_result.extra.get("formula") == "time_series"
        assert panel_result.extra.get("formula") == "bfn_panel"

    def test_compute_standard_diagnostics_uses_bfn_for_panel_results(self):
        """
        compute_standard_diagnostics() must extract entity_index from
        result.extra["residuals_index"] and pass it to _diag_durbin_watson,
        activating the BFN formula for panel EstimationResults.
        """
        df = _grunfeld_df()
        estimator = EntityFE(params=_grunfeld_spec_fe())
        result = estimator.run(df)
        dw = next(d for d in result.diagnostic_results
                  if d.diagnostic_id == "durbin_watson")
        assert dw.extra.get("formula") == "bfn_panel"
        assert dw.statistic == pytest.approx(_DW_FE_GRUNFELD, rel=1e-3)


class TestSprintS1ModelSpecificationError:
    """
    Sprint S1: ModelSpecificationError on time-invariant regressors in FE.
    """

    def test_time_invariant_regressor_raises_entity_fe(self):
        """A constant regressor must raise ModelSpecificationError before fit."""
        from econflow.estimation.base import ModelSpecificationError

        df = _grunfeld_df()
        # 'const_col' is the same for all observations within every firm
        df = df.copy()
        df["const_col"] = 1.0
        params = {
            "dependent": "invest",
            "regressors": ["value", "const_col"],
            "entity_col": "firm",
            "time_col": "year",
        }
        with pytest.raises(ModelSpecificationError, match="zero within-entity variance"):
            EntityFE(params=params).run(df)

    def test_time_invariant_regressor_raises_twoway_fe(self):
        """
        TwoWayFE guard detects a time-invariant regressor and raises
        ModelSpecificationError before PanelOLS is called.

        Sprint S1 blocker fix: the previous test never included the invariant
        column in 'regressors', so the guard was never exercised.  This
        replacement includes 'const_col' in the regressors list and asserts
        that the error fires with the correct message.
        """
        from econflow.estimation.base import ModelSpecificationError

        df = _grunfeld_df()
        df = df.copy()
        df["const_col"] = 1.0  # constant across all firms and years
        params = {
            "dependent": "invest",
            "regressors": ["value", "const_col"],  # const_col IS in regressors
            "entity_col": "firm",
            "time_col": "year",
        }
        with pytest.raises(ModelSpecificationError, match="zero within-entity variance"):
            TwoWayFE(params=params).run(df)

    def test_time_varying_regressors_do_not_raise(self):
        """Normal time-varying regressors must not trigger the guard."""
        df = _grunfeld_df()
        params = _grunfeld_spec_fe()
        result = EntityFE(params=params).run(df)
        assert result is not None

    def test_model_specification_error_is_subclass_of_estimator_error(self):
        from econflow.estimation.base import EstimatorError, ModelSpecificationError

        assert issubclass(ModelSpecificationError, EstimatorError)

    def test_error_message_names_the_regressor(self):
        """Error message must identify which regressor is time-invariant (EntityFE)."""
        from econflow.estimation.base import ModelSpecificationError

        df = _grunfeld_df()
        df = df.copy()
        df["bad_var"] = 42.0
        params = {
            "dependent": "invest",
            "regressors": ["value", "bad_var"],
            "entity_col": "firm",
            "time_col": "year",
        }
        with pytest.raises(ModelSpecificationError) as exc_info:
            EntityFE(params=params).run(df)
        assert "bad_var" in str(exc_info.value)

    def test_error_message_names_the_regressor_twoway_fe(self):
        """Error message must identify which regressor is time-invariant (TwoWayFE)."""
        from econflow.estimation.base import ModelSpecificationError

        df = _grunfeld_df()
        df = df.copy()
        df["bad_var_tw"] = 99.0
        params = {
            "dependent": "invest",
            "regressors": ["value", "bad_var_tw"],
            "entity_col": "firm",
            "time_col": "year",
        }
        with pytest.raises(ModelSpecificationError) as exc_info:
            TwoWayFE(params=params).run(df)
        assert "bad_var_tw" in str(exc_info.value)


class TestSprintS1FERSquared:
    """
    Sprint S1: EntityFE and TwoWayFE expose within-R² as primary rsquared.

    Cross-checks the new within-R² values against linearmodels ground truth
    and verifies that the overall R² is preserved in extra["rsquared_overall"].
    """

    # Grunfeld 11-firm pins (linearmodels ground truth)
    _FE_RSQ_WITHIN = 0.7666706515488430
    _TWFE_RSQ_WITHIN = 0.7565668429373535
    _TWFE_RSQ_OVERALL = 0.7252669941886911

    @pytest.fixture(scope="class")
    def fe_result(self):
        return EntityFE(params=_grunfeld_spec_fe()).run(_grunfeld_df())

    @pytest.fixture(scope="class")
    def twfe_result(self):
        return TwoWayFE(params=_grunfeld_spec_fe()).run(_grunfeld_df())

    def test_fe_rsquared_is_within(self, fe_result):
        assert fe_result.rsquared == pytest.approx(self._FE_RSQ_WITHIN, rel=1e-6)

    def test_twfe_rsquared_is_within(self, twfe_result):
        assert twfe_result.rsquared == pytest.approx(self._TWFE_RSQ_WITHIN, rel=1e-6)

    def test_twfe_rsquared_overall_in_extra(self, twfe_result):
        """Overall R² is different from within-R² for TWFE and stored in extra."""
        overall = twfe_result.extra.get("rsquared_overall")
        assert overall is not None
        assert overall == pytest.approx(self._TWFE_RSQ_OVERALL, rel=1e-6)
        assert overall != pytest.approx(twfe_result.rsquared, rel=1e-4)

    def test_fe_rsquared_within_in_extra_equals_rsquared(self, fe_result):
        """extra['rsquared_within'] is kept for backward compat; equals rsquared."""
        assert fe_result.extra.get("rsquared_within") == pytest.approx(
            fe_result.rsquared, rel=1e-10
        )

    def test_fe_rsquared_adj_uses_within_formula(self, fe_result):
        """
        rsquared_adj = 1 - (1 - R²_within)(N - N_entities) / df_resid.
        Must NOT equal the old formula: 1 - (1 - R²_overall)(N - 1) / df_resid.
        """
        N = fe_result.nobs
        Ng = fe_result.ngroups
        df_r = fe_result.df_resid
        r2w = fe_result.rsquared
        expected_adj = 1.0 - (1.0 - r2w) * (N - Ng) / df_r
        assert fe_result.rsquared_adj == pytest.approx(expected_adj, rel=1e-10)

    def test_twfe_rsquared_adj_within_formula(self, twfe_result):
        # Sprint S1 blocker fix: TWFE absorbs entity AND time effects.
        # Correct numerator = N - N_entities - (N_times - 1), not N - N_entities.
        # For Grunfeld (N=220, Ng=11, Nt=20): numerator = 190 (not 209).
        N = twfe_result.nobs
        Ng = twfe_result.ngroups
        Nt = len(twfe_result.time_periods)
        df_r = twfe_result.df_resid
        r2w = twfe_result.rsquared
        expected_adj = 1.0 - (1.0 - r2w) * (N - Ng - (Nt - 1)) / df_r
        assert twfe_result.rsquared_adj == pytest.approx(expected_adj, rel=1e-10)
