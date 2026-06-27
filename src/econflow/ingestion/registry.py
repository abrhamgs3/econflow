"""
econflow.ingestion.registry — Connector auto-registration system.

Usage — registering a new connector
-------------------------------------
Decorate the connector class with :func:`register`::

    from econflow.ingestion.registry import register

    @register("my_source", label="My Data Source")
    class MyConnector(AbstractConnector):
        ...

The connector is then available via :func:`get_connector` and appears in
``econflow info`` without any other code change.

Usage — retrieving a connector
--------------------------------
::

    from econflow.ingestion.registry import get_connector

    ConnectorClass = get_connector("world_bank")
    conn = ConnectorClass(params={"indicators": ["IT.NET.USER.ZS"]})

Design
------
The registry is a module-level dict populated at import time via the
``@register`` decorator.  This means connectors register themselves as soon
as their module is imported.  The :mod:`econflow.ingestion` package imports
all built-in connectors in its ``__init__.py``, so they are always available
when ``econflow.ingestion`` is imported.

Third-party connectors can register by importing ``register`` and decorating
their class.  No modification to existing EconFlow code is required.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from econflow.ingestion.base import AbstractConnector

# ---------------------------------------------------------------------------
# Internal registry store
# ---------------------------------------------------------------------------

#: Maps connector_id → connector class.
_REGISTRY: dict[str, type[AbstractConnector]] = {}

#: Maps connector_id → display metadata (label, status, notes).
_REGISTRY_META: dict[str, dict[str, str]] = {}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def register(
    connector_id: str,
    *,
    label: str = "",
    status: str = "implemented",
    notes: str = "",
) -> Any:
    """
    Class decorator that registers a connector in the global registry.

    Parameters
    ----------
    connector_id:
        Unique short identifier (e.g. ``"csv"``, ``"world_bank"``).
        Must be unique across all registered connectors.
    label:
        Human-readable name shown in ``econflow info``.
        Defaults to the class name if empty.
    status:
        ``"implemented"`` or ``"stub"``.  Stub connectors are listed in
        ``econflow info`` but raise ``NotImplementedError`` at runtime.
    notes:
        Optional free-text notes shown in ``econflow info``.

    Raises
    ------
    ValueError
        If *connector_id* is already registered.
    """
    def decorator(cls: type[AbstractConnector]) -> type[AbstractConnector]:
        if connector_id in _REGISTRY:
            raise ValueError(
                f"Connector ID {connector_id!r} is already registered "
                f"(by {_REGISTRY[connector_id].__name__!r}). "
                "Use a different connector_id or unregister the existing one first."
            )
        _REGISTRY[connector_id] = cls
        _REGISTRY_META[connector_id] = {
            "id": connector_id,
            "label": label or cls.__name__,
            "status": status,
            "notes": notes,
        }
        # Stamp the class so it knows its own registry ID
        cls.connector_id = connector_id  # type: ignore[attr-defined]
        return cls

    return decorator


def get_connector(connector_id: str) -> type[AbstractConnector]:
    """
    Return the connector class registered under *connector_id*.

    Parameters
    ----------
    connector_id:
        Short identifier (e.g. ``"csv"``, ``"world_bank"``).

    Raises
    ------
    KeyError
        If *connector_id* is not found.  The error message lists available IDs.
    """
    if connector_id not in _REGISTRY:
        available = sorted(_REGISTRY)
        raise KeyError(
            f"No connector registered as {connector_id!r}. "
            f"Available connectors: {available}"
        )
    return _REGISTRY[connector_id]


def list_connectors() -> list[dict[str, str]]:
    """
    Return a list of dicts describing all registered connectors.

    Each dict has keys: ``id``, ``label``, ``status``, ``notes``.
    Used by ``econflow info`` to populate the connector table.
    """
    return [_REGISTRY_META[cid] for cid in sorted(_REGISTRY_META)]


def unregister(connector_id: str) -> None:
    """
    Remove a connector from the registry.

    Intended primarily for testing.  Not safe to call while connectors
    are in use.

    Parameters
    ----------
    connector_id:
        The ID to remove.  Silently does nothing if not registered.
    """
    _REGISTRY.pop(connector_id, None)
    _REGISTRY_META.pop(connector_id, None)
