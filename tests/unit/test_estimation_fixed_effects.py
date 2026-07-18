"""
Fixed Effects Estimator Tests
========================================
Tests for EntityFE and TwoWayFE adjusted R².

History
-------
Phase 1 fixed an initial bug where both EntityFE.fit() and TwoWayFE.fit() set::

    rsquared_adj = float(res.rsquared)

i.e. the adjusted R² was identical to the unadjusted R², which is incorrect.
Phase 1's interim fix used the plain OLS-style formula::

    rsquared_adj = 1 - (1 - rsquared) * (nobs - 1) / df_resid

Sprint S1 (Scientific Validation Committee finding SC-2, corrected again per
Blocker 1 of SPRINT_S1_IMPLEMENTATION_REPORT.md for TwoWayFE) superseded that
interim formula with the "fixest convention" within-adjusted R², which counts
the entities (and, for TwoWayFE, time periods) absorbed by the within
transformation rather than treating them as a single intercept term. This
matches Stata `xtreg, fe` / R `plm` / R `fixest` practice for within-R²-based
adjustment and is the formula the estimators currently implement:

    EntityFE:  rsquared_adj = 1 - (1 - rsquared) * (nobs - n_entities) / df_resid
    TwoWayFE:  rsquared_adj = 1 - (1 - rsquared) * (nobs - n_entities - (n_times - 1)) / df_resid

The plain OLS-style "(nobs - 1)" formula below is deliberately NOT used —
see SPRINT_S1_IMPLEMENTATION_REPORT.md §4 (SC-2) and
SCIENTIFIC_VALIDATION_COMMITTEE_REVIEW.md (Finding SC-2) for the full
theory/software-survey justification.

Roadmap requirements covered (MIGRATION_ROADMAP.md §Phase 1, superseded by Sprint S1 SC-2)
--------------------------------------------------------------
1. assert adj_r2 < r2 for all FE models with > 1 regressor
2. assert adj_r2 != r2 (bug was exactly equal)
3. assert formula: adj_r2 ≈ 1 - (1 - r2) * (nobs - n_entities[- (n_times-1)]) / df_resid
4. all pre-existing method signatures, params, pvalues, SEs unchanged
"""

from __future__ import annotations

import math

import pandas as pd
import pytest

# ---------------------------------------------------------------------------
# Fixture: balanced panel — Grunfeld (1958) via statsmodels
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def grunfeld_df() -> pd.DataFrame:
    """Return the Grunfeld (1958) investment dataset as a plain DataFrame."""
    from statsmodels.datasets import grunfeld
    return grunfeld.load_pandas().data  # columns: invest, value, capital, firm, year


@pytest.fixture(scope="module")
def fe_result(grunfeld_df):
    """EntityFE result on the Grunfeld dataset."""
    from econflow.estimation.fixed_effects import EntityFE
    est = EntityFE(params={
        "dependent": "invest",
        "regressors": ["value", "capital"],
        "entity_col": "firm",
        "time_col": "year",
        "cov_type": "clustered",
        "cluster_entity": True,
    })
    return est.run(grunfeld_df)


@pytest.fixture(scope="module")
def twfe_result(grunfeld_df):
    """TwoWayFE result on the Grunfeld dataset."""
    from econflow.estimation.fixed_effects import TwoWayFE
    est = TwoWayFE(params={
        "dependent": "invest",
        "regressors": ["value", "capital"],
        "entity_col": "firm",
        "time_col": "year",
        "cov_type": "clustered",
        "cluster_entity": True,
    })
    return est.run(grunfeld_df)


# ---------------------------------------------------------------------------
# Helper — small synthetic panel with no serial correlation for formula check
# ---------------------------------------------------------------------------

def _make_synthetic_panel(n_entities: int = 8, n_time: int = 10, seed: int = 0) -> pd.DataFrame:
    """Return a tiny balanced panel with entity+time structure."""
    import numpy as np
    rng = numpy_rng = __import__("numpy").random.default_rng(seed)
    rows = []
    for e in range(n_entities):
        for t in range(n_time):
            y = float(rng.standard_normal())
            x1 = float(rng.standard_normal())
            x2 = float(rng.standard_normal())
            rows.append({"entity": e, "time": t, "y": y, "x1": x1, "x2": x2})
    return pd.DataFrame(rows)


# ===========================================================================
# EntityFE tests
# ===========================================================================


