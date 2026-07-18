"""
Unit tests for econflow.diagnostics.registry.

Coverage targets
----------------
register_diagnostic()
    - registers class under given id
    - stores label, status metadata
    - re-registration raises RegistryError

get_diagnostic()
    - returns registered class
    - unknown id raises RegistryError

list_diagnostics()
    - returns list of dicts with id, label, status
    - reflects current state

unregister_diagnostic()
    - removes entry
    - unknown id raises RegistryError

BaseDiagnostic
    - cannot instantiate (abstract)
    - supports("*") returns True for any estimator_id
    - supports(["fe","twfe"]) returns True for "fe", False for "ols"
    - _not_applicable() returns DiagnosticResult with level "skip"

Built-in diagnostic plugins
    - hausman, breusch_pagan, pesaran_cd, vif are registered
    - wooldridge, serial_correlation are stubs
"""

from __future__ import annotations

import pytest

from econflow.diagnostics.base import BaseDiagnostic, DiagnosticError
from econflow.diagnostics.registry import (
    _REGISTRY,
    _REGISTRY_META,
    get_diagnostic,
    list_diagnostics,
    register_diagnostic,
    unregister_diagnostic,
)
from econflow.estimation.result import DiagnosticResult

# ---------------------------------------------------------------------------
# Helper — minimal concrete diagnostic
# ---------------------------------------------------------------------------

def _make_diagnostic_class(name: str = "Dummy"):
    class _DummyDiag(BaseDiagnostic):
        diagnostic_id = name.lower()
        name_ = name
        supported_estimators = ["*"]

        def run(self, result, **kwargs):
            return DiagnosticResult(
                diagnostic_id=self.diagnostic_id,
                diagnostic_name=self.name_,
            )

    _DummyDiag.__name__ = name
    return _DummyDiag


TEST_ID = "_test_dummy_diag"


@pytest.fixture(autouse=True)
def cleanup():
    _REGISTRY.pop(TEST_ID, None)
    _REGISTRY_META.pop(TEST_ID, None)
    yield
    _REGISTRY.pop(TEST_ID, None)
    _REGISTRY_META.pop(TEST_ID, None)


# ---------------------------------------------------------------------------
# register_diagnostic()
# ---------------------------------------------------------------------------

class TestRegisterDiagnostic:
    def test_registers_class(self):
        @register_diagnostic(TEST_ID, label="Test Diag")
        class _D(_make_diagnostic_class("D1")):
            pass

        assert get_diagnostic(TEST_ID) is _D

    def test_stores_metadata(self):
        @register_diagnostic(TEST_ID, label="LBL", status="stub", notes="wip")
        class _D(_make_diagnostic_class("D2")):
            pass

        meta = _REGISTRY_META[TEST_ID]
        assert meta["label"] == "LBL"
        assert meta["status"] == "stub"
        assert meta["notes"] == "wip"

    def test_default_status_is_implemented(self):
        @register_diagnostic(TEST_ID)
        class _D(_make_diagnostic_class("D3")):
            pass

        assert _REGISTRY_META[TEST_ID]["status"] == "implemented"

    def test_reregistration_raises(self):
        @register_diagnostic(TEST_ID)
        class _D1(_make_diagnostic_class("D4")):
            pass

        from econflow.core.exceptions import RegistryError
        with pytest.raises(RegistryError):
            @register_diagnostic(TEST_ID)
            class _D2(_make_diagnostic_class("D5")):
                pass


# ---------------------------------------------------------------------------
# get_diagnostic()
# ---------------------------------------------------------------------------

class TestGetDiagnostic:
    def test_returns_class(self):
        @register_diagnostic(TEST_ID)
        class _D(_make_diagnostic_class("DGet")):
            pass

        assert get_diagnostic(TEST_ID) is _D

    def test_unknown_raises(self):
        from econflow.core.exceptions import RegistryError
        with pytest.raises(RegistryError, match="ghost_diag"):
            get_diagnostic("ghost_diag")


# ---------------------------------------------------------------------------
# list_diagnostics()
# ---------------------------------------------------------------------------

