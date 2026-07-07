"""
tests/unit/test_estimator_protocol.py — Milestone 3 protocol conformance tests.

Verifies:
1. EstimatorProtocol is satisfied by all 8 registered BaseEstimator subclasses.
2. A duck-typed custom class satisfies the Protocol without inheriting BaseEstimator.
3. A class missing a required attribute/method does NOT satisfy the Protocol.
4. BackendCapabilities validates backend strings and capability flags.
5. EstimatorRegistry list_by_backend() filters correctly.
6. All registered estimators have the correct backend = "linearmodels".
7. LinearmodelsMixin._to_panel() produces a correct MultiIndex DataFrame.
8. LinearmodelsMixin._backend_capabilities() returns correct flags.
9. Stub mixins (statsmodels, pyfixest, doubleml, pymc) raise NotImplementedError.
10. BaseEstimator._backend_capabilities() falls back to BackendCapabilities(backend="custom").
"""

from __future__ import annotations

import pandas as pd
import pytest

from econflow.estimation.backends import (
    DoubleMLMixin,
    LinearmodelsMixin,
    PyfixestMixin,
    PyMCMixin,
    StatsmodelsMixin,
)
from econflow.estimation.base import BaseEstimator

# ---------------------------------------------------------------------------
# Protocol and backend imports
# ---------------------------------------------------------------------------
from econflow.estimation.protocol import (
    BACKEND_CUSTOM,
    BACKEND_DOUBLEML,
    BACKEND_LINEARMODELS,
    BACKEND_PYFIXEST,
    BACKEND_PYMC,
    BACKEND_STATSMODELS,
    KNOWN_BACKENDS,
    BackendCapabilities,
    EstimatorProtocol,
)
from econflow.estimation.result import EstimationResult

# ---------------------------------------------------------------------------
# Helpers — minimal duck-typed estimator (no BaseEstimator inheritance)
# ---------------------------------------------------------------------------

class _MinimalCustomEstimator:
    """
    A fully duck-typed estimator that satisfies EstimatorProtocol without
    inheriting from BaseEstimator.  This simulates e.g. a pyfixest wrapper
    written by a third-party contributor.
    """
    estimator_id = "custom_ols"
    name         = "Custom OLS"
    backend      = BACKEND_CUSTOM

    def fit(self, data) -> EstimationResult:
        return EstimationResult(
            estimator_id=self.estimator_id,
            estimator_name=self.name,
            coefficients={},
            std_errors={},
            p_values={},
            n_obs=0,
        )

    def validate(self, data) -> None:
        pass

    def diagnostics(self, result) -> list:
        return []

    def run(self, data) -> EstimationResult:
        self.validate(data)
        result = self.fit(data)
        result.diagnostic_results = self.diagnostics(result)
        return result


class _IncompleteEstimator:
    """Missing 'run' and 'backend' — should NOT satisfy protocol."""
    estimator_id = "bad"
    name = "Bad"

    def fit(self, data): ...
    def validate(self, data): ...
    def diagnostics(self, result): ...
    # missing: run, backend


# ---------------------------------------------------------------------------
# 1. Protocol — KNOWN_BACKENDS and constants
# ---------------------------------------------------------------------------

class TestBackendConstants:
    def test_known_backends_contains_all(self):
        assert BACKEND_LINEARMODELS in KNOWN_BACKENDS
        assert BACKEND_STATSMODELS in KNOWN_BACKENDS
        assert BACKEND_PYFIXEST in KNOWN_BACKENDS
        assert BACKEND_DOUBLEML in KNOWN_BACKENDS
        assert BACKEND_PYMC in KNOWN_BACKENDS
        assert BACKEND_CUSTOM in KNOWN_BACKENDS

    def test_known_backends_is_frozenset(self):
        assert isinstance(KNOWN_BACKENDS, frozenset)

    def test_constant_values(self):
        assert BACKEND_LINEARMODELS == "linearmodels"
        assert BACKEND_STATSMODELS == "statsmodels"
        assert BACKEND_PYFIXEST == "pyfixest"
        assert BACKEND_DOUBLEML == "doubleml"
        assert BACKEND_PYMC == "pymc"
        assert BACKEND_CUSTOM == "custom"


# ---------------------------------------------------------------------------
# 2. BackendCapabilities
# ---------------------------------------------------------------------------