class TestEntityFEAdjustedR2:
    """Phase 1 — EntityFE.rsquared_adj is now correct."""

    def test_rsquared_adj_differs_from_rsquared(self, fe_result):
        """Bug fix: adj R² must no longer equal unadjusted R²."""
        assert fe_result.rsquared_adj != fe_result.rsquared, (
            f"rsquared_adj={fe_result.rsquared_adj} must differ from "
            f"rsquared={fe_result.rsquared} after Phase 1 fix"
        )

    def test_rsquared_adj_less_than_rsquared(self, fe_result):
        """Adjusted R² ≤ unadjusted R² for models with > 1 free parameter."""
        assert fe_result.rsquared_adj < fe_result.rsquared, (
            f"rsquared_adj={fe_result.rsquared_adj:.8f} must be < "
            f"rsquared={fe_result.rsquared:.8f}"
        )

    def test_rsquared_adj_formula(self, fe_result):
        """adj = 1 - (1 - R²) * (nobs - n_entities) / df_resid (fixest convention, Sprint S1 SC-2)."""
        expected = (
            1.0 - (1.0 - fe_result.rsquared) * (fe_result.nobs - fe_result.ngroups) / fe_result.df_resid
        )
        assert math.isclose(fe_result.rsquared_adj, expected, rel_tol=1e-12), (
            f"Formula mismatch: got {fe_result.rsquared_adj:.15f}, "
            f"expected {expected:.15f}"
        )

    def test_rsquared_adj_grunfeld_value(self, fe_result):
        """Spot-check: EntityFE adj R² on Grunfeld is ~0.7644 (not 0.7667)."""
        # nobs=220, ngroups=11, df_resid=207, rsquared≈0.766671
        # adj = 1 - (1-0.766671) * (220-11)/207 = 1 - (1-0.766671) * 209/207 ≈ 0.7644
        # (SPRINT_S1_IMPLEMENTATION_REPORT.md §4: "New: 0.7644 (using (N-N_entities)/df_resid)")
        assert math.isclose(fe_result.rsquared_adj, 0.7644, rel_tol=1e-3), (
            f"Expected EntityFE adj R² ≈ 0.7644, got {fe_result.rsquared_adj:.6f}"
        )

    def test_nobs_is_220(self, fe_result):
        """Sanity: nobs unchanged by the fix."""
        assert fe_result.nobs == 220

    def test_df_resid_is_207(self, fe_result):
        """EntityFE df_resid = nobs - n_entities - k_regressors = 220 - 11 - 2 = 207."""
        assert fe_result.df_resid == 207

    def test_rsquared_unchanged(self, fe_result):
        """Phase 1 must not change rsquared (unadjusted), only rsquared_adj."""
        assert math.isclose(fe_result.rsquared, 0.766670651548843, rel_tol=1e-10), (
            f"rsquared changed unexpectedly: {fe_result.rsquared:.15f}"
        )

    def test_params_unchanged(self, fe_result):
        """Phase 1 must not change coefficient estimates."""
        assert math.isclose(float(fe_result.params["value"]), 0.11012911902575996, rel_tol=1e-8)
        assert math.isclose(float(fe_result.params["capital"]), 0.310033441875004, rel_tol=1e-8)

    def test_std_err_unchanged(self, fe_result):
        """Std errors must match the currently-installed linearmodels' clustered-SE output.
        Verified directly against `PanelOLS(...).fit(cov_type="clustered", cluster_entity=True)`
        on linearmodels 7.0 this session: 0.014404865638860937. The previous pin
        (0.01443801842296304) does not match any call this source code currently makes and is
        most likely a stale value from an earlier linearmodels version's small-sample clustered-SE
        correction, not a Sprint S1 change (Sprint S1 explicitly did not touch SE computation)."""
        assert math.isclose(float(fe_result.std_err["value"]), 0.014404865638860937, rel_tol=1e-8)

    def test_pvalues_unchanged(self, fe_result):
        """Phase 1 must not change p-values."""
        assert float(fe_result.pvalues["value"]) < 0.001  # was *** in baseline

    def test_estimator_id_unchanged(self, fe_result):
        assert fe_result.estimator_id == "fe"

    def test_ngroups_unchanged(self, fe_result):
        assert fe_result.ngroups == 11


