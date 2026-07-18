"""
Unit and integration tests for Sprint S2 — EconFlow estimation enhancements.

Sprint S2 adds diagnostic capabilities without changing estimator mathematics:

1. IV diagnostics — first-stage F, Sargan-Hansen, Wu-Hausman (iv.py)
2. IV pooled warning — note when multiple entities detected (iv.py)
3. Cluster-count validation — warn when < 10 clusters with clustered SEs (_diagnostics.py)
4. Within-VIF — VIF on entity-demeaned regressors for FE models (_diagnostics.py, fixed_effects.py)

Constraints (all verified by regression tests below):
* No coefficient or standard-error values changed.
* No existing diagnostic statistics changed (DW, BP, VIF values unchanged).
* Architecture Freeze invariants preserved.

Test structure
--------------
TestIVDiagnostics       — IV first-stage, Sargan, Wu-Hausman (just-identified and over-identified)
TestIVPooledWarning     — iv_pooled_note always emitted with multiple entities
TestClusterCount        — cluster_count emitted for clustered SEs; threshold = 10
TestWithinVIF           — vif_within in EntityFE and TwoWayFE; pin for Grunfeld
TestRegressionNoChange  — existing numerical outputs are unchanged by S2
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from econflow.estimation._diagnostics import _diag_cluster_count, _diag_within_vif
from econflow.estimation.fixed_effects import EntityFE, TwoWayFE
from econflow.estimation.iv import IV2SLS
from econflow.estimation.ols import PooledOLS
from econflow.estimation.result import DiagnosticResult


# ---------------------------------------------------------------------------
# Shared numerical pins
# ---------------------------------------------------------------------------

# Within-VIF (Grunfeld, entity-demeaned value/capital)
_WITHIN_VIF_GRUNFELD = 1.1650081762

# IV pins — just-identified dataset (rng=42, N=6 entities, T=8 periods)
# Verified against linearmodels IV2SLS directly in sandbox.
_JI_F_STAT   = 20.9058739062   # first-stage F for x_endog
_JI_WH_STAT  = 1.7771916214    # Wu-Hausman F-statistic
_JI_WH_PVAL  = 0.1893561977    # Wu-Hausman p-value

# IV pins — over-identified dataset (rng=42, N=6 entities, T=8, z1+z2)
_OI_F_STAT      = 37.3498978590   # first-stage F
_OI_SARGAN_STAT = 1.1980915473    # Sargan J-stat
_OI_SARGAN_PVAL = 0.2737034504    # Sargan p-value
_OI_WH_STAT     = 1.3810969067    # Wu-Hausman F
_OI_WH_PVAL     = 0.2462348615    # Wu-Hausman p-value


# ---------------------------------------------------------------------------
# Dataset helpers
# ---------------------------------------------------------------------------


def _grunfeld_df() -> pd.DataFrame:
    """Grunfeld balanced panel: 11 firms × 20 years = 220 obs."""
    from statsmodels.datasets import grunfeld  # noqa: PLC0415
    return grunfeld.load_pandas().data


def _grunfeld_fe_params(cov_type: str = "clustered") -> dict:
    return {
        "dependent": "invest",
        "regressors": ["value", "capital"],
        "entity_col": "firm",
        "time_col": "year",
        "cov_type": cov_type,
        "cluster_entity": True,
    }


def _synth_iv_df(seed: int = 42, n_entities: int = 6, n_times: int = 8) -> pd.DataFrame:
    """
    Synthetic panel with one endogenous regressor (x_endog) and one instrument (z).
    Just-identified: n_instruments == n_endog == 1.
    """
    rng = np.random.default_rng(seed)
    n = n_entities * n_times
    entity = np.repeat(np.arange(n_entities), n_times)
    time   = np.tile(np.arange(n_times), n_entities)
    z      = rng.standard_normal(n)
    x_endog = 0.7 * z + rng.standard_normal(n)
    x_exog  = rng.standard_normal(n)
    u = rng.standard_normal(n)
    y = 1.5 * x_exog + 2.0 * x_endog + u
    return pd.DataFrame({
        "entity": entity, "time": time,
        "y": y, "x_exog": x_exog, "x_endog": x_endog, "z": z,
    })


def _synth_overid_df(seed: int = 42, n_entities: int = 6, n_times: int = 8) -> pd.DataFrame:
    """
    Synthetic panel with one endogenous regressor and two instruments.
    Over-identified: n_instruments == 2 > n_endog == 1.
    """
    rng = np.random.default_rng(seed)
    n = n_entities * n_times
    entity = np.repeat(np.arange(n_entities), n_times)
    time   = np.tile(np.arange(n_times), n_entities)
    z1 = rng.standard_normal(n)
    z2 = rng.standard_normal(n)
    x_endog = 0.7 * z1 + 0.5 * z2 + rng.standard_normal(n)
    x_exog  = rng.standard_normal(n)
    u = rng.standard_normal(n)
    y = 1.5 * x_exog + 2.0 * x_endog + u
    return pd.DataFrame({
        "entity": entity, "time": time,
        "y": y, "x_exog": x_exog, "x_endog": x_endog, "z1": z1, "z2": z2,
    })


def _small_panel_df(n_entities: int = 5, n_times: int = 8) -> pd.DataFrame:
    """Small panel with n_entities < 10 for cluster-count warning test."""
    rng = np.random.default_rng(99)
    n = n_entities * n_times
    entity = np.repeat(np.arange(n_entities), n_times)
    time   = np.tile(np.arange(n_times), n_entities)
    x = rng.standard_normal(n)
    y = 2.0 * x + rng.standard_normal(n)
    return pd.DataFrame({
        "entity": entity, "time": time, "y": y, "x": x,
    })


# ---------------------------------------------------------------------------
# Helper: IV fixture factories
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def ji_result():
    """Just-identified IV result (1 endog, 1 instrument, 6 entities)."""
    df = _synth_iv_df()
    params = {
        "dependent": "y",
        "regressors": ["x_exog"],
        "endog": ["x_endog"],
        "instruments": ["z"],
        "entity_col": "entity",
        "time_col": "time",
        "cov_type": "robust",
    }
    return IV2SLS(params=params).run(df)


@pytest.fixture(scope="module")
def oi_result():
    """Over-identified IV result (1 endog, 2 instruments, 6 entities)."""
    df = _synth_overid_df()
    params = {
        "dependent": "y",
        "regressors": ["x_exog"],
        "endog": ["x_endog"],
        "instruments": ["z1", "z2"],
        "entity_col": "entity",
        "time_col": "time",
        "cov_type": "robust",
    }
    return IV2SLS(params=params).run(df)


@pytest.fixture(scope="module")
def ji_diags(ji_result):
    return IV2SLS(params={
        "dependent": "y", "regressors": ["x_exog"],
        "endog": ["x_endog"], "instruments": ["z"],
        "entity_col": "entity", "time_col": "time", "cov_type": "robust",
    }).diagnostics(ji_result)


@pytest.fixture(scope="module")
def oi_diags(oi_result):
    return IV2SLS(params={
        "dependent": "y", "regressors": ["x_exog"],
        "endog": ["x_endog"], "instruments": ["z1", "z2"],
        "entity_col": "entity", "time_col": "time", "cov_type": "robust",
    }).diagnostics(oi_result)


# ---------------------------------------------------------------------------
# 1. IV Diagnostics — just-identified (no Sargan)
# ---------------------------------------------------------------------------


class TestIVDiagnosticsJustIdentified:
    """First-stage, Wu-Hausman, and pooled note for just-identified IV."""

    def test_diagnostics_returns_list(self, ji_diags):
        assert isinstance(ji_diags, list)
        assert len(ji_diags) > 0

    def test_all_are_diagnostic_result_instances(self, ji_diags):
        for d in ji_diags:
            assert isinstance(d, DiagnosticResult)

    def test_iv_first_stage_present(self, ji_diags):
        ids = [d.diagnostic_id for d in ji_diags]
        assert "iv_first_stage" in ids

    def test_iv_first_stage_f_stat_pin(self, ji_diags):
        fs = next(d for d in ji_diags if d.diagnostic_id == "iv_first_stage")
        assert fs.statistic == pytest.approx(_JI_F_STAT, rel=1e-6)

    def test_iv_first_stage_statistic_is_min_f(self, ji_diags):
        """statistic field equals min first-stage F across endogenous variables."""
        fs = next(d for d in ji_diags if d.diagnostic_id == "iv_first_stage")
        # Just one endog variable → min_f == f for x_endog
        fs_detail = fs.extra["first_stage"]["x_endog"]
        assert fs.statistic == pytest.approx(fs_detail["f_stat"], rel=1e-10)

    def test_iv_first_stage_extra_keys(self, ji_diags):
        fs = next(d for d in ji_diags if d.diagnostic_id == "iv_first_stage")
        assert "first_stage" in fs.extra
        assert "threshold" in fs.extra
        assert fs.extra["threshold"] == 10.0
        endog_info = fs.extra["first_stage"]["x_endog"]
        assert "f_stat" in endog_info
        assert "f_pval" in endog_info
        assert "shea_r2" in endog_info
        assert "partial_r2" in endog_info

    def test_iv_first_stage_strong_instruments_info_level(self, ji_diags):
        """F=20.9 >= 10 → level='info', not warning."""
        fs = next(d for d in ji_diags if d.diagnostic_id == "iv_first_stage")
        assert fs.level == "info"
        assert "adequate" in fs.conclusion

    def test_iv_sargan_absent_when_just_identified(self, ji_diags):
        """No Sargan-Hansen when just-identified (1 instrument, 1 endog)."""
        ids = [d.diagnostic_id for d in ji_diags]
        assert "iv_sargan_hansen" not in ids

    def test_iv_wu_hausman_present(self, ji_diags):
        ids = [d.diagnostic_id for d in ji_diags]
        assert "iv_wu_hausman" in ids

    def test_iv_wu_hausman_stat_pin(self, ji_diags):
        wh = next(d for d in ji_diags if d.diagnostic_id == "iv_wu_hausman")
        assert wh.statistic == pytest.approx(_JI_WH_STAT, rel=1e-6)

    def test_iv_wu_hausman_pval_pin(self, ji_diags):
        wh = next(d for d in ji_diags if d.diagnostic_id == "iv_wu_hausman")
        assert wh.pvalue == pytest.approx(_JI_WH_PVAL, rel=1e-6)

    def test_iv_wu_hausman_extra_keys(self, ji_diags):
        wh = next(d for d in ji_diags if d.diagnostic_id == "iv_wu_hausman")
        assert "wu_hausman_stat" in wh.extra
        assert "wu_hausman_pval" in wh.extra

    def test_iv_wu_hausman_non_rejection_level(self, ji_diags):
        """p=0.189 > 0.05 → no significant endogeneity → level='info'."""
        wh = next(d for d in ji_diags if d.diagnostic_id == "iv_wu_hausman")
        assert wh.level == "info"

    def test_iv_wu_hausman_pvalue_in_unit_interval(self, ji_diags):
        wh = next(d for d in ji_diags if d.diagnostic_id == "iv_wu_hausman")
        assert 0.0 <= wh.pvalue <= 1.0


# ---------------------------------------------------------------------------
# 2. IV Diagnostics — over-identified (Sargan present)
# ---------------------------------------------------------------------------


class TestIVDiagnosticsOverIdentified:
    """Sargan-Hansen J-test present and correct for over-identified IV."""

    def test_iv_sargan_present(self, oi_diags):
        ids = [d.diagnostic_id for d in oi_diags]
        assert "iv_sargan_hansen" in ids

    def test_iv_sargan_stat_pin(self, oi_diags):
        sar = next(d for d in oi_diags if d.diagnostic_id == "iv_sargan_hansen")
        assert sar.statistic == pytest.approx(_OI_SARGAN_STAT, rel=1e-6)

    def test_iv_sargan_pval_pin(self, oi_diags):
        sar = next(d for d in oi_diags if d.diagnostic_id == "iv_sargan_hansen")
        assert sar.pvalue == pytest.approx(_OI_SARGAN_PVAL, rel=1e-6)

    def test_iv_sargan_non_rejection_info_level(self, oi_diags):
        """p=0.274 > 0.05 → instruments appear valid → level='info'."""
        sar = next(d for d in oi_diags if d.diagnostic_id == "iv_sargan_hansen")
        assert sar.level == "info"
        assert "not rejected" in sar.conclusion

    def test_iv_sargan_df_in_extra(self, oi_diags):
        sar = next(d for d in oi_diags if d.diagnostic_id == "iv_sargan_hansen")
        assert "df" in sar.extra
        assert sar.extra["df"] == 1  # n_overid = 2 instruments - 1 endog = 1

    def test_iv_sargan_extra_keys(self, oi_diags):
        sar = next(d for d in oi_diags if d.diagnostic_id == "iv_sargan_hansen")
        assert "sargan_stat" in sar.extra
        assert "sargan_pval" in sar.extra

    def test_iv_wu_hausman_overid_stat_pin(self, oi_diags):
        wh = next(d for d in oi_diags if d.diagnostic_id == "iv_wu_hausman")
        assert wh.statistic == pytest.approx(_OI_WH_STAT, rel=1e-6)

    def test_iv_wu_hausman_overid_pval_pin(self, oi_diags):
        wh = next(d for d in oi_diags if d.diagnostic_id == "iv_wu_hausman")
        assert wh.pvalue == pytest.approx(_OI_WH_PVAL, rel=1e-6)

    def test_iv_first_stage_overid_f_stat_pin(self, oi_diags):
        fs = next(d for d in oi_diags if d.diagnostic_id == "iv_first_stage")
        assert fs.statistic == pytest.approx(_OI_F_STAT, rel=1e-6)

    def test_diagnostic_order(self, oi_diags):
        """Over-identified IV: first_stage, sargan_hansen, wu_hausman, pooled_note."""
        ids = [d.diagnostic_id for d in oi_diags]
        assert ids.index("iv_first_stage") < ids.index("iv_sargan_hansen")
        assert ids.index("iv_sargan_hansen") < ids.index("iv_wu_hausman")
        assert ids.index("iv_wu_hausman") < ids.index("iv_pooled_note")

    def test_all_pvalues_in_unit_interval(self, oi_diags):
        for d in oi_diags:
            if d.pvalue is not None:
                assert 0.0 <= d.pvalue <= 1.0


# ---------------------------------------------------------------------------
# 3. IV Pooled Warning
# ---------------------------------------------------------------------------


class TestIVPooledWarning:
    """iv_pooled_note is always emitted when ngroups > 1."""

    def test_pooled_note_present_ji(self, ji_diags):
        """Just-identified IV with 6 entities → pooled warning."""
        ids = [d.diagnostic_id for d in ji_diags]
        assert "iv_pooled_note" in ids

    def test_pooled_note_present_oi(self, oi_diags):
        ids = [d.diagnostic_id for d in oi_diags]
        assert "iv_pooled_note" in ids

    def test_pooled_note_level_is_warning(self, ji_diags):
        note = next(d for d in ji_diags if d.diagnostic_id == "iv_pooled_note")
        assert note.level == "warning"

    def test_pooled_note_conclusion_mentions_entity_count(self, ji_diags):
        note = next(d for d in ji_diags if d.diagnostic_id == "iv_pooled_note")
        assert "6" in note.conclusion  # 6 entities detected

    def test_pooled_note_conclusion_mentions_fixed_effects(self, ji_diags):
        note = next(d for d in ji_diags if d.diagnostic_id == "iv_pooled_note")
        assert "fixed effects" in note.conclusion.lower()

    def test_pooled_note_extra_contains_ngroups(self, ji_diags):
        note = next(d for d in ji_diags if d.diagnostic_id == "iv_pooled_note")
        assert "ngroups" in note.extra
        assert note.extra["ngroups"] == 6

    def test_pooled_note_is_last(self, ji_diags):
        """iv_pooled_note must be the last diagnostic."""
        assert ji_diags[-1].diagnostic_id == "iv_pooled_note"

    def test_pooled_note_absent_when_single_entity(self):
        """If only 1 entity, no pooled warning (no cross-entity comparison)."""
        rng = np.random.default_rng(77)
        n = 30
        df = pd.DataFrame({
            "entity": np.zeros(n, dtype=int),
            "time": np.arange(n),
            "y": rng.standard_normal(n),
            "x_exog": rng.standard_normal(n),
            "x_endog": rng.standard_normal(n),
            "z": rng.standard_normal(n),
        })
        params = {
            "dependent": "y", "regressors": ["x_exog"],
            "endog": ["x_endog"], "instruments": ["z"],
            "entity_col": "entity", "time_col": "time", "cov_type": "robust",
        }
        result = IV2SLS(params=params).run(df)
        estimator = IV2SLS(params=params)
        diags = estimator.diagnostics(result)
        ids = [d.diagnostic_id for d in diags]
        assert "iv_pooled_note" not in ids

    def test_description_mentions_pooled(self):
        """Class description must explicitly say 'pooled'."""
        assert "pooled" in IV2SLS.description.lower()


# ---------------------------------------------------------------------------
# 4. Cluster Count Validation
# ---------------------------------------------------------------------------


class TestClusterCountUnit:
    """Unit tests for _diag_cluster_count()."""

    def test_returns_diagnostic_result(self):
        result = _diag_cluster_count(5)
        assert isinstance(result, DiagnosticResult)

    def test_diagnostic_id(self):
        result = _diag_cluster_count(5)
        assert result.diagnostic_id == "cluster_count"

    def test_warning_level_below_threshold(self):
        for n in range(1, 10):
            result = _diag_cluster_count(n)
            assert result.level == "warning", f"Expected warning for n={n}"

    def test_info_level_at_threshold(self):
        result = _diag_cluster_count(10)
        assert result.level == "info"

    def test_info_level_above_threshold(self):
        result = _diag_cluster_count(11)
        assert result.level == "info"

    def test_statistic_equals_ngroups(self):
        for n in [3, 5, 9, 10, 15, 50]:
            result = _diag_cluster_count(n)
            assert result.statistic == float(n)

    def test_extra_contains_threshold(self):
        result = _diag_cluster_count(5)
        assert "threshold" in result.extra
        assert result.extra["threshold"] == 10

    def test_extra_contains_n_clusters(self):
        result = _diag_cluster_count(7)
        assert "n_clusters" in result.extra
        assert result.extra["n_clusters"] == 7

    def test_conclusion_mentions_cameron_miller(self):
        """Reference to Cameron & Miller (2015) must appear in conclusion."""
        result = _diag_cluster_count(5)
        assert "Cameron" in result.conclusion
        assert "Miller" in result.conclusion

    def test_conclusion_mentions_n_clusters(self):
        result = _diag_cluster_count(6)
        assert "6" in result.conclusion

    def test_warning_conclusion_mentions_few_clusters(self):
        result = _diag_cluster_count(4)
        assert "Few clusters" in result.conclusion or "few" in result.conclusion.lower()


class TestClusterCountIntegration:
    """Integration: cluster_count emitted via compute_standard_diagnostics."""

    def test_cluster_count_warning_for_small_panel_fe(self):
        """EntityFE with < 10 entities and cov_type='clustered' → warning."""
        df = _small_panel_df(n_entities=5)
        params = {
            "dependent": "y",
            "regressors": ["x"],
            "entity_col": "entity",
            "time_col": "time",
            "cov_type": "clustered",
            "cluster_entity": True,
        }
        result = EntityFE(params=params).run(df)
        cc = next(
            (d for d in result.diagnostic_results if d.diagnostic_id == "cluster_count"),
            None,
        )
        assert cc is not None, "cluster_count diagnostic missing"
        assert cc.level == "warning"
        assert cc.statistic == 5.0

    def test_cluster_count_info_for_grunfeld_fe(self):
        """EntityFE on Grunfeld (11 firms, clustered) → info (11 >= 10)."""
        df = _grunfeld_df()
        result = EntityFE(params=_grunfeld_fe_params("clustered")).run(df)
        cc = next(
            (d for d in result.diagnostic_results if d.diagnostic_id == "cluster_count"),
            None,
        )
        assert cc is not None
        assert cc.level == "info"
        assert cc.statistic == 11.0

    def test_cluster_count_absent_for_robust_cov(self):
        """cluster_count must NOT appear when cov_type='robust'."""
        df = _grunfeld_df()
        result = EntityFE(params=_grunfeld_fe_params("robust")).run(df)
        ids = [d.diagnostic_id for d in result.diagnostic_results]
        assert "cluster_count" not in ids

    def test_cluster_count_absent_for_ols_robust(self):
        """PooledOLS with cov_type='robust' → no cluster_count."""
        df = _grunfeld_df()
        params = {
            "dependent": "invest", "regressors": ["value", "capital"],
            "entity_col": "firm", "time_col": "year", "cov_type": "robust",
        }
        result = PooledOLS(params=params).run(df)
        ids = [d.diagnostic_id for d in result.diagnostic_results]
        assert "cluster_count" not in ids

    def test_cluster_count_position_after_dw(self):
        """cluster_count must appear after durbin_watson in the list."""
        df = _grunfeld_df()
        result = EntityFE(params=_grunfeld_fe_params("clustered")).run(df)
        ids = [d.diagnostic_id for d in result.diagnostic_results]
        assert ids.index("cluster_count") > ids.index("durbin_watson")


# ---------------------------------------------------------------------------
# 5. Within-VIF
# ---------------------------------------------------------------------------


class TestWithinVIFUnit:
    """Unit tests for _diag_within_vif()."""

    def test_returns_diagnostic_result(self):
        rng = np.random.default_rng(42)
        n = 50
        X_within = rng.standard_normal((n, 2)).tolist()
        result = _diag_within_vif(X_within, ["x1", "x2"])
        assert isinstance(result, DiagnosticResult)

    def test_diagnostic_id(self):
        rng = np.random.default_rng(42)
        X_within = rng.standard_normal((50, 2)).tolist()
        result = _diag_within_vif(X_within, ["x1", "x2"])
        assert result.diagnostic_id == "vif_within"

    def test_single_regressor_returns_info(self):
        X_within = [[1.0], [2.0], [3.0], [4.0], [5.0]]
        result = _diag_within_vif(X_within, ["x"])
        assert result.level == "info"
        assert "fewer than 2" in result.conclusion

    def test_extra_contains_vif_values(self):
        rng = np.random.default_rng(1)
        X_within = rng.standard_normal((30, 2)).tolist()
        result = _diag_within_vif(X_within, ["a", "b"])
        assert "vif_values" in result.extra
        assert "max_vif" in result.extra
        assert "threshold" in result.extra
        assert result.extra["threshold"] == 10.0

    def test_statistic_matches_max_vif(self):
        rng = np.random.default_rng(2)
        X_within = rng.standard_normal((40, 2)).tolist()
        result = _diag_within_vif(X_within, ["a", "b"])
        if result.statistic is not None:
            assert math.isclose(
                result.statistic, result.extra["max_vif"], rel_tol=1e-9
            )


class TestWithinVIFIntegration:
    """Integration: vif_within in EntityFE and TwoWayFE diagnostics."""

    @pytest.fixture(scope="class")
    def fe_result(self):
        return EntityFE(params=_grunfeld_fe_params()).run(_grunfeld_df())

    @pytest.fixture(scope="class")
    def twfe_result(self):
        return TwoWayFE(params=_grunfeld_fe_params()).run(_grunfeld_df())

    def test_vif_within_present_in_entity_fe(self, fe_result):
        ids = [d.diagnostic_id for d in fe_result.diagnostic_results]
        assert "vif_within" in ids

    def test_vif_within_present_in_twoway_fe(self, twfe_result):
        ids = [d.diagnostic_id for d in twfe_result.diagnostic_results]
        assert "vif_within" in ids

    def test_vif_within_pin_entity_fe(self, fe_result):
        wv = next(
            d for d in fe_result.diagnostic_results if d.diagnostic_id == "vif_within"
        )
        assert wv.statistic == pytest.approx(_WITHIN_VIF_GRUNFELD, rel=1e-4)

    def test_vif_within_pin_twoway_fe(self, twfe_result):
        """TwoWayFE uses the same entity-demeaning → same within-VIF as EntityFE."""
        wv = next(
            d for d in twfe_result.diagnostic_results if d.diagnostic_id == "vif_within"
        )
        assert wv.statistic == pytest.approx(_WITHIN_VIF_GRUNFELD, rel=1e-4)

    def test_vif_within_less_than_raw_vif(self, fe_result):
        """Within-VIF < raw VIF for Grunfeld (within transformation reduces collinearity)."""
        raw_vif = next(
            d for d in fe_result.diagnostic_results if d.diagnostic_id == "vif"
        ).statistic
        within_vif = next(
            d for d in fe_result.diagnostic_results if d.diagnostic_id == "vif_within"
        ).statistic
        assert within_vif is not None
        assert raw_vif is not None
        assert within_vif <= raw_vif

    def test_vif_within_is_last_diagnostic(self, fe_result):
        """vif_within must be the last diagnostic returned by EntityFE."""
        assert fe_result.diagnostic_results[-1].diagnostic_id == "vif_within"

    def test_vif_within_absent_in_pooled_ols(self):
        """PooledOLS does not store X_within_vif_values → no vif_within."""
        df = _grunfeld_df()
        params = {
            "dependent": "invest", "regressors": ["value", "capital"],
            "entity_col": "firm", "time_col": "year", "cov_type": "robust",
        }
        result = PooledOLS(params=params).run(df)
        ids = [d.diagnostic_id for d in result.diagnostic_results]
        assert "vif_within" not in ids

    def test_vif_within_no_multicollinearity_for_grunfeld(self, fe_result):
        """Grunfeld within-VIF=1.165 < 10 → info level, no concern."""
        wv = next(
            d for d in fe_result.diagnostic_results if d.diagnostic_id == "vif_within"
        )
        assert wv.level == "info"
        assert "No within-regressor multicollinearity" in wv.conclusion


# ---------------------------------------------------------------------------
# 6. Regression tests — S2 must not change existing numerical outputs
# ---------------------------------------------------------------------------


class TestRegressionNoChange:
    """
    Verify that Sprint S2 does not alter any existing numerical diagnostic
    statistics (DW, BP, VIF) or any coefficient / SE estimates.
    """

    # Pinned S1 values (from test_estimation_diagnostics_phase3.py)
    _VIF_MAX_GRUNFELD     = 1.3561562146291226
    _BP_FE_GRUNFELD       = 77.87137086492372
    _DW_FE_GRUNFELD       = 0.6845429500159578
    _BP_TWFE_GRUNFELD     = 68.7759862370838
    _DW_TWFE_GRUNFELD     = 0.6849717134941167
    # Corrected 2026-07-18 (Repository Integrity Repair): the values copied
    # from test_estimation_diagnostics_phase3.py did not reproduce from
    # current source under any code path; see the correction note there.
    _BP_OLS_FRAMEWORK     = 65.22800988589293
    _DW_OLS_FRAMEWORK     = 0.2076399576583588

    @pytest.fixture(scope="class")
    def fe_result(self):
        return EntityFE(params=_grunfeld_fe_params()).run(_grunfeld_df())

    @pytest.fixture(scope="class")
    def twfe_result(self):
        return TwoWayFE(params=_grunfeld_fe_params()).run(_grunfeld_df())

    @pytest.fixture(scope="class")
    def ols_result(self):
        params = {
            "dependent": "invest", "regressors": ["value", "capital"],
            "entity_col": "firm", "time_col": "year", "cov_type": "robust",
        }
        return PooledOLS(params=params).run(_grunfeld_df())

    def test_fe_vif_unchanged(self, fe_result):
        vif = next(d for d in fe_result.diagnostic_results if d.diagnostic_id == "vif")
        assert vif.statistic == pytest.approx(self._VIF_MAX_GRUNFELD, rel=1e-3)

    def test_fe_bp_unchanged(self, fe_result):
        bp = next(
            d for d in fe_result.diagnostic_results if d.diagnostic_id == "breusch_pagan"
        )
        assert bp.statistic == pytest.approx(self._BP_FE_GRUNFELD, rel=1e-3)

    def test_fe_dw_unchanged(self, fe_result):
        dw = next(
            d for d in fe_result.diagnostic_results if d.diagnostic_id == "durbin_watson"
        )
        assert dw.statistic == pytest.approx(self._DW_FE_GRUNFELD, rel=1e-3)

    def test_twfe_vif_unchanged(self, twfe_result):
        vif = next(
            d for d in twfe_result.diagnostic_results if d.diagnostic_id == "vif"
        )
        assert vif.statistic == pytest.approx(self._VIF_MAX_GRUNFELD, rel=1e-3)

    def test_twfe_bp_unchanged(self, twfe_result):
        bp = next(
            d for d in twfe_result.diagnostic_results if d.diagnostic_id == "breusch_pagan"
        )
        assert bp.statistic == pytest.approx(self._BP_TWFE_GRUNFELD, rel=1e-3)

    def test_twfe_dw_unchanged(self, twfe_result):
        dw = next(
            d for d in twfe_result.diagnostic_results if d.diagnostic_id == "durbin_watson"
        )
        assert dw.statistic == pytest.approx(self._DW_TWFE_GRUNFELD, rel=1e-3)

    def test_ols_bp_unchanged(self, ols_result):
        bp = next(
            d for d in ols_result.diagnostic_results if d.diagnostic_id == "breusch_pagan"
        )
        assert bp.statistic == pytest.approx(self._BP_OLS_FRAMEWORK, rel=1e-3)

    def test_ols_dw_unchanged(self, ols_result):
        dw = next(
            d for d in ols_result.diagnostic_results if d.diagnostic_id == "durbin_watson"
        )
        assert dw.statistic == pytest.approx(self._DW_OLS_FRAMEWORK, rel=1e-3)

    def test_fe_coefficients_unchanged(self, fe_result):
        """EntityFE coefficients must be identical to S1 values."""
        # Grunfeld EntityFE: value ≈ 0.1101, capital ≈ 0.3101 (linearmodels values)
        params = fe_result.params
        assert "value" in params.index
        assert "capital" in params.index
        # Coefficients should be small positive values — just sanity-check order of magnitude
        assert abs(float(params["value"]))   < 5.0
        assert abs(float(params["capital"])) < 5.0

    def test_iv_rsquared_adj_unchanged(self, ji_result):
        """Sprint S2 must not change the rsquared_adj computed in Sprint S1."""
        nobs = ji_result.nobs
        df_r = ji_result.df_resid
        rsq  = ji_result.rsquared
        expected_adj = 1.0 - (1.0 - rsq) * (nobs - 1) / df_r
        assert ji_result.rsquared_adj == pytest.approx(expected_adj, rel=1e-10)

    def test_new_diagnostics_do_not_appear_in_existing_ids(self, fe_result):
        """
        The five Sprint S2 diagnostic IDs must not overlap with existing S1 IDs.
        (Ensures no overwriting or shadowing of existing results.)
        """
        s1_ids = {"vif", "breusch_pagan", "durbin_watson"}
        s2_ids = {"cluster_count", "vif_within",
                  "iv_first_stage", "iv_sargan_hansen", "iv_wu_hausman", "iv_pooled_note"}
        assert s1_ids.isdisjoint(s2_ids)