class TestBackendCapabilities:
    def test_valid_construction(self):
        caps = BackendCapabilities(backend=BACKEND_LINEARMODELS, supports_panel=True)
        assert caps.backend == BACKEND_LINEARMODELS
        assert caps.supports_panel is True
        assert caps.supports_bayesian is False

    def test_all_capabilities_default_false(self):
        caps = BackendCapabilities(backend=BACKEND_CUSTOM)
        for flag in (
            "supports_panel", "supports_cross_section", "supports_time_series",
            "supports_spatial", "supports_bayesian", "supports_iv",
            "supports_quantile", "supports_gmm",
        ):
            assert getattr(caps, flag) is False, f"{flag} should default to False"

    def test_invalid_backend_raises(self):
        with pytest.raises(ValueError, match="Unknown backend"):
            BackendCapabilities(backend="nonexistent_library")

    def test_linearmodels_capabilities(self):
        caps = LinearmodelsMixin()._backend_capabilities()
        assert caps.backend == BACKEND_LINEARMODELS
        assert caps.supports_panel is True
        assert caps.supports_iv is True
        assert caps.supports_gmm is True
        assert caps.supports_bayesian is False

    def test_statsmodels_capabilities(self):
        caps = StatsmodelsMixin()._backend_capabilities()
        assert caps.backend == BACKEND_STATSMODELS
        assert caps.supports_cross_section is True
        assert caps.supports_time_series is True
        assert caps.supports_quantile is True
        assert caps.supports_panel is False

    def test_pyfixest_capabilities(self):
        caps = PyfixestMixin()._backend_capabilities()
        assert caps.backend == BACKEND_PYFIXEST
        assert caps.supports_panel is True
        assert caps.supports_iv is True

    def test_doubleml_capabilities(self):
        caps = DoubleMLMixin()._backend_capabilities()
        assert caps.backend == BACKEND_DOUBLEML
        assert caps.supports_panel is True
        assert caps.supports_iv is True

    def test_pymc_capabilities(self):
        caps = PyMCMixin()._backend_capabilities()
        assert caps.backend == BACKEND_PYMC
        assert caps.supports_bayesian is True
        assert caps.supports_spatial is True


# ---------------------------------------------------------------------------
# 3. EstimatorProtocol — isinstance checks
# ---------------------------------------------------------------------------

class TestEstimatorProtocol:
    def test_custom_duck_typed_satisfies_protocol(self):
        """Non-ABC class satisfies protocol via structural typing."""
        est = _MinimalCustomEstimator()
        assert isinstance(est, EstimatorProtocol)

    def test_incomplete_class_does_not_satisfy_protocol(self):
        """Class missing 'run' and 'backend' fails protocol check."""
        est = _IncompleteEstimator()
        assert not isinstance(est, EstimatorProtocol)

    def test_protocol_is_runtime_checkable(self):
        """EstimatorProtocol must be decorated with @runtime_checkable."""
        # If not runtime-checkable, isinstance() would raise TypeError
        est = _MinimalCustomEstimator()
        try:
            result = isinstance(est, EstimatorProtocol)
            assert isinstance(result, bool)
        except TypeError:
            pytest.fail("EstimatorProtocol is not @runtime_checkable")

    def test_base_estimator_subclass_satisfies_protocol(self):
        """A minimal concrete BaseEstimator satisfies EstimatorProtocol."""
        class _ConcreteEstimator(BaseEstimator):
            estimator_id = "_test_concrete"
            name = "Test"
            backend = BACKEND_LINEARMODELS

            def validate(self, data): pass
            def fit(self, data): return EstimationResult(
                estimator_id=self.estimator_id,
                estimator_name=self.name,
                coefficients={}, std_errors={}, p_values={}, n_obs=0,
            )
            def diagnostics(self, result): return []

        est = _ConcreteEstimator()
        assert isinstance(est, EstimatorProtocol)


# ---------------------------------------------------------------------------
# 4. All registered estimators satisfy EstimatorProtocol
# ---------------------------------------------------------------------------

# Import estimation to trigger @register() on all 8 built-in estimators

ALL_ESTIMATOR_IDS = ["ols", "fe", "twfe", "re", "fd", "iv", "gmm", "quantile"]


