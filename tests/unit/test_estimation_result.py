"""
Unit tests for econflow.estimation.result.

Coverage targets
----------------
DiagnosticResult
    - construction with required fields only
    - construction with all optional fields
    - to_dict() round-trip
    - to_json() / from_dict() round-trip
    - level validation is unrestricted (accepts any string)

EstimationResult
    - construction with required fields
    - tvalues property
    - summary_frame() columns and dtypes
    - to_dict() contains expected keys
    - to_json() / from_dict() round-trip preserves numeric values
    - diagnostic_results list is mutable
    - warnings list is mutable
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest

from econflow.estimation.result import DiagnosticResult, EstimationResult

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def diag_minimal() -> DiagnosticResult:
    return DiagnosticResult(
        diagnostic_id="hausman",
        diagnostic_name="Hausman Test",
    )


@pytest.fixture()
def diag_full() -> DiagnosticResult:
    return DiagnosticResult(
        diagnostic_id="breusch_pagan",
        diagnostic_name="Breusch-Pagan LM Test",
        statistic=12.34,
        pvalue=0.001,
        conclusion="Reject H0: heteroskedasticity detected",
        level="warn",
        extra={"lm": 12.34, "df": 3},
    )


def _make_estimation_result(**kwargs) -> EstimationResult:
    """Return a minimal valid EstimationResult."""
    idx = pd.Index(["x1", "x2"])
    defaults = dict(
        estimator_id="fe",
        estimator_name="Fixed Effects",
        params=pd.Series([0.5, -0.3], index=idx),
        std_err=pd.Series([0.1, 0.05], index=idx),
        conf_int=pd.DataFrame(
            {"lower": [0.3, -0.4], "upper": [0.7, -0.2]}, index=idx
        ),
        pvalues=pd.Series([0.001, 0.01], index=idx),
        nobs=150,
        ngroups=25,
        df_resid=123,
        rsquared=0.72,
        rsquared_adj=0.70,
    )
    defaults.update(kwargs)
    return EstimationResult(**defaults)


@pytest.fixture()
def est_result() -> EstimationResult:
    return _make_estimation_result()


# ---------------------------------------------------------------------------
# DiagnosticResult — construction
# ---------------------------------------------------------------------------

class TestDiagnosticResultConstruction:
    def test_required_fields_only(self, diag_minimal):
        assert diag_minimal.diagnostic_id == "hausman"
        assert diag_minimal.diagnostic_name == "Hausman Test"

    def test_defaults(self, diag_minimal):
        assert diag_minimal.statistic is None
        assert diag_minimal.pvalue is None
        assert diag_minimal.conclusion == ""
        assert diag_minimal.level == "info"
        assert diag_minimal.extra == {}

    def test_full_construction(self, diag_full):
        assert diag_full.statistic == pytest.approx(12.34)
        assert diag_full.pvalue == pytest.approx(0.001)
        assert diag_full.level == "warn"
        assert diag_full.extra["df"] == 3

    def test_level_accepts_any_string(self):
        d = DiagnosticResult(diagnostic_id="x", diagnostic_name="X", level="critical")
        assert d.level == "critical"


# ---------------------------------------------------------------------------
# DiagnosticResult — serialization
# ---------------------------------------------------------------------------

class TestDiagnosticResultSerialization:
    def test_to_dict_keys(self, diag_full):
        d = diag_full.to_dict()
        for key in ("diagnostic_id", "diagnostic_name", "statistic", "pvalue",
                    "conclusion", "level", "extra"):
            assert key in d

    def test_to_dict_values(self, diag_full):
        d = diag_full.to_dict()
        assert d["diagnostic_id"] == "breusch_pagan"
        assert d["statistic"] == pytest.approx(12.34)

    def test_to_json_is_valid_json(self, diag_full):
        raw = diag_full.to_json()
        parsed = json.loads(raw)
        assert parsed["diagnostic_id"] == "breusch_pagan"

    def test_from_dict_round_trip(self, diag_full):
        d = diag_full.to_dict()
        restored = DiagnosticResult.from_dict(d)
        assert restored.diagnostic_id == diag_full.diagnostic_id
        assert restored.statistic == pytest.approx(diag_full.statistic)
        assert restored.extra == diag_full.extra

    def test_from_dict_minimal(self):
        d = {"diagnostic_id": "vif", "diagnostic_name": "VIF"}
        restored = DiagnosticResult.from_dict(d)
        assert restored.diagnostic_id == "vif"
        assert restored.statistic is None


# ---------------------------------------------------------------------------
# EstimationResult — construction
# ---------------------------------------------------------------------------

class TestEstimationResultConstruction:
    def test_required_fields(self, est_result):
        assert est_result.estimator_id == "fe"
        assert est_result.nobs == 150
        assert est_result.ngroups == 25

    def test_optional_defaults(self, est_result):
        assert est_result.f_statistic is None
        assert est_result.f_pvalue is None
        assert est_result.entities == []
        assert est_result.time_periods == []
        assert est_result.diagnostic_results == []
        assert est_result.warnings == []
        assert est_result.provenance == {}
        assert est_result.extra == {}

    def test_params_are_series(self, est_result):
        assert isinstance(est_result.params, pd.Series)
        assert list(est_result.params.index) == ["x1", "x2"]

    def test_conf_int_columns(self, est_result):
        assert list(est_result.conf_int.columns) == ["lower", "upper"]


# ---------------------------------------------------------------------------
# EstimationResult — tvalues property
# ---------------------------------------------------------------------------

class TestTValues:
    def test_tvalues_formula(self, est_result):
        tv = est_result.tvalues
        expected = est_result.params / est_result.std_err
        pd.testing.assert_series_equal(tv, expected)

    def test_tvalues_index_matches_params(self, est_result):
        assert list(est_result.tvalues.index) == list(est_result.params.index)


# ---------------------------------------------------------------------------
# EstimationResult — summary_frame
# ---------------------------------------------------------------------------

class TestSummaryFrame:
    def test_columns(self, est_result):
        sf = est_result.summary_frame()
        expected_cols = {"coef", "std_err", "t_stat", "pvalue", "ci_lower", "ci_upper"}
        assert set(sf.columns) == expected_cols

    def test_row_index_matches_params(self, est_result):
        sf = est_result.summary_frame()
        assert list(sf.index) == list(est_result.params.index)

    def test_coef_values(self, est_result):
        sf = est_result.summary_frame()
        pd.testing.assert_series_equal(sf["coef"], est_result.params, check_names=False)

    def test_t_stat_values(self, est_result):
        sf = est_result.summary_frame()
        expected_t = est_result.params / est_result.std_err
        pd.testing.assert_series_equal(sf["t_stat"], expected_t, check_names=False)

    def test_numeric_dtypes(self, est_result):
        sf = est_result.summary_frame()
        for col in sf.columns:
            assert np.issubdtype(sf[col].dtype, np.floating), f"{col} is not float"


# ---------------------------------------------------------------------------
# EstimationResult — serialization
# ---------------------------------------------------------------------------

class TestEstimationResultSerialization:
    def test_to_dict_has_required_keys(self, est_result):
        d = est_result.to_dict()
        for key in ("estimator_id", "estimator_name", "params", "std_err",
                    "pvalues", "nobs", "ngroups", "df_resid",
                    "rsquared", "rsquared_adj"):
            assert key in d, f"Missing key: {key}"

    def test_to_dict_params_serializable(self, est_result):
        d = est_result.to_dict()
        # params should be dict or list (JSON-serializable)
        assert isinstance(d["params"], dict)

    def test_to_json_valid(self, est_result):
        raw = est_result.to_json()
        parsed = json.loads(raw)
        assert parsed["estimator_id"] == "fe"
        assert parsed["nobs"] == 150

    def test_diagnostic_results_in_dict(self):
        dr = DiagnosticResult("hausman", "Hausman", statistic=5.0, pvalue=0.03)
        r = _make_estimation_result(diagnostic_results=[dr])
        d = r.to_dict()
        assert len(d["diagnostic_results"]) == 1
        assert d["diagnostic_results"][0]["diagnostic_id"] == "hausman"

    def test_warnings_in_dict(self):
        r = _make_estimation_result(warnings=["low nobs"])
        d = r.to_dict()
        assert d["warnings"] == ["low nobs"]


# ---------------------------------------------------------------------------
# EstimationResult — mutability
# ---------------------------------------------------------------------------

class TestMutability:
    def test_diagnostic_results_appendable(self, est_result):
        dr = DiagnosticResult("vif", "VIF")
        est_result.diagnostic_results.append(dr)
        assert len(est_result.diagnostic_results) == 1

    def test_warnings_appendable(self, est_result):
        est_result.warnings.append("singular matrix")
        assert "singular matrix" in est_result.warnings
