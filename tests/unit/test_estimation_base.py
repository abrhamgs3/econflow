"""
Unit tests for econflow.estimation.base.

Coverage targets
----------------
EstimatorError
    - message, estimator_id, cause attributes
    - cause chain preserved

BaseEstimator
    - cannot instantiate directly (abstract)
    - concrete subclass: validate/fit/diagnostics all required
    - run() calls validate → fit → diagnostics chain
    - run() attaches diagnostic_results to the result
    - _require_params() raises EstimatorError for missing key
    - _require_columns() raises EstimatorError for missing column
    - _to_panel() produces MultiIndex DataFrame
    - _provenance_stamp() returns dict with estimator_id + version

Backward compatibility
    - from econflow.estimation.base import EstimationResult succeeds
    - from econflow.estimation.base import DiagnosticResult succeeds
"""

from __future__ import annotations

import pandas as pd
import pytest

from econflow.estimation.base import (
    BaseEstimator,
    DiagnosticResult,
    EstimationResult,
    EstimatorError,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_panel(n_entities: int = 5, n_times: int = 6) -> pd.DataFrame:
    import numpy as np
    rng = np.random.default_rng(42)
    entities = [f"E{i}" for i in range(n_entities)]
    times = list(range(2000, 2000 + n_times))
    rows = [(e, t) for e in entities for t in times]
    df = pd.DataFrame(rows, columns=["entity", "time"])
    df["y"] = rng.standard_normal(len(df))
    df["x1"] = rng.standard_normal(len(df))
    df["x2"] = rng.standard_normal(len(df))
    return df


def _make_result(estimator_id: str = "test") -> EstimationResult:
    idx = pd.Index(["x1"])
    return EstimationResult(
        estimator_id=estimator_id,
        estimator_name="Test",
        params=pd.Series([1.0], index=idx),
        std_err=pd.Series([0.1], index=idx),
        conf_int=pd.DataFrame({"lower": [0.8], "upper": [1.2]}, index=idx),
        pvalues=pd.Series([0.01], index=idx),
        nobs=30, ngroups=5, df_resid=24,
        rsquared=0.5, rsquared_adj=0.48,
    )


class _ConcreteEstimator(BaseEstimator):
    """Minimal concrete implementation for testing."""

    estimator_id = "concrete_test"
    estimator_name = "Concrete Test Estimator"

    def validate(self, data: pd.DataFrame) -> None:
        self._require_params("dependent")
        self._require_columns(data, self.params.get("dependent", "y"))

    def fit(self, data: pd.DataFrame) -> EstimationResult:
        return _make_result(self.estimator_id)

    def diagnostics(self, result: EstimationResult) -> list[DiagnosticResult]:
        return [DiagnosticResult("mock_diag", "Mock Diagnostic")]


# ---------------------------------------------------------------------------
# EstimatorError
# ---------------------------------------------------------------------------

class TestEstimatorError:
    def test_message(self):
        e = EstimatorError("something failed")
        assert "something failed" in str(e)

    def test_estimator_id_attribute(self):
        e = EstimatorError("bad", estimator_id="fe")
        assert e.estimator_id == "fe"

    def test_cause_preserved(self):
        original = ValueError("original cause")
        e = EstimatorError("wrapped", cause=original)
        assert e.cause is original

    def test_default_estimator_id_empty(self):
        e = EstimatorError("x")
        assert e.estimator_id == ""


# ---------------------------------------------------------------------------
# BaseEstimator — abstract
# ---------------------------------------------------------------------------

class TestBaseEstimatorAbstract:
    def test_cannot_instantiate_directly(self):
        with pytest.raises(TypeError):
            BaseEstimator()

    def test_subclass_missing_validate_is_abstract(self):
        class _Missing(BaseEstimator):
            def fit(self, data): ...
            def diagnostics(self, result): ...

        with pytest.raises(TypeError):
            _Missing()

    def test_subclass_missing_fit_is_abstract(self):
        class _Missing(BaseEstimator):
            def validate(self, data): ...
            def diagnostics(self, result): ...

        with pytest.raises(TypeError):
            _Missing()

    def test_subclass_missing_diagnostics_is_abstract(self):
        class _Missing(BaseEstimator):
            def validate(self, data): ...
            def fit(self, data): ...

        with pytest.raises(TypeError):
            _Missing()


# ---------------------------------------------------------------------------
# _ConcreteEstimator — instantiation
# ---------------------------------------------------------------------------

class TestConcreteEstimatorInstantiation:
    def test_instantiates_with_no_params(self):
        est = _ConcreteEstimator()
        assert est.params == {}

    def test_instantiates_with_params(self):
        est = _ConcreteEstimator({"dependent": "y", "regressors": ["x1"]})
        assert est.params["dependent"] == "y"

    def test_params_defaults_to_empty_dict(self):
        est = _ConcreteEstimator()
        assert isinstance(est.params, dict)


# ---------------------------------------------------------------------------
# _require_params
# ---------------------------------------------------------------------------

class TestRequireParams:
    def test_passes_when_key_present(self):
        est = _ConcreteEstimator({"dependent": "y"})
        est._require_params("dependent")  # should not raise

    def test_raises_when_key_missing(self):
        est = _ConcreteEstimator({})
        with pytest.raises(EstimatorError, match="dependent"):
            est._require_params("dependent")

    def test_raises_for_multiple_missing(self):
        est = _ConcreteEstimator({})
        with pytest.raises(EstimatorError):
            est._require_params("dependent", "regressors")


# ---------------------------------------------------------------------------
# _require_columns
# ---------------------------------------------------------------------------

class TestRequireColumns:
    def test_passes_when_columns_present(self):
        est = _ConcreteEstimator()
        df = pd.DataFrame({"y": [1, 2], "x1": [3, 4]})
        est._require_columns(df, "y", "x1")  # should not raise

    def test_raises_when_column_missing(self):
        est = _ConcreteEstimator()
        df = pd.DataFrame({"y": [1, 2]})
        with pytest.raises(EstimatorError, match="x1"):
            est._require_columns(df, "y", "x1")


# ---------------------------------------------------------------------------
# _to_panel
# ---------------------------------------------------------------------------

class TestToPanel:
    def test_returns_multiindex(self):
        est = _ConcreteEstimator()
        df = _make_panel()
        panel = est._to_panel(df, "entity", "time")
        assert isinstance(panel.index, pd.MultiIndex)

    def test_multiindex_levels(self):
        est = _ConcreteEstimator()
        df = _make_panel()
        panel = est._to_panel(df, "entity", "time")
        assert panel.index.names == ["entity", "time"]

    def test_sorted(self):
        est = _ConcreteEstimator()
        df = _make_panel().sample(frac=1, random_state=0)  # shuffle
        panel = est._to_panel(df, "entity", "time")
        assert panel.index.is_monotonic_increasing

    def test_columns_unchanged(self):
        est = _ConcreteEstimator()
        df = _make_panel()
        panel = est._to_panel(df, "entity", "time")
        # entity and time become index; data cols remain
        assert "y" in panel.columns


# ---------------------------------------------------------------------------
# _provenance_stamp
# ---------------------------------------------------------------------------

class TestProvenanceStamp:
    def test_returns_dict(self):
        est = _ConcreteEstimator()
        stamp = est._provenance_stamp()
        assert isinstance(stamp, dict)

    def test_contains_estimator_id(self):
        est = _ConcreteEstimator()
        stamp = est._provenance_stamp()
        assert stamp.get("estimator_id") == "concrete_test"

    def test_contains_econflow_version(self):
        est = _ConcreteEstimator()
        stamp = est._provenance_stamp()
        assert "econflow_version" in stamp


# ---------------------------------------------------------------------------
# run() — validate → fit → diagnostics chain
# ---------------------------------------------------------------------------

class TestRunChain:
    def test_run_returns_estimation_result(self):
        est = _ConcreteEstimator({"dependent": "y"})
        df = _make_panel()
        result = est.run(df)
        assert isinstance(result, EstimationResult)

    def test_run_attaches_diagnostics(self):
        est = _ConcreteEstimator({"dependent": "y"})
        df = _make_panel()
        result = est.run(df)
        assert len(result.diagnostic_results) == 1
        assert result.diagnostic_results[0].diagnostic_id == "mock_diag"

    def test_run_calls_validate_first(self):
        """validate() should be called; missing param raises before fit."""
        est = _ConcreteEstimator()  # no params
        df = _make_panel()
        with pytest.raises(EstimatorError, match="dependent"):
            est.run(df)

    def test_predict_raises_not_implemented(self):
        est = _ConcreteEstimator({"dependent": "y"})
        result = _make_result()
        with pytest.raises(NotImplementedError):
            est.predict(result)


# ---------------------------------------------------------------------------
# Backward-compatibility re-exports
# ---------------------------------------------------------------------------

class TestBackwardCompatReexports:
    def test_estimation_result_importable_from_base(self):
        from econflow.estimation.base import EstimationResult as ER  # noqa: F401
        assert ER is EstimationResult

    def test_diagnostic_result_importable_from_base(self):
        from econflow.estimation.base import DiagnosticResult as DR  # noqa: F401
        assert DR is DiagnosticResult
