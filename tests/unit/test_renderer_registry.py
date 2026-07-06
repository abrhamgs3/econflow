"""
Unit tests for econflow.outputs.registry — renderer registry.

Covers:
- register_renderer / get_renderer / list_renderers / unregister_renderer
- RegistryError on duplicate registration and unknown id
- Renderer metadata fields
- All 5 built-in renderers are registered on import
"""

from __future__ import annotations

import pytest

from econflow.core.exceptions import RegistryError
from econflow.outputs.base import BaseRenderer
from econflow.outputs.model import ReportTable
from econflow.outputs.registry import (
    get_renderer,
    list_renderers,
    register_renderer,
    unregister_renderer,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _import_renderers():
    """Ensure all built-in renderers are registered before each test."""
    import econflow.outputs.renderers  # noqa: F401


# ---------------------------------------------------------------------------
# Built-in registry state
# ---------------------------------------------------------------------------

class TestBuiltinRenderers:
    def test_five_renderers_registered(self):
        ids = {r["id"] for r in list_renderers()}
        assert {"csv", "html", "json", "latex", "markdown"} <= ids

    def test_csv_renderer_metadata(self):
        meta = next(r for r in list_renderers() if r["id"] == "csv")
        assert meta["status"] == "implemented"
        assert meta["file_extension"] == ".csv"

    def test_latex_renderer_metadata(self):
        meta = next(r for r in list_renderers() if r["id"] == "latex")
        assert meta["file_extension"] == ".tex"

    def test_markdown_renderer_metadata(self):
        meta = next(r for r in list_renderers() if r["id"] == "markdown")
        assert meta["file_extension"] == ".md"

    def test_html_renderer_metadata(self):
        meta = next(r for r in list_renderers() if r["id"] == "html")
        assert meta["file_extension"] == ".html"

    def test_json_renderer_metadata(self):
        meta = next(r for r in list_renderers() if r["id"] == "json")
        assert meta["file_extension"] == ".json"


# ---------------------------------------------------------------------------
# get_renderer
# ---------------------------------------------------------------------------

class TestGetRenderer:
    def test_get_csv(self):
        cls = get_renderer("csv")
        assert issubclass(cls, BaseRenderer)

    def test_get_latex(self):
        cls = get_renderer("latex")
        assert issubclass(cls, BaseRenderer)

    def test_unknown_raises_registry_error(self):
        with pytest.raises(RegistryError, match="(?i)no renderer registered"):
            get_renderer("__unknown__")

    def test_error_message_includes_id(self):
        with pytest.raises(RegistryError, match="__missing__"):
            get_renderer("__missing__")


# ---------------------------------------------------------------------------
# register / unregister lifecycle
# ---------------------------------------------------------------------------

class TestRegistryLifecycle:
    def _make_renderer(self, rid: str) -> type[BaseRenderer]:
        @register_renderer(rid, label=f"Test {rid}", file_extension=".txt")
        class _R(BaseRenderer):
            renderer_id = rid
            file_extension = ".txt"
            def render(self, table: ReportTable, **kwargs) -> str:
                return ""
        return _R

    def test_register_and_retrieve(self):
        cls = self._make_renderer("_test_reg_001")
        try:
            retrieved = get_renderer("_test_reg_001")
            assert retrieved is cls
        finally:
            unregister_renderer("_test_reg_001")

    def test_duplicate_raises_registry_error(self):
        self._make_renderer("_test_dup_001")
        try:
            with pytest.raises(RegistryError, match="already registered"):
                self._make_renderer("_test_dup_001")
        finally:
            unregister_renderer("_test_dup_001")

    def test_unregister_removes_from_list(self):
        self._make_renderer("_test_unreg_001")
        unregister_renderer("_test_unreg_001")
        ids = {r["id"] for r in list_renderers()}
        assert "_test_unreg_001" not in ids

    def test_unregister_unknown_raises_registry_error(self):
        with pytest.raises(RegistryError):
            unregister_renderer("__nonexistent__")

    def test_list_renderers_returns_copies(self):
        lst = list_renderers()
        assert isinstance(lst, list)
        lst.clear()
        assert len(list_renderers()) > 0