class TestListDiagnostics:
    def test_returns_list_of_dicts(self):
        entries = list_diagnostics()
        assert isinstance(entries, list)
        assert all(isinstance(e, dict) for e in entries)

    def test_each_has_required_keys(self):
        for e in list_diagnostics():
            assert "id" in e
            assert "status" in e

    def test_reflects_new_entry(self):
        ids_before = {e["id"] for e in list_diagnostics()}

        @register_diagnostic(TEST_ID, label="T")
        class _D(_make_diagnostic_class("DList")):
            pass

        ids_after = {e["id"] for e in list_diagnostics()}
        assert TEST_ID in ids_after
        assert TEST_ID not in ids_before


# ---------------------------------------------------------------------------
# unregister_diagnostic()
# ---------------------------------------------------------------------------

class TestUnregisterDiagnostic:
    def test_removes_entry(self):
        @register_diagnostic(TEST_ID)
        class _D(_make_diagnostic_class("DUnreg")):
            pass

        unregister_diagnostic(TEST_ID)

        from econflow.core.exceptions import RegistryError
        with pytest.raises(RegistryError):
            get_diagnostic(TEST_ID)

    def test_unknown_raises(self):
        from econflow.core.exceptions import RegistryError
        with pytest.raises(RegistryError):
            unregister_diagnostic("ghost")


# ---------------------------------------------------------------------------
# BaseDiagnostic — abstract + helpers
# ---------------------------------------------------------------------------

class TestBaseDiagnostic:
    def test_cannot_instantiate_directly(self):
        with pytest.raises(TypeError):
            BaseDiagnostic()

    def test_supports_wildcard(self):
        cls = _make_diagnostic_class("Wild")
        d = cls()
        assert d.supports("ols") is True
        assert d.supports("twfe") is True

    def test_supports_specific_list(self):
        class _Specific(BaseDiagnostic):
            diagnostic_id = "spec"
            supported_estimators = ["fe", "twfe"]
            def run(self, result, **kwargs): ...

        d = _Specific()
        assert d.supports("fe") is True
        assert d.supports("twfe") is True
        assert d.supports("ols") is False

    def test_not_applicable_returns_skip_level(self):
        cls = _make_diagnostic_class("NA")
        d = cls()
        result = d._not_applicable("n/a reason")
        assert isinstance(result, DiagnosticResult)
        assert result.level in ("info", "skip")
        assert result.diagnostic_id == cls().diagnostic_id


# ---------------------------------------------------------------------------
# DiagnosticError
# ---------------------------------------------------------------------------

class TestDiagnosticError:
    def test_message(self):
        e = DiagnosticError("test error")
        assert "test error" in str(e)

    def test_diagnostic_id_attribute(self):
        e = DiagnosticError("x", diagnostic_id="vif")
        assert e.diagnostic_id == "vif"

    def test_cause_attribute(self):
        cause = RuntimeError("root cause")
        e = DiagnosticError("wrapped", cause=cause)
        assert e.cause is cause


# ---------------------------------------------------------------------------
# Built-in diagnostic plugins
# ---------------------------------------------------------------------------

class TestBuiltinDiagnostics:
    @pytest.fixture(autouse=True)
    def _import_plugins(self):
        import econflow.diagnostics  # noqa: F401

    def test_implemented_plugins_registered(self):
        ids = {e["id"] for e in list_diagnostics()}
        for did in ("hausman", "breusch_pagan", "pesaran_cd", "vif"):
            assert did in ids, f"Missing: {did}"

    def test_stub_plugins_registered(self):
        ids = {e["id"] for e in list_diagnostics()}
        for did in ("wooldridge", "serial_correlation"):
            assert did in ids, f"Missing stub: {did}"

    def test_implemented_status(self):
        by_id = {e["id"]: e for e in list_diagnostics()}
        for did in ("hausman", "breusch_pagan", "pesaran_cd", "vif"):
            assert by_id[did]["status"] == "implemented"

    def test_stub_status(self):
        by_id = {e["id"]: e for e in list_diagnostics()}
        assert by_id["wooldridge"]["status"] == "stub"
        assert by_id["serial_correlation"]["status"] == "stub"

    def test_get_returns_class(self):
        from econflow.diagnostics.plugins.vif import VIFCheck as VIFDiagnostic
        assert get_diagnostic("vif") is VIFDiagnostic