class TestRegisteredEstimatorsProtocol:
    @pytest.mark.parametrize("estimator_id", ALL_ESTIMATOR_IDS)
    def test_satisfies_estimator_protocol(self, estimator_id):
        from econflow.estimation.registry import get_estimator
        cls = get_estimator(estimator_id)
        inst = cls(params={"dependent": "y", "regressors": ["x"]})
        assert isinstance(inst, EstimatorProtocol), (
            f"{cls.__name__} does not satisfy EstimatorProtocol"
        )

    @pytest.mark.parametrize("estimator_id", ALL_ESTIMATOR_IDS)
    def test_has_backend_attribute(self, estimator_id):
        from econflow.estimation.registry import get_estimator
        cls = get_estimator(estimator_id)
        assert hasattr(cls, "backend"), f"{cls.__name__} missing .backend"
        assert cls.backend == BACKEND_LINEARMODELS, (
            f"{cls.__name__}.backend={cls.backend!r}, expected 'linearmodels'"
        )

    @pytest.mark.parametrize("estimator_id", ALL_ESTIMATOR_IDS)
    def test_has_estimator_id_attribute(self, estimator_id):
        from econflow.estimation.registry import get_estimator
        cls = get_estimator(estimator_id)
        assert cls.estimator_id == estimator_id

    @pytest.mark.parametrize("estimator_id", ALL_ESTIMATOR_IDS)
    def test_has_name_attribute(self, estimator_id):
        from econflow.estimation.registry import get_estimator
        cls = get_estimator(estimator_id)
        assert isinstance(cls.name, str) and cls.name, (
            f"{cls.__name__}.name is empty or missing"
        )


# ---------------------------------------------------------------------------
# 5. Registry list_by_backend()
# ---------------------------------------------------------------------------

class TestListByBackend:
    def test_linearmodels_returns_all_eight(self):
        from econflow.estimation.registry import list_by_backend
        results = list_by_backend("linearmodels")
        ids = {r["id"] for r in results}
        assert ids == set(ALL_ESTIMATOR_IDS), (
            f"Expected all 8 estimators under linearmodels, got: {ids}"
        )

    def test_statsmodels_returns_empty(self):
        from econflow.estimation.registry import list_by_backend
        results = list_by_backend("statsmodels")
        assert results == []

    def test_unknown_backend_returns_empty(self):
        from econflow.estimation.registry import list_by_backend
        results = list_by_backend("does_not_exist")
        assert results == []

    def test_entries_include_backend_key(self):
        from econflow.estimation.registry import list_estimators
        for entry in list_estimators():
            assert "backend" in entry, f"Entry for {entry['id']} missing 'backend' key"
            assert entry["backend"] == BACKEND_LINEARMODELS

    def test_sorted_by_id(self):
        from econflow.estimation.registry import list_by_backend
        results = list_by_backend("linearmodels")
        ids = [r["id"] for r in results]
        assert ids == sorted(ids)


# ---------------------------------------------------------------------------
# 6. LinearmodelsMixin._to_panel()
# ---------------------------------------------------------------------------

class TestLinearmodelsMixin:
    def _sample_df(self) -> pd.DataFrame:
        return pd.DataFrame({
            "country": ["A", "A", "B", "B"],
            "year":    [2000, 2001, 2000, 2001],
            "y":       [1.0, 2.0, 3.0, 4.0],
            "x":       [0.1, 0.2, 0.3, 0.4],
        })

    def test_to_panel_sets_multiindex(self):
        mixin = LinearmodelsMixin()
        df = self._sample_df()
        panel = mixin._to_panel(df, "country", "year")
        assert list(panel.index.names) == ["country", "year"]

    def test_to_panel_is_sorted(self):
        mixin = LinearmodelsMixin()
        df = self._sample_df().iloc[::-1].reset_index(drop=True)  # reverse order
        panel = mixin._to_panel(df, "country", "year")
        assert panel.index.is_monotonic_increasing

    def test_to_panel_preserves_values(self):
        mixin = LinearmodelsMixin()
        df = self._sample_df()
        panel = mixin._to_panel(df, "country", "year")
        assert panel.loc[("A", 2000), "y"] == pytest.approx(1.0)
        assert panel.loc[("B", 2001), "x"] == pytest.approx(0.4)

    def test_to_panel_original_unchanged(self):
        mixin = LinearmodelsMixin()
        df = self._sample_df()
        _ = mixin._to_panel(df, "country", "year")
        # Original DataFrame should still have flat index
        assert list(df.index.names) == [None]

    def test_check_linearmodels_returns_string_or_none(self):
        mixin = LinearmodelsMixin()
        result = mixin._check_linearmodels()
        assert result is None or isinstance(result, str)

    def test_backend_attribute(self):
        assert LinearmodelsMixin.backend == BACKEND_LINEARMODELS


# ---------------------------------------------------------------------------
# 7. Stub mixin NotImplementedError
# ---------------------------------------------------------------------------

