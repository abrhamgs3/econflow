"""
tests/unit/test_ingestion_registry.py — Unit tests for connector registry.

Covers:
- register() decorator stamps connector_id on class
- register() populates _REGISTRY and _REGISTRY_META
- get_connector() returns the right class
- get_connector() raises KeyError for unknown IDs with helpful message
- list_connectors() returns sorted list of dicts
- unregister() removes from both dicts; silent on unknown IDs
- Duplicate registration raises ValueError
"""

from __future__ import annotations

from pathlib import Path

import pytest

from econflow.ingestion.base import AbstractConnector
from econflow.ingestion.metadata import DatasetMetadata
from econflow.ingestion.registry import (
    _REGISTRY,
    _REGISTRY_META,
    get_connector,
    list_connectors,
    register,
    unregister,
)
from econflow.ingestion.validation import DataValidationReport

# ---------------------------------------------------------------------------
# Minimal concrete connector for testing
# ---------------------------------------------------------------------------

def _make_connector_class(name: str) -> type:
    class _Stub(AbstractConnector):
        def connect(self): pass  # noqa: E704
        def download(self, *, force=False): return Path("/tmp/x.csv")  # noqa: E704
        def validate(self, path):  # noqa: E704
            return DataValidationReport(path=str(path), row_count=0, col_count=0)
        def metadata(self): return DatasetMetadata.now(connector_id=name, source="S", url="/u")  # noqa: E704
        def cache_key(self): return name  # noqa: E704
    _Stub.__name__ = name
    return _Stub


class TestRegisterDecorator:
    def setup_method(self):
        # Use unique IDs per test to avoid cross-test contamination
        self._ids: list[str] = []

    def teardown_method(self):
        for cid in self._ids:
            unregister(cid)

    def _register(self, cid, **kw):
        self._ids.append(cid)
        cls = _make_connector_class(cid)
        return register(cid, **kw)(cls)

    def test_stamps_connector_id_on_class(self) -> None:
        cls = self._register("test_stamp_001")
        assert cls.connector_id == "test_stamp_001"

    def test_adds_to_registry(self) -> None:
        self._register("test_add_002")
        assert "test_add_002" in _REGISTRY

    def test_adds_to_registry_meta(self) -> None:
        self._register("test_meta_003")
        assert "test_meta_003" in _REGISTRY_META

    def test_label_defaults_to_class_name(self) -> None:
        cid = "test_label_004"
        cls = _make_connector_class("MyClass")
        self._ids.append(cid)
        register(cid)(cls)
        assert _REGISTRY_META[cid]["label"] == "MyClass"

    def test_custom_label(self) -> None:
        self._register("test_custom_005", label="My Source")
        assert _REGISTRY_META["test_custom_005"]["label"] == "My Source"

    def test_status_defaults_to_implemented(self) -> None:
        self._register("test_status_006")
        assert _REGISTRY_META["test_status_006"]["status"] == "implemented"

    def test_custom_status_stub(self) -> None:
        self._register("test_stub_007", status="stub")
        assert _REGISTRY_META["test_stub_007"]["status"] == "stub"

    def test_notes_stored(self) -> None:
        self._register("test_notes_008", notes="Some notes")
        assert _REGISTRY_META["test_notes_008"]["notes"] == "Some notes"

    def test_duplicate_raises_value_error(self) -> None:
        self._register("test_dup_009")
        with pytest.raises(ValueError, match="already registered"):
            self._register("test_dup_009")

    def test_decorator_returns_class(self) -> None:
        cls = _make_connector_class("test_ret_010")
        self._ids.append("test_ret_010")
        result = register("test_ret_010")(cls)
        assert result is cls


class TestGetConnector:
    def setup_method(self):
        self._ids: list[str] = []

    def teardown_method(self):
        for cid in self._ids:
            unregister(cid)

    def _register(self, cid):
        self._ids.append(cid)
        cls = _make_connector_class(cid)
        return register(cid)(cls)

    def test_returns_registered_class(self) -> None:
        cls = self._register("test_get_011")
        assert get_connector("test_get_011") is cls

    def test_unknown_raises_key_error(self) -> None:
        with pytest.raises(KeyError):
            get_connector("nonexistent_xyz_000")

    def test_error_message_mentions_available(self) -> None:
        self._register("test_avail_012")
        with pytest.raises(KeyError, match="Available connectors"):
            get_connector("nonexistent_xyz_001")


class TestListConnectors:
    def setup_method(self):
        self._ids: list[str] = []

    def teardown_method(self):
        for cid in self._ids:
            unregister(cid)

    def _register(self, cid, **kw):
        self._ids.append(cid)
        cls = _make_connector_class(cid)
        register(cid, **kw)(cls)

    def test_returns_list_of_dicts(self) -> None:
        result = list_connectors()
        assert isinstance(result, list)
        for item in result:
            assert isinstance(item, dict)

    def test_each_dict_has_required_keys(self) -> None:
        self._register("test_lc_013")
        result = list_connectors()
        for item in result:
            for key in ("id", "label", "status", "notes"):
                assert key in item

    def test_sorted_by_id(self) -> None:
        self._register("zzz_test_014")
        self._register("aaa_test_015")
        ids = [c["id"] for c in list_connectors()]
        assert ids == sorted(ids)


class TestUnregister:
    def test_removes_from_registry(self) -> None:
        cid = "test_unr_016"
        cls = _make_connector_class(cid)
        register(cid)(cls)
        assert cid in _REGISTRY
        unregister(cid)
        assert cid not in _REGISTRY

    def test_removes_from_registry_meta(self) -> None:
        cid = "test_unr_017"
        cls = _make_connector_class(cid)
        register(cid)(cls)
        unregister(cid)
        assert cid not in _REGISTRY_META

    def test_silent_on_unknown_id(self) -> None:
        unregister("does_not_exist_xyz")  # should not raise

    def test_can_reregister_after_unregister(self) -> None:
        cid = "test_rereg_018"
        cls = _make_connector_class(cid)
        register(cid)(cls)
        unregister(cid)
        register(cid)(cls)  # should not raise
        unregister(cid)


class TestBuiltinConnectors:
    """Verify the built-in connectors are registered when ingestion is imported."""

    def test_csv_is_registered(self) -> None:
        import econflow.ingestion  # noqa: F401
        assert "csv" in _REGISTRY

    def test_world_bank_is_registered(self) -> None:
        import econflow.ingestion  # noqa: F401
        assert "world_bank" in _REGISTRY

    def test_oecd_is_registered(self) -> None:
        import econflow.ingestion  # noqa: F401
        assert "oecd" in _REGISTRY

    def test_pwt_is_registered(self) -> None:
        import econflow.ingestion  # noqa: F401
        assert "pwt" in _REGISTRY
