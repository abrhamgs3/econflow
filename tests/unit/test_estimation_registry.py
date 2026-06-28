"""
Unit tests for econflow.estimation.registry.

Coverage targets
----------------
register()
    - registers a class under the given id
    - stores label, status, notes, supported_data metadata
    - re-registration raises RegistryError
    - status defaults to "implemented"

get_estimator()
    - returns the registered class
    - unknown id raises RegistryError with helpful message

list_estimators()
    - returns a list of dicts with id, label, status
    - reflects current registry contents

unregister()
    - removes the class; subsequent get raises RegistryError
    - unknown id raises RegistryError

Built-in estimators
    - ols, fe, twfe, re, fd, iv are implemented
    - gmm, quantile are stubs
    - all 8 are present after importing econflow.estimation
"""

from __future__ import annotations

import pytest

from econflow.estimation.base import BaseEstimator, EstimationResult
from econflow.estimation.registry import (
    _REGISTRY,
    _REGISTRY_META,
    get_estimator,
    list_estimators,
    register,
    unregister,
)

# ---------------------------------------------------------------------------
# Helper — minimal concrete estimator for registration tests
# ---------------------------------------------------------------------------

def _make_estimator_class(name: str = "Dummy"):
    """Return a minimal concrete BaseEstimator subclass."""

    class _DummyEstimator(BaseEstimator):
        estimator_id = name.lower()
        estimator_name = name

        def validate(self, data):
            pass

        def fit(self, data):
            import pandas as pd
            idx = pd.Index(["x"])
            return EstimationResult(
                estimator_id=self.estimator_id,
                estimator_name=self.estimator_name,
                params=pd.Series([1.0], index=idx),
                std_err=pd.Series([0.1], index=idx),
                conf_int=pd.DataFrame({"lower": [0.8], "upper": [1.2]}, index=idx),
                pvalues=pd.Series([0.01], index=idx),
                nobs=10, ngroups=5, df_resid=8,
                rsquared=0.5, rsquared_adj=0.48,
            )

        def diagnostics(self, result):
            return []

    _DummyEstimator.__name__ = name
    _DummyEstimator.__qualname__ = name
    return _DummyEstimator


# ---------------------------------------------------------------------------
# Fixtures — ensure test isolation via unregister teardown
# ---------------------------------------------------------------------------

TEST_ID = "_test_dummy_reg"

@pytest.fixture(autouse=True)
def cleanup_test_registry():
    """Remove the test estimator from registry before and after each test."""
    _REGISTRY.pop(TEST_ID, None)
    _REGISTRY_META.pop(TEST_ID, None)
    yield
    _REGISTRY.pop(TEST_ID, None)
    _REGISTRY_META.pop(TEST_ID, None)


# ---------------------------------------------------------------------------
# register()
# ---------------------------------------------------------------------------

class TestRegister:
    def test_registers_class(self):
        cls = _make_estimator_class("DummyReg")

        @register(TEST_ID, label="Dummy Reg", status="implemented")
        class Wrapped(cls):
            pass

        assert get_estimator(TEST_ID) is Wrapped

    def test_stores_metadata(self):
        @register(TEST_ID, label="My Label", status="stub", notes="tbd")
        class _E(_make_estimator_class("E")):
            pass

        meta = _REGISTRY_META[TEST_ID]
        assert meta["label"] == "My Label"
        assert meta["status"] == "stub"
        assert meta["notes"] == "tbd"

    def test_default_status_is_implemented(self):
        @register(TEST_ID)
        class _E(_make_estimator_class("E2")):
            pass

        assert _REGISTRY_META[TEST_ID]["status"] == "implemented"

    def test_reregistration_raises(self):
        @register(TEST_ID)
        class _E1(_make_estimator_class("E3")):
            pass

        from econflow.core.exceptions import RegistryError
        with pytest.raises(RegistryError, match=TEST_ID):
            @register(TEST_ID)
            class _E2(_make_estimator_class("E4")):
                pass

    def test_decorator_returns_class_unchanged(self):
        cls = _make_estimator_class("DRet")

        @register(TEST_ID)
        class Wrapped(cls):
            pass

        assert issubclass(Wrapped, BaseEstimator)


