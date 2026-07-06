"""
econflow.integrity.checks.registry — Integrity check auto-registration.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from econflow.core.exceptions import RegistryError

if TYPE_CHECKING:
    from econflow.integrity.checks.base import BaseIntegrityCheck

_REGISTRY: dict[str, type[BaseIntegrityCheck]] = {}
_REGISTRY_META: dict[str, dict[str, Any]] = {}


def register_integrity_check(
    check_id: str,
    *,
    label: str = "",
    status: str = "implemented",
    notes: str = "",
) -> Any:
    """
    Class decorator that registers an integrity check plugin.

    Parameters
    ----------
    check_id:
        Unique short identifier (e.g. ``"coefficient_stability"``).
    label:
        Human-readable name.  Defaults to the class name.
    status:
        ``"implemented"`` or ``"stub"``.
    notes:
        Optional free-text notes.

    Raises
    ------
    RegistryError
        If *check_id* is already registered.
    """

    def decorator(cls: type[BaseIntegrityCheck]) -> type[BaseIntegrityCheck]:
        if check_id in _REGISTRY:
            raise RegistryError(
                f"Integrity check ID {check_id!r} is already registered "
                f"(by {_REGISTRY[check_id].__name__!r})."
            )
        _REGISTRY[check_id] = cls
        _REGISTRY_META[check_id] = {
            "id": check_id,
            "label": label or cls.__name__,
            "status": status,
            "notes": notes,
        }
        cls.check_id = check_id  # type: ignore[attr-defined]
        return cls

    return decorator


def get_check(check_id: str) -> type[BaseIntegrityCheck]:
    """
    Return the integrity check class registered under *check_id*.

    Raises
    ------
    RegistryError
        If not found.
    """
    if check_id not in _REGISTRY:
        available = sorted(_REGISTRY)
        raise RegistryError(
            f"No integrity check registered as {check_id!r}. "
            f"Available: {available}"
        )
    return _REGISTRY[check_id]


def list_checks() -> list[dict[str, Any]]:
    """Return a sorted list of integrity check metadata dicts."""
    return [_REGISTRY_META[cid] for cid in sorted(_REGISTRY_META)]


def unregister_check(check_id: str) -> None:
    """
    Remove an integrity check from the registry.

    Raises
    ------
    RegistryError
        If *check_id* is not registered.
    """
    if check_id not in _REGISTRY:
        raise RegistryError(f"No integrity check registered as {check_id!r}.")
    _REGISTRY.pop(check_id, None)
    _REGISTRY_META.pop(check_id, None)


# ---------------------------------------------------------------------------
# Stable API alias
# ---------------------------------------------------------------------------

#: Alias for :func:`unregister_check` using consistent naming convention.
unregister_integrity_check = unregister_check