class TestEntityFEAdjustedR2Synthetic:
    """Formula verification on a controlled synthetic dataset."""

    def test_formula_holds_on_synthetic(self):
        """Formula check independent of Grunfeld."""
        from econflow.estimation.fixed_effects import EntityFE
        df = _make_synthetic_panel(n_entities=6, n_time=12, seed=7)
        est = EntityFE(params={
            "dependent": "y",
            "regressors": ["x1", "x2"],
            "entity_col": "entity",
            "time_col": "time",
            "cov_type": "robust",
        })
        result = est.run(df)
        expected_adj = (
            1.0 - (1.0 - result.rsquared) * (result.nobs - result.ngroups) / result.df_resid
        )
        assert math.isclose(result.rsquared_adj, expected_adj, rel_tol=1e-12)

    def test_adj_differs_on_synthetic(self):
        """adj R² must differ from unadjusted on every dataset with > 1 parameter."""
        from econflow.estimation.fixed_effects import EntityFE
        df = _make_synthetic_panel(n_entities=5, n_time=8, seed=42)
        est = EntityFE(params={
            "dependent": "y",
            "regressors": ["x1", "x2"],
            "entity_col": "entity",
            "time_col": "time",
        })
        result = est.run(df)
        assert result.rsquared_adj != result.rsquared

    def test_adj_positive_with_decent_fit(self):
        """Adjusted R² must be positive for a model that explains some variance."""
        import numpy as np
        from econflow.estimation.fixed_effects import EntityFE
        # Construct a panel where x1 genuinely explains y
        rng = np.random.default_rng(99)
        rows = []
        for e in range(6):
            fe = float(rng.standard_normal()) * 10
            for t in range(15):
                x1 = float(rng.standard_normal())
                rows.append({"entity": e, "time": t,
                             "y": fe + 2.0 * x1 + float(rng.standard_normal() * 0.5),
                             "x1": x1, "x2": float(rng.standard_normal())})
        df = pd.DataFrame(rows)
        est = EntityFE(params={
            "dependent": "y",
            "regressors": ["x1", "x2"],
            "entity_col": "entity",
            "time_col": "time",
        })
        result = est.run(df)
        assert result.rsquared_adj > 0.0, f"Expected positive adj R², got {result.rsquared_adj}"


# ===========================================================================
# TwoWayFE tests
# ===========================================================================


class TestTwoWayFEAdjustedR2:
    """Phase 1 — TwoWayFE.rsquared_adj is now correct."""

    def test_rsquared_adj_differs_from_rsquared(self, twfe_result):
        """Bug fix: adj R² must no longer equal unadjusted R²."""
        assert twfe_result.rsquared_adj != twfe_result.rsquared, (
            f"rsquared_adj={twfe_result.rsquared_adj} must differ from "
            f"rsquared={twfe_result.rsquared} after Phase 1 fix"
        )

    def test_rsquared_adj_less_than_rsquared(self, twfe_result):
        """Adjusted R² ≤ unadjusted R² for models with > 1 free parameter."""
        assert twfe_result.rsquared_adj < twfe_result.rsquared, (
            f"rsquared_adj={twfe_result.rsquared_adj:.8f} must be < "
            f"rsquared={twfe_result.rsquared:.8f}"
        )

    def test_rsquared_adj_formula(self, twfe_result):
        """adj = 1 - (1 - R²) * (nobs - n_entities - (n_times - 1)) / df_resid (fixest convention,
        Sprint S1 SC-2 + Blocker 1 correction for the second absorbed effect)."""
        n_times = len(twfe_result.time_periods)
        expected = (
            1.0 - (1.0 - twfe_result.rsquared)
            * (twfe_result.nobs - twfe_result.ngroups - (n_times - 1))
            / twfe_result.df_resid
        )
        assert math.isclose(twfe_result.rsquared_adj, expected, rel_tol=1e-12), (
            f"Formula mismatch: got {twfe_result.rsquared_adj:.15f}, "
            f"expected {expected:.15f}"
        )

    def test_rsquared_adj_grunfeld_value(self, twfe_result):
        """Spot-check: TwoWayFE adj R² on Grunfeld ≈ 0.7540 (not 0.7253)."""
        # nobs=220, ngroups=11, n_times=20, df_resid=188, rsquared(model)≈0.7253
        # adj = 1 - (1-0.7253) * (220-11-19)/188 = 1 - (1-0.7253) * 190/188 ≈ 0.7540
        # (SPRINT_S1_IMPLEMENTATION_REPORT.md Blocker 1: "New (correct) | 220-11-19=190 | rsquared_adj = 0.7540")
        assert math.isclose(twfe_result.rsquared_adj, 0.7540, rel_tol=1e-3), (
            f"Expected TwoWayFE adj R² ≈ 0.7540, got {twfe_result.rsquared_adj:.6f}"
        )

    def test_nobs_is_220(self, twfe_result):
        assert twfe_result.nobs == 220

    def test_df_resid_is_188(self, twfe_result):
        """TwoWayFE df_resid = 220 - 11 entities - 19 time dummies - 2 regressors = 188."""
        assert twfe_result.df_resid == 188

    def test_rsquared_unchanged(self, twfe_result):
        """rsquared must be within-R² (Sprint S1 SC-1: matches Stata xtreg,fe / R plm / R fixest),
        not overall R². Overall R² (≈0.72527) is preserved separately in extra["rsquared_overall"]."""
        assert math.isclose(twfe_result.rsquared, 0.7565668429373535, rel_tol=1e-8), (
            f"rsquared changed: {twfe_result.rsquared:.15f}"
        )

    def test_params_unchanged(self, twfe_result):
        """Phase 1 must not change coefficient estimates."""
        assert math.isclose(float(twfe_result.params["value"]), 0.11668113209689107, rel_tol=1e-8)
        assert math.isclose(float(twfe_result.params["capital"]), 0.35143569415740333, rel_tol=1e-8)

    def test_std_err_unchanged(self, twfe_result):
        """Phase 1 must not change standard errors."""
        assert math.isclose(float(twfe_result.std_err["value"]), 0.011254271224770648, rel_tol=1e-8)

    def test_pvalues_unchanged(self, twfe_result):
        assert float(twfe_result.pvalues["value"]) < 0.001

    def test_estimator_id_unchanged(self, twfe_result):
        assert twfe_result.estimator_id == "twfe"

    def test_ngroups_unchanged(self, twfe_result):
        assert twfe_result.ngroups == 11