# ---------------------------------------------------------------------------
# get_estimator()
# ---------------------------------------------------------------------------

class TestGetEstimator:
    def test_returns_registered_class(self):
        @register(TEST_ID)
        class _E(_make_estimator_class("EGet")):
            pass

        assert get_estimator(TEST_ID) is _E

    def test_unknown_id_raises(self):
        from econflow.core.exceptions import RegistryError
        with pytest.raises(RegistryError, match="not_found_xyz"):
            get_estimator("not_found_xyz")

    def test_error_message_lists_available(self):
        from econflow.core.exceptions import RegistryError
        with pytest.raises(RegistryError) as exc_info:
            get_estimator("does_not_exist")
        # error should hint at valid IDs
        assert "ols" in str(exc_info.value).lower() or "available" in str(exc_info.value).lower()


# ---------------------------------------------------------------------------
# list_estimators()
# ---------------------------------------------------------------------------

class TestListEstimators:
    def test_returns_list_of_dicts(self):
        entries = list_estimators()
        assert isinstance(entries, list)
        assert all(isinstance(e, dict) for e in entries)

    def test_each_entry_has_required_keys(self):
        for entry in list_estimators():
            assert "id" in entry
            assert "label" in entry
            assert "status" in entry

    def test_reflects_new_registration(self):
        ids_before = {e["id"] for e in list_estimators()}

        @register(TEST_ID, label="Test Dummy")
        class _E(_make_estimator_class("EList")):
            pass

        ids_after = {e["id"] for e in list_estimators()}
        assert TEST_ID in ids_after
        assert TEST_ID not in ids_before

    def test_returns_copy_not_reference(self):
        a = list_estimators()
        b = list_estimators()
        assert a is not b


# ---------------------------------------------------------------------------
# unregister()
# ---------------------------------------------------------------------------

class TestUnregister:
    def test_removes_from_registry(self):
        @register(TEST_ID)
        class _E(_make_estimator_class("EUnreg")):
            pass

        unregister(TEST_ID)

        from econflow.core.exceptions import RegistryError
        with pytest.raises(RegistryError):
            get_estimator(TEST_ID)

    def test_removes_metadata(self):
        @register(TEST_ID)
        class _E(_make_estimator_class("EMeta")):
            pass

        unregister(TEST_ID)
        assert TEST_ID not in _REGISTRY_META

    def test_unknown_id_raises(self):
        from econflow.core.exceptions import RegistryError
        with pytest.raises(RegistryError):
            unregister("ghost_estimator")


# ---------------------------------------------------------------------------
# Built-in estimators (import econflow.estimation to trigger @register() calls)
# ---------------------------------------------------------------------------

class TestBuiltinEstimators:
    @pytest.fixture(autouse=True)
    def _import_estimation(self):
        import econflow.estimation  # noqa: F401

    def test_implemented_estimators_present(self):
        ids = {e["id"] for e in list_estimators()}
        for eid in ("ols", "fe", "twfe", "re", "fd", "iv"):
            assert eid in ids, f"Missing implemented estimator: {eid}"

    def test_stub_estimators_present(self):
        ids = {e["id"] for e in list_estimators()}
        for eid in ("gmm", "quantile"):
            assert eid in ids, f"Missing stub estimator: {eid}"

    def test_implemented_status(self):
        by_id = {e["id"]: e for e in list_estimators()}
        for eid in ("ols", "fe", "twfe", "re", "fd", "iv"):
            assert by_id[eid]["status"] == "implemented"

    def test_stub_status(self):
        by_id = {e["id"]: e for e in list_estimators()}
        assert by_id["gmm"]["status"] == "stub"
        assert by_id["quantile"]["status"] == "stub"

    def test_get_estimator_returns_class(self):
        from econflow.estimation.ols import PooledOLS
        assert get_estimator("ols") is PooledOLS

    def test_total_estimator_count(self):
        # 6 implemented + 2 stubs = 8 built-ins (plus any test entries)
        ids = {e["id"] for e in list_estimators()}
        builtin = {"ols", "fe", "twfe", "re", "fd", "iv", "gmm", "quantile"}
        assert builtin.issubset(ids)
