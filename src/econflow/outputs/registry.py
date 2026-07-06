"""
econflow.outputs.registry — Renderer auto-registration system.

Usage — registering a renderer
--------------------------------
::

    from econflow.outputs.registry import register_renderer
    from econflow.outputs.base import BaseRenderer

    @register_renderer("myformat", label="My Custom Format")
    class MyRenderer(BaseRenderer):
        ...

Usage — resolving a renderer from config
------------------------------------------
::

    from econflow.outputs.registry import get_renderer

    RendererClass = get_renderer("latex")
    rendered = RendererClass().render(table)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from econflow.core.exceptions import RegistryError

if TYPE_CHECKING:
    from econflow.outputs.base import BaseRenderer

_REGISTRY: dict[str, type[BaseRenderer]] = {}
_REGISTRY_META: dict[str, dict[str, Any]] = {}


def register_renderer(
    renderer_id: str,
    *,
    label: str = "",
    status: str = "implemented",
    file_extension: str = "",
    notes: str = "",
) -> Any:
    """
    Class decorator that registers a renderer in the global registry.

    Parameters
    ----------
    renderer_id:
        Unique short identifier (e.g. ``"csv"``, ``"latex"``).
    label:
        Human-readable name.  Defaults to the class name.
    status:
        ``"implemented"`` or ``"stub"``.
    file_extension:
        Default file extension including the dot (e.g. ``".csv"``).
    notes:
        Optional notes shown in ``econflow info``.

    Raises
    ------
    RegistryError
        If *renderer_id* is already registered.
    """
    def decorator(cls: type[BaseRenderer]) -> type[BaseRenderer]:
        if renderer_id in _REGISTRY:
            raise RegistryError(
                f"Renderer ID {renderer_id!r} is already registered "
                f"(by {_REGISTRY[renderer_id].__name__!r})."
            )
        _REGISTRY[renderer_id] = cls
        _REGISTRY_META[renderer_id] = {
            "id":             renderer_id,
            "label":          label or cls.__name__,
            "status":         status,
            "file_extension": file_extension,
            "notes":          notes,
        }
        cls.renderer_id = renderer_id  # type: ignore[attr-defined]
        return cls

    return decorator


def get_renderer(renderer_id: str) -> type[BaseRenderer]:
    """
    Return the renderer class registered under *renderer_id*.

    Raises
    ------
    RegistryError
        If *renderer_id* is not found.
    """
    if renderer_id not in _REGISTRY:
        available = sorted(_REGISTRY)
        raise RegistryError(
            f"No renderer registered as {renderer_id!r}. "
            f"Available renderers: {available}"
        )
    return _REGISTRY[renderer_id]


def list_renderers() -> list[dict[str, Any]]:
    """Return a sorted list of renderer metadata dicts."""
    return [_REGISTRY_META[rid] for rid in sorted(_REGISTRY_META)]


def unregister_renderer(renderer_id: str) -> None:
    """
    Remove a renderer from the registry.

    Raises
    ------
    RegistryError
        If *renderer_id* is not registered.
    """
    if renderer_id not in _REGISTRY:
        raise RegistryError(f"No renderer registered as {renderer_id!r}.")
    _REGISTRY.pop(renderer_id)
    _REGISTRY_META.pop(renderer_id)