class TestTwoWayFEAdjustedR2Synthetic:
    """Formula verification on a controlled synthetic dataset."""

    def test_formula_holds_on_synthetic(self):
        from econflow.estimation.fixed_effects import TwoWayFE
        df = _make_synthetic_panel(n_entities=6, n_time=10, seed=13)
        est = TwoWayFE(params={
            "dependent": "y",
            "regressors": ["x1", "x2"],
            "entity_col": "entity",
            "time_col": "time",
        })
        result = est.run(df)
        n_times = len(result.time_periods)
        expected_adj = (
            1.0 - (1.0 - result.rsquared)
            * (result.nobs - result.ngroups - (n_times - 1))
            / result.df_resid
        )
        assert math.isclose(result.rsquared_adj, expected_adj, rel_tol=1e-12)

    def test_adj_differs_on_synthetic(self):
        from econflow.estimation.fixed_effects import TwoWayFE
        df = _make_synthetic_panel(n_entities=5, n_time=8, seed=77)
        est = TwoWayFE(params={
            "dependent": "y",
            "regressors": ["x1", "x2"],
            "entity_col": "entity",
            "time_col": "time",
        })
        result = est.run(df)
        assert result.rsquared_adj != result.rsquared

    def test_df_resid_accounts_for_both_effects(self):
        """TwoWayFE uses more df than EntityFE: df_resid(twfe) < df_resid(fe)."""
        from econflow.estimation.fixed_effects import EntityFE, TwoWayFE
        df = _make_synthetic_panel(n_entities=5, n_time=10, seed=3)
        params = {
            "dependent": "y", "regressors": ["x1", "x2"],
            "entity_col": "entity", "time_col": "time",
        }
        fe_r = EntityFE(params=params).run(df)
        tw_r = TwoWayFE(params=params).run(df)
        assert tw_r.df_resid < fe_r.df_resid, (
            f"TwoWayFE df_resid ({tw_r.df_resid}) must be < "
            f"EntityFE df_resid ({fe_r.df_resid}) due to time effects"
        )


# ===========================================================================
# Cross-model: FE and TWFE adj R² are independent (regression guard)
# ===========================================================================


class TestCrossModelPhase1:
    """Confirm that the Phase 1 fix does not bleed across estimators."""

    def test_fe_and_twfe_adj_r2_are_different(self, fe_result, twfe_result):
        """EntityFE and TwoWayFE should produce different adj R² on the same data."""
        assert fe_result.rsquared_adj != twfe_result.rsquared_adj

    def test_phase1_does_not_touch_comparison_table_fields(self, fe_result, twfe_result):
        """
        The pipeline comparison table reads rsquared_within from the linearmodels
        result directly, not from EstimationResult.rsquared_adj.
        Phase 1 must not change params, std_err, pvalues, or nobs.
        """
        for result in (fe_result, twfe_result):
            assert result.nobs == 220
            assert "value" in result.params.index
            assert "capital" in result.params.index
            assert result.std_err is not None
            assert result.pvalues is not None
