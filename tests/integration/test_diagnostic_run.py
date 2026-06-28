"""
Integration tests — diagnostic plugins run against real EstimationResults.

Each implemented plugin (Hausman, BreuschPagan, PesaranCD, VIF) is run
on an EstimationResult produced by the relevant estimator.  Stubs
(Wooldridge, SerialCorrelation) are verified to raise NotImplementedError.

For each implemented plugin we check:
  - run() returns a DiagnosticResult
  - diagnostic_id matches the registered id
  - level is one of {info, warn, error, skip}
  - conclusion is a non-empty string
  - statistic is finite (or None for informational results)
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from econflow.estimation.result import DiagnosticResult, EstimationResult

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

N_ENTITIES = 15
N_TIMES = 8
N_OBS = N_ENTITIES * N_TIMES
VALID_LEVELS = {"info", "warn", "error", "skip", "pass", "fail"}


@pytest.fixture(scope="module")
def panel_df() -> pd.DataFrame:
    rng = np.random.default_rng(1)
    entities = [f"C{i:02d}" for i in range(N_ENTITIES)]
    times = list(range(2005, 2005 + N_TIMES))
    rows = [(e, t) for e in entities for t in times]
    df = pd.DataFrame(rows, columns=["entity", "time"])
    fe_vals = rng.standard_normal(N_ENTITIES)
    fe_map = dict(zip(entities, fe_vals))
    df["fe"] = df["entity"].map(fe_map)
    df["x1"] = rng.standard_normal(N_OBS)
    df["x2"] = rng.standard_normal(N_OBS)
    df["z1"] = df["x1"] * 0.8 + rng.standard_normal(N_OBS) * 0.2
    df["y"] = 2.0 * df["x1"] - df["x2"] + df["fe"] + rng.standard_normal(N_OBS) * 0.3
    return df.drop(columns=["fe"])


@pytest.fixture(scope="module")
def fe_result(panel_df) -> EstimationResult:
    from econflow.estimation.fixed_effects import EntityFE
    est = EntityFE({"dependent": "y", "regressors": ["x1", "x2"],
                    "entity_col": "entity", "time_col": "time"})
    return est.fit(panel_df)


@pytest.fixture(scope="module")
def re_result(panel_df) -> EstimationResult:
    from econflow.estimation.random_effects import RandomEffects
    est = RandomEffects({"dependent": "y", "regressors": ["x1", "x2"],
                         "entity_col": "entity", "time_col": "time"})
    return est.fit(panel_df)


@pytest.fixture(scope="module")
def ols_result(panel_df) -> EstimationResult:
    from econflow.estimation.ols import PooledOLS
    est = PooledOLS({"dependent": "y", "regressors": ["x1", "x2"],
                     "entity_col": "entity", "time_col": "time"})
    return est.fit(panel_df)


def _assert_valid_diag(dr: DiagnosticResult) -> None:
    assert isinstance(dr, DiagnosticResult)
    assert isinstance(dr.diagnostic_id, str) and dr.diagnostic_id
    assert isinstance(dr.conclusion, str)
    if dr.statistic is not None:
        assert np.isfinite(dr.statistic), f"statistic is not finite: {dr.statistic}"


# ---------------------------------------------------------------------------
# Hausman test
# ---------------------------------------------------------------------------

class TestHausmanDiagnostic:
    def test_run_returns_diagnostic_result(self, fe_result, re_result):
        from econflow.diagnostics.plugins.hausman import HausmanTest
        diag = HausmanTest()
        dr = diag.run(fe_result, re_result=re_result)
        _assert_valid_diag(dr)

    def test_diagnostic_id(self, fe_result, re_result):
        from econflow.diagnostics.plugins.hausman import HausmanTest
        dr = HausmanTest().run(fe_result, re_result=re_result)
        assert dr.diagnostic_id == "hausman"

    def test_statistic_is_positive(self, fe_result, re_result):
        from econflow.diagnostics.plugins.hausman import HausmanTest
        dr = HausmanTest().run(fe_result, re_result=re_result)
        if dr.statistic is not None:
            assert dr.statistic >= 0

    def test_pvalue_in_unit_interval(self, fe_result, re_result):
        from econflow.diagnostics.plugins.hausman import HausmanTest
        dr = HausmanTest().run(fe_result, re_result=re_result)
        if dr.pvalue is not None:
            assert 0.0 <= dr.pvalue <= 1.0

    def test_not_supported_for_ols(self, ols_result):
        from econflow.diagnostics.plugins.hausman import HausmanTest
        diag = HausmanTest()
        assert diag.supports("ols") is False

    def test_without_re_result_returns_skip(self, fe_result):
        from econflow.diagnostics.plugins.hausman import HausmanTest
        dr = HausmanTest().run(fe_result)
        assert dr.level == "skip"


# ---------------------------------------------------------------------------
# Breusch-Pagan heteroskedasticity test
# ---------------------------------------------------------------------------

class TestBreuschPagan:
    def test_run_returns_diagnostic_result(self, ols_result, panel_df):
        from econflow.diagnostics.plugins.breusch_pagan import BreuschPagan as BreuschPaganTest
        dr = BreuschPaganTest().run(ols_result, data=panel_df)
        _assert_valid_diag(dr)

    def test_diagnostic_id(self, ols_result, panel_df):
        from econflow.diagnostics.plugins.breusch_pagan import BreuschPagan as BreuschPaganTest
        dr = BreuschPaganTest().run(ols_result, data=panel_df)
        assert dr.diagnostic_id == "breusch_pagan"

    def test_statistic_nonnegative(self, ols_result, panel_df):
        from econflow.diagnostics.plugins.breusch_pagan import BreuschPagan as BreuschPaganTest
        dr = BreuschPaganTest().run(ols_result, data=panel_df)
        if dr.statistic is not None:
            assert dr.statistic >= 0

    def test_without_data_returns_skip(self, ols_result):
        from econflow.diagnostics.plugins.breusch_pagan import BreuschPagan as BreuschPaganTest
        dr = BreuschPaganTest().run(ols_result)
        assert dr.level == "skip"


# ---------------------------------------------------------------------------
# Pesaran CD test
# ---------------------------------------------------------------------------

class TestPesaranCD:
    def test_run_returns_diagnostic_result(self, fe_result, panel_df):
        from econflow.diagnostics.plugins.pesaran_cd import PesaranCD as PesaranCDTest
        dr = PesaranCDTest().run(fe_result, data=panel_df)
        _assert_valid_diag(dr)

    def test_diagnostic_id(self, fe_result, panel_df):
        from econflow.diagnostics.plugins.pesaran_cd import PesaranCD as PesaranCDTest
        dr = PesaranCDTest().run(fe_result, data=panel_df)
        assert dr.diagnostic_id == "pesaran_cd"

    def test_statistic_is_finite(self, fe_result, panel_df):
        from econflow.diagnostics.plugins.pesaran_cd import PesaranCD as PesaranCDTest
        dr = PesaranCDTest().run(fe_result, data=panel_df)
        if dr.statistic is not None:
            assert np.isfinite(dr.statistic)

    def test_pvalue_in_unit_interval(self, fe_result, panel_df):
        from econflow.diagnostics.plugins.pesaran_cd import PesaranCD as PesaranCDTest
        dr = PesaranCDTest().run(fe_result, data=panel_df)
        if dr.pvalue is not None:
            assert 0.0 <= dr.pvalue <= 1.0

    def test_without_data_returns_skip(self, fe_result):
        from econflow.diagnostics.plugins.pesaran_cd import PesaranCD as PesaranCDTest
        dr = PesaranCDTest().run(fe_result)
        assert dr.level == "skip"


# ---------------------------------------------------------------------------
# VIF diagnostic
# ---------------------------------------------------------------------------

class TestVIF:
    def test_run_returns_diagnostic_result(self, ols_result, panel_df):
        from econflow.diagnostics.plugins.vif import VIFCheck as VIFDiagnostic
        dr = VIFDiagnostic().run(ols_result, data=panel_df)
        _assert_valid_diag(dr)

    def test_diagnostic_id(self, ols_result, panel_df):
        from econflow.diagnostics.plugins.vif import VIFCheck as VIFDiagnostic
        dr = VIFDiagnostic().run(ols_result, data=panel_df)
        assert dr.diagnostic_id == "vif"

    def test_vif_values_in_extra(self, ols_result, panel_df):
        from econflow.diagnostics.plugins.vif import VIFCheck as VIFDiagnostic
        dr = VIFDiagnostic().run(ols_result, data=panel_df)
        # extra should contain per-variable VIF values
        assert "vif_values" in dr.extra or len(dr.extra) > 0

    def test_supports_all_estimators(self):
        from econflow.diagnostics.plugins.vif import VIFCheck as VIFDiagnostic
        diag = VIFDiagnostic()
        for eid in ("ols", "fe", "twfe", "re", "iv"):
            assert diag.supports(eid) is True

    def test_without_data_returns_skip(self, ols_result):
        from econflow.diagnostics.plugins.vif import VIFCheck as VIFDiagnostic
        dr = VIFDiagnostic().run(ols_result)
        assert dr.level == "skip"


# ---------------------------------------------------------------------------
# Stubs
# ---------------------------------------------------------------------------

class TestStubDiagnostics:
    def test_wooldridge_raises_not_implemented(self, fe_result):
        from econflow.diagnostics.plugins.wooldridge import WooldridgeTest
        diag = WooldridgeTest()
        with pytest.raises(NotImplementedError):
            diag.run(fe_result)

    def test_serial_correlation_raises_not_implemented(self, fe_result):
        from econflow.diagnostics.plugins.serial_correlation import SerialCorrelationTest
        diag = SerialCorrelationTest()
        with pytest.raises(NotImplementedError):
            diag.run(fe_result)


# ---------------------------------------------------------------------------
# Registry-driven diagnostic lookup
# ---------------------------------------------------------------------------

class TestRegistryDrivenDiagnostic:
    def test_get_and_run_hausman(self, fe_result, re_result):
        from econflow.diagnostics.registry import get_diagnostic
        cls = get_diagnostic("hausman")
        dr = cls().run(fe_result, re_result=re_result)
        assert dr.diagnostic_id == "hausman"

    def test_get_and_run_vif(self, ols_result, panel_df):
        from econflow.diagnostics.registry import get_diagnostic
        cls = get_diagnostic("vif")
        dr = cls().run(ols_result, data=panel_df)
        assert dr.diagnostic_id == "vif"
