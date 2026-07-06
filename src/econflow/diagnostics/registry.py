"""
econflow.diagnostics.registry — Diagnostic plugin auto-registration.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from econflow.core.exceptions import RegistryError

if TYPE_CHECKING:
    from econflow.diagnostics.base import BaseDiagnostic

_REGISTRY: dict[str, type[BaseDiagnostic]] = {}
_REGISTRY_META: dict[str, dict[str, Any]] = {}


def register_diagnostic(
    diagnostic_id: str,
    *,
    label: str = "",
    status: str = "implemented",
    notes: str = "",
) -> Any:
    """
    Class decorator that registers a diagnostic plugin.

    Parameters
    ----------
    diagnostic_id:
        Unique short identifier (e.g. ``"hausman"``).
    label:
        Human-readable name.  Defaults to the class name.
    status:
        ``"implemented"`` or ``"stub"``.
    notes:
        Optional free-text notes.

    Raises
    ------
    RegistryError
        If *diagnostic_id* is already registered.
    """
    def decorator(cls: type[BaseDiagnostic]) -> type[BaseDiagnostic]:
        if diagnostic_id in _REGISTRY:
            raise RegistryError(
                f"Diagnostic ID {diagnostic_id!r} is already registered "
                f"(by {_REGISTRY[diagnostic_id].__name__!r})."
            )
        _REGISTRY[diagnostic_id] = cls
        _REGISTRY_META[diagnostic_id] = {
            "id":     diagnostic_id,
            "label":  label or cls.__name__,
            "status": status,
            "notes":  notes,
        }
        cls.diagnostic_id = diagnostic_id  # type: ignore[attr-defined]
        return cls

    return decorator


def get_diagnostic(diagnostic_id: str) -> type[BaseDiagnostic]:
    """
    Return the diagnostic class registered under *diagnostic_id*.

    Raises
    ------
    RegistryError
        If not found.
    """
    if diagnostic_id not in _REGISTRY:
        available = sorted(_REGISTRY)
        raise RegistryError(
            f"No diagnostic registered as {diagnostic_id!r}. "
            f"Available: {available}"
        )
    return _REGISTRY[diagnostic_id]


def list_diagnostics() -> list[dict[str, Any]]:
    """Return a sorted list of diagnostic metadata dicts."""
    return [_REGISTRY_META[did] for did in sorted(_REGISTRY_META)]


def unregister_diagnostic(diagnostic_id: str) -> None:
    """Remove a diagnostic from the registry.

    Raises
    ------
    RegistryError
        If *diagnostic_id* is not registered.
    """
    if diagnostic_id not in _REGISTRY:
        raise RegistryError(f"No diagnostic registered as {diagnostic_id!r}.")
    _REGISTRY.pop(diagnostic_id, None)
    _REGISTRY_META.pop(diagnostic_id, None)