class TestStubMixinErrors:
    def test_statsmodels_to_formula_raises(self):
        mixin = StatsmodelsMixin()
        with pytest.raises(NotImplementedError, match="Milestone 4"):
            mixin._to_formula("y", ["x"])

    def test_pyfixest_to_fixest_formula_raises(self):
        mixin = PyfixestMixin()
        with pytest.raises(NotImplementedError, match="Milestone 4"):
            mixin._to_fixest_formula("y", ["x"])

    def test_doubleml_to_data_raises(self):
        mixin = DoubleMLMixin()
        with pytest.raises(NotImplementedError, match="Milestone 5"):
            mixin._to_doubleml_data(None, "y", "d", ["x"])

    def test_pymc_build_model_raises(self):
        mixin = PyMCMixin()
        with pytest.raises(NotImplementedError, match="Milestone 6"):
            mixin._build_pymc_model(None, "y", ["x"])

    def test_pymc_extract_posterior_raises(self):
        mixin = PyMCMixin()
        with pytest.raises(NotImplementedError, match="Milestone 6"):
            mixin._extract_posterior_summary(None)

    def test_stub_check_methods_return_none_or_string(self):
        """Version check methods are introspection only — never raise."""
        assert StatsmodelsMixin()._check_statsmodels() is None or isinstance(
            StatsmodelsMixin()._check_statsmodels(), str
        )
        assert PyfixestMixin()._check_pyfixest() is None or isinstance(
            PyfixestMixin()._check_pyfixest(), str
        )
        assert DoubleMLMixin()._check_doubleml() is None or isinstance(
            DoubleMLMixin()._check_doubleml(), str
        )
        assert PyMCMixin()._check_pymc() is None or isinstance(
            PyMCMixin()._check_pymc(), str
        )


# ---------------------------------------------------------------------------
# 8. BaseEstimator._backend_capabilities() fallback
# ---------------------------------------------------------------------------

class TestBaseEstimatorBackendCapabilities:
    def _make_concrete(self, backend_val: str = "unknown"):
        class _Concrete(BaseEstimator):
            estimator_id = "_test_caps"
            name = "Test"
            backend = backend_val
            def validate(self, data): pass
            def fit(self, data): return EstimationResult(
                estimator_id=self.estimator_id, estimator_name=self.name,
                coefficients={}, std_errors={}, p_values={}, n_obs=0,
            )
            def diagnostics(self, result): return []
        return _Concrete()

    def test_unknown_backend_falls_back_to_custom(self):
        est = self._make_concrete("unknown")
        caps = est._backend_capabilities()
        assert caps.backend == BACKEND_CUSTOM

    def test_linearmodels_backend_resolves(self):
        est = self._make_concrete(BACKEND_LINEARMODELS)
        caps = est._backend_capabilities()
        assert caps.backend == BACKEND_LINEARMODELS

    def test_returns_backend_capabilities_instance(self):
        est = self._make_concrete()
        caps = est._backend_capabilities()
        assert isinstance(caps, BackendCapabilities)


# ---------------------------------------------------------------------------
# 9. Public __init__ exports are present
# ---------------------------------------------------------------------------

class TestPublicExports:
    def test_estimator_protocol_exported(self):
        import econflow.estimation as ee
        assert hasattr(ee, "EstimatorProtocol")
        assert ee.EstimatorProtocol is EstimatorProtocol

    def test_backend_capabilities_exported(self):
        import econflow.estimation as ee
        assert hasattr(ee, "BackendCapabilities")

    def test_backend_constants_exported(self):
        import econflow.estimation as ee
        for name in (
            "BACKEND_LINEARMODELS", "BACKEND_STATSMODELS", "BACKEND_PYFIXEST",
            "BACKEND_DOUBLEML", "BACKEND_PYMC", "BACKEND_CUSTOM", "KNOWN_BACKENDS",
        ):
            assert hasattr(ee, name), f"Missing export: {name}"

    def test_linearmodels_mixin_exported(self):
        import econflow.estimation as ee
        assert hasattr(ee, "LinearmodelsMixin")
        assert ee.LinearmodelsMixin is LinearmodelsMixin

    def test_stub_mixins_exported(self):
        import econflow.estimation as ee
        for name in ("StatsmodelsMixin", "PyfixestMixin", "DoubleMLMixin", "PyMCMixin"):
            assert hasattr(ee, name), f"Missing export: {name}"

    def test_list_by_backend_exported(self):
        import econflow.estimation as ee
        assert hasattr(ee, "list_by_backend")
        assert callable(ee.list_by_backend)

    def test_backward_compat_exports_unchanged(self):
        """All pre-Milestone 3 exports still present."""
        import econflow.estimation as ee
        for name in (
            "EstimationResult", "DiagnosticResult", "BaseEstimator", "EstimatorError",
            "register", "get_estimator", "list_estimators", "unregister",
            "PooledOLS", "EntityFE", "TwoWayFE", "RandomEffects",
            "FirstDifference", "IV2SLS", "SystemGMM", "PanelQuantile",
        ):
            assert hasattr(ee, name), f"Backward-compat export missing: {name}"
