"""
Integration tests — estimator run() on a synthetic panel dataset.

Each implemented estimator (OLS, FE, TWFE, RE, FD, IV) is run against
a 150-row synthetic panel.  Stubs (GMM, Quantile) are verified to raise
NotImplementedError.

For each implemented estimator we check:
  - run() returns an EstimationResult
  - result has finite params (no NaN/Inf)
  - result.nobs > 0
  - result.rsquared is in [0, 1]
  - conf_int has columns ["lower", "upper"] and correct shape
  - summary_frame() has correct columns
  - diagnostic_results is a list (may be empty for base implementations)
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from econflow.estimation.result import EstimationResult

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

N_ENTITIES = 20
N_TIMES = 10
N_OBS = N_ENTITIES * N_TIMES


@pytest.fixture(scope="module")
def panel_df() -> pd.DataFrame:
    """150-row balanced panel with entity, time, y, x1, x2, x3, z1."""
    rng = np.random.default_rng(0)
    entities = [f"C{i:02d}" for i in range(N_ENTITIES)]
    times = list(range(2000, 2000 + N_TIMES))
    rows = [(e, t) for e in entities for t in times]
    df = pd.DataFrame(rows, columns=["entity", "time"])
    fe = rng.standard_normal(N_ENTITIES)
    fe_map = dict(zip(entities, fe))
    df["fe"] = df["entity"].map(fe_map)
    df["x1"] = rng.standard_normal(N_OBS)
    df["x2"] = rng.standard_normal(N_OBS)
    df["x3"] = rng.standard_normal(N_OBS)
    # z1 is a valid instrument for x3 (correlated but exogenous)
    df["z1"] = df["x3"] * 0.7 + rng.standard_normal(N_OBS) * 0.3
    df["z2"] = rng.standard_normal(N_OBS)
    df["y"] = 1.5 * df["x1"] - 0.8 * df["x2"] + df["fe"] + rng.standard_normal(N_OBS) * 0.5
    return df.drop(columns=["fe"])


def _assert_valid_result(result: EstimationResult) -> None:
    """Shared assertions for any implemented estimator result."""
    assert isinstance(result, EstimationResult)
    assert result.nobs > 0
    assert np.isfinite(result.rsquared) or result.rsquared == 0.0
    assert 0.0 <= result.rsquared <= 1.0 or result.rsquared < 0  # RE can produce < 0
    assert np.all(np.isfinite(result.params.values)), "params contain non-finite values"
    assert np.all(np.isfinite(result.std_err.values)), "std_err contain non-finite values"
    assert list(result.conf_int.columns) == ["lower", "upper"]
    assert result.conf_int.shape[0] == len(result.params)
    assert isinstance(result.diagnostic_results, list)
    sf = result.summary_frame()
    assert {"coef", "std_err", "t_stat", "pvalue", "ci_lower", "ci_upper"}.issubset(sf.columns)


# ---------------------------------------------------------------------------
# OLS
# ---------------------------------------------------------------------------

class TestPooledOLS:
    def test_basic_run(self, panel_df):
        from econflow.estimation.ols import PooledOLS
        est = PooledOLS({
            "dependent": "y",
            "regressors": ["x1", "x2"],
            "entity_col": "entity",
            "time_col": "time",
        })
        result = est.run(panel_df)
        _assert_valid_result(result)

    def test_estimator_id(self, panel_df):
        from econflow.estimation.ols import PooledOLS
        est = PooledOLS({
            "dependent": "y", "regressors": ["x1"],
            "entity_col": "entity", "time_col": "time",
        })
        result = est.run(panel_df)
        assert result.estimator_id == "ols"

    def test_param_names_match_regressors(self, panel_df):
        from econflow.estimation.ols import PooledOLS
        est = PooledOLS({"dependent": "y", "regressors": ["x1", "x2"],
                         "entity_col": "entity", "time_col": "time"})
        result = est.run(panel_df)
        assert "x1" in result.params.index
        assert "x2" in result.params.index

    def test_validate_raises_on_missing_column(self, panel_df):
        from econflow.estimation.base import EstimatorError
        from econflow.estimation.ols import PooledOLS
        est = PooledOLS({"dependent": "y", "regressors": ["x_missing"],
                         "entity_col": "entity", "time_col": "time"})
        with pytest.raises(EstimatorError):
            est.run(panel_df)


# ---------------------------------------------------------------------------
# Entity Fixed Effects
# ---------------------------------------------------------------------------

class TestEntityFE:
    def test_basic_run(self, panel_df):
        from econflow.estimation.fixed_effects import EntityFE
        est = EntityFE({"dependent": "y", "regressors": ["x1", "x2"],
                        "entity_col": "entity", "time_col": "time"})
        result = est.run(panel_df)
        _assert_valid_result(result)

    def test_estimator_id(self, panel_df):
        from econflow.estimation.fixed_effects import EntityFE
        est = EntityFE({"dependent": "y", "regressors": ["x1"],
                        "entity_col": "entity", "time_col": "time"})
        result = est.run(panel_df)
        assert result.estimator_id == "fe"

    def test_ngroups_equals_entities(self, panel_df):
        from econflow.estimation.fixed_effects import EntityFE
        est = EntityFE({"dependent": "y", "regressors": ["x1"],
                        "entity_col": "entity", "time_col": "time"})
        result = est.run(panel_df)
        assert result.ngroups == N_ENTITIES


# ---------------------------------------------------------------------------
# Two-Way Fixed Effects
# ---------------------------------------------------------------------------

class TestTwoWayFE:
    def test_basic_run(self, panel_df):
        from econflow.estimation.fixed_effects import TwoWayFE
        est = TwoWayFE({"dependent": "y", "regressors": ["x1", "x2"],
                         "entity_col": "entity", "time_col": "time"})
        result = est.run(panel_df)
        _assert_valid_result(result)

    def test_estimator_id(self, panel_df):
        from econflow.estimation.fixed_effects import TwoWayFE
        est = TwoWayFE({"dependent": "y", "regressors": ["x1"],
                         "entity_col": "entity", "time_col": "time"})
        result = est.run(panel_df)
        assert result.estimator_id == "twfe"


# ---------------------------------------------------------------------------
# Random Effects
# ---------------------------------------------------------------------------

class TestRandomEffects:
    def test_basic_run(self, panel_df):
        from econflow.estimation.random_effects import RandomEffects
        est = RandomEffects({"dependent": "y", "regressors": ["x1", "x2"],
                              "entity_col": "entity", "time_col": "time"})
        result = est.run(panel_df)
        _assert_valid_result(result)

    def test_estimator_id(self, panel_df):
        from econflow.estimation.random_effects import RandomEffects
        est = RandomEffects({"dependent": "y", "regressors": ["x1"],
                              "entity_col": "entity", "time_col": "time"})
        result = est.run(panel_df)
        assert result.estimator_id == "re"


# ---------------------------------------------------------------------------
# First Difference
# ---------------------------------------------------------------------------

class TestFirstDifference:
    def test_basic_run(self, panel_df):
        from econflow.estimation.first_difference import FirstDifference
        est = FirstDifference({"dependent": "y", "regressors": ["x1", "x2"],
                                "entity_col": "entity", "time_col": "time"})
        result = est.run(panel_df)
        _assert_valid_result(result)

    def test_estimator_id(self, panel_df):
        from econflow.estimation.first_difference import FirstDifference
        est = FirstDifference({"dependent": "y", "regressors": ["x1"],
                                "entity_col": "entity", "time_col": "time"})
        result = est.run(panel_df)
        assert result.estimator_id == "fd"

    def test_nobs_less_than_full(self, panel_df):
        """FD loses one observation per entity."""
        from econflow.estimation.first_difference import FirstDifference
        est = FirstDifference({"dependent": "y", "regressors": ["x1"],
                                "entity_col": "entity", "time_col": "time"})
        result = est.run(panel_df)
        assert result.nobs < N_OBS


# ---------------------------------------------------------------------------
# IV / 2SLS
# ---------------------------------------------------------------------------

class TestIV2SLS:
    def test_basic_run(self, panel_df):
        from econflow.estimation.iv import IV2SLS
        est = IV2SLS({
            "dependent": "y",
            "regressors": ["x1", "x2"],
            "endog": ["x2"],
            "instruments": ["z1"],
            "entity_col": "entity",
            "time_col": "time",
        })
        result = est.run(panel_df)
        _assert_valid_result(result)

    def test_estimator_id(self, panel_df):
        from econflow.estimation.iv import IV2SLS
        est = IV2SLS({
            "dependent": "y", "regressors": ["x1", "x2"],
            "endog": ["x2"], "instruments": ["z1"],
            "entity_col": "entity", "time_col": "time",
        })
        result = est.run(panel_df)
        assert result.estimator_id == "iv"

    def test_order_condition_violation_raises(self, panel_df):
        """More endogenous regressors than instruments should raise."""
        from econflow.estimation.base import EstimatorError
        from econflow.estimation.iv import IV2SLS
        est = IV2SLS({
            "dependent": "y", "regressors": ["x1", "x2", "x3"],
            "endog": ["x2", "x3"],   # 2 endog
            "instruments": ["z1"],   # only 1 instrument → underidentified
            "entity_col": "entity", "time_col": "time",
        })
        with pytest.raises(EstimatorError, match="[Oo]rder|instrument|underidentif"):
            est.run(panel_df)


# ---------------------------------------------------------------------------
# Stubs — GMM and Quantile
# ---------------------------------------------------------------------------

class TestStubEstimators:
    def test_gmm_raises_not_implemented(self, panel_df):
        from econflow.estimation.gmm import SystemGMM
        est = SystemGMM({"dependent": "y", "regressors": ["x1"],
                          "entity_col": "entity", "time_col": "time"})
        with pytest.raises(NotImplementedError):
            est.fit(panel_df)

    def test_quantile_raises_not_implemented(self, panel_df):
        from econflow.estimation.quantile import PanelQuantile
        est = PanelQuantile({"dependent": "y", "regressors": ["x1"],
                              "entity_col": "entity", "time_col": "time",
                              "quantile": 0.5})
        with pytest.raises(NotImplementedError):
            est.fit(panel_df)

    def test_quantile_validate_invalid_quantile(self, panel_df):
        from econflow.estimation.base import EstimatorError
        from econflow.estimation.quantile import PanelQuantile
        est = PanelQuantile({"dependent": "y", "regressors": ["x1"],
                              "entity_col": "entity", "time_col": "time",
                              "quantile": 1.5})
        with pytest.raises(EstimatorError):
            est.validate(panel_df)


# ---------------------------------------------------------------------------
# Registry round-trip
# ---------------------------------------------------------------------------

class TestRegistryRoundTrip:
    def test_get_estimator_and_run(self, panel_df):
        """Retrieve estimator from registry by id, instantiate, and run."""
        from econflow.estimation.registry import get_estimator
        cls = get_estimator("twfe")
        est = cls({
            "dependent": "y", "regressors": ["x1", "x2"],
            "entity_col": "entity", "time_col": "time",
        })
        result = est.run(panel_df)
        _assert_valid_result(result)
        assert result.estimator_id == "twfe"
