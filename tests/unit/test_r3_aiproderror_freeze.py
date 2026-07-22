"""
tests/unit/test_r3_aiproderror_freeze.py — R3 regression suite.

Guards against C-2 regression: ``AIProdError`` — a name explicitly slated for
removal in v0.3.0 — being committed to the 1.0 public API via inclusion in
``econflow.__all__``. Freezing a name in ``__all__`` at 1.0 obligates the
project to keep it until 2.0; the planned v0.3.0 removal would then violate
semantic versioning.

Coverage dimensions:
    1. ``__all__`` membership   — AIProdError must not appear in econflow.__all__
    2. Runtime availability     — `from econflow import AIProdError` still works
    3. Identity                 — the alias is still the same object as EconFlowError
    4. Deprecation signal       — accessing it warns exactly once (first access)
    5. Unknown-attribute guard  — __getattr__ still raises AttributeError for typos
    6. Submodule unaffected     — econflow.exceptions.AIProdError is untouched
       (no __all__ change there; this fix is scoped to the top-level package)
"""

from __future__ import annotations

import sys
import warnings

import pytest


# ---------------------------------------------------------------------------
# 1. __all__ membership
# ---------------------------------------------------------------------------

class TestAllExports:
    def test_aiproderror_not_in_top_level_all(self) -> None:
        import econflow
        assert "AIProdError" not in econflow.__all__

    def test_econflowerror_still_in_top_level_all(self) -> None:
        import econflow
        assert "EconFlowError" in econflow.__all__


# ---------------------------------------------------------------------------
# 2 & 3. Runtime availability + identity
# ---------------------------------------------------------------------------

class TestBackwardCompatAccess:
    def test_from_import_still_works(self) -> None:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            from econflow import AIProdError
        assert AIProdError is not None

    def test_attribute_access_still_works(self) -> None:
        import econflow
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            assert econflow.AIProdError is not None

    def test_alias_is_econflowerror(self) -> None:
        import econflow
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            assert econflow.AIProdError is econflow.EconFlowError

    def test_alias_still_catches_domain_exceptions(self) -> None:
        import econflow
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            aip = econflow.AIProdError
        with pytest.raises(aip):
            raise econflow.DataValidationError("boom")


# ---------------------------------------------------------------------------
# 4. Deprecation signal
# ---------------------------------------------------------------------------

class TestDeprecationWarning:
    def test_first_access_warns(self, monkeypatch) -> None:
        # Import a fresh module object so caching from earlier tests in this
        # session doesn't suppress the warning.
        #
        # NOTE: a raw `sys.modules.pop("econflow", None)` here (as this test
        # used to do) leaks: it drops the *key* but leaves every already-
        # imported submodule (econflow.commands, econflow.estimation, ...)
        # cached in sys.modules, parented to the *old* module object. The
        # fresh `importlib.import_module("econflow")` below creates a new
        # module object that never re-imports those submodules, so it has
        # no `.commands` attribute -- and since the submodules are still
        # cached, later `import econflow.commands...` calls (e.g. inside
        # unittest.mock.patch(...) in test_release_check.py, when the full
        # suite runs in one process) short-circuit on the cache and never
        # rebind `commands` onto the new econflow module, causing a
        # persistent `AttributeError: module 'econflow' has no attribute
        # 'commands'` for the rest of the test session. Using
        # monkeypatch.delitem instead ensures pytest restores the original,
        # fully-populated sys.modules["econflow"] entry at teardown.
        import importlib

        monkeypatch.delitem(sys.modules, "econflow", raising=False)
        econflow = importlib.import_module("econflow")
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            _ = econflow.AIProdError
        deprecation_warnings = [
            w for w in caught if issubclass(w.category, DeprecationWarning)
        ]
        assert len(deprecation_warnings) == 1
        assert "AIProdError" in str(deprecation_warnings[0].message)
        assert "v0.3.0" in str(deprecation_warnings[0].message)

    def test_second_access_does_not_rewarn(self) -> None:
        import econflow
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            _ = econflow.AIProdError  # prime the cache
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            _ = econflow.AIProdError
        assert len(caught) == 0


# ---------------------------------------------------------------------------
# 5. Unknown-attribute guard
# ---------------------------------------------------------------------------

class TestUnknownAttributeGuard:
    def test_unknown_attribute_raises_attributeerror(self) -> None:
        import econflow
        with pytest.raises(AttributeError):
            econflow.ThisAttributeDoesNotExist


# ---------------------------------------------------------------------------
# 6. Submodule unaffected — econflow.exceptions is untouched by this fix
# ---------------------------------------------------------------------------

class TestSubmoduleUnaffected:
    def test_exceptions_module_still_exports_aiproderror_directly(self) -> None:
        # No __getattr__ trick here — econflow.exceptions.AIProdError is a
        # plain module-level assignment and is unaffected by the top-level
        # __all__ change (C-2 scope is econflow/__init__.py only).
        from econflow.exceptions import AIProdError, EconFlowError
        assert AIProdError is EconFlowError
