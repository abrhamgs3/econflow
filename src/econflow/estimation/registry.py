"""
econflow.estimation.registry — Estimator auto-registration system.

Works identically to :mod:`econflow.ingestion.registry` but for estimators.

Usage — registering an estimator
----------------------------------
::

    from econflow.estimation.registry import register
    from econflow.estimation.base import BaseEstimator

    @register("my_estimator", label="My Custom Estimator", backend="linearmodels")
    class MyEstimator(BaseEstimator):
        ...

Usage — resolving an estimator from YAML config
-------------------------------------------------
::

    from econflow.estimation.registry import get_estimator

    EstimatorClass = get_estimator(config["estimator"])  # e.g. "twfe"
    model = EstimatorClass(params=config)
    result = model.run(data)

Architecture Stabilization Milestone 3
---------------------------------------
``@register`` now accepts an optional ``backend`` keyword argument.  If
omitted, the decorator reads ``cls.backend`` from the class after decoration.
This means existing ``@register(...)`` calls without ``backend=`` continue to
work — the class attribute set in each concrete estimator is used instead.

``list_estimators()`` now includes a ``"backend"`` key in each entry dict.

``list_by_backend(backend)`` is a new helper that filters the registry by
backend identifier, e.g. ``list_by_backend("linearmodels")``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from econflow.core.exceptions import RegistryError

if TYPE_CHECKING:
    from econflow.estimation.base import BaseEstimator

# ---------------------------------------------------------------------------
# Internal registry
# ---------------------------------------------------------------------------

#: Maps estimator_id -> estimator class.
_REGISTRY: dict[str, type[BaseEstimator]] = {}

#: Maps estimator_id -> display metadata.
_REGISTRY_META: dict[str, dict[str, Any]] = {}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def register(
    estimator_id: str,
    *,
    label: str = "",
    status: str = "implemented",
    notes: str = "",
    supported_data: list[str] | None = None,
    backend: str = "",
) -> Any:
    """
    Class decorator that registers an estimator in the global registry.

    Parameters
    ----------
    estimator_id:
        Unique short identifier (e.g. ``"ols"``, ``"twfe"``).
    label:
        Human-readable name shown in ``econflow info``.
        Defaults to the class name if empty.
    status:
        ``"implemented"`` or ``"stub"``.
    notes:
        Optional notes shown in ``econflow info``.
    supported_data:
        Data formats this estimator supports (e.g. ``["balanced_panel",
        "unbalanced_panel"]``).  Defaults to ``["panel"]``.
    backend:
        The underlying estimation library (e.g. ``"linearmodels"``).
        Defaults to the class's ``backend`` attribute if omitted.
        One of the ``BACKEND_*`` constants in
        :mod:`econflow.estimation.protocol`.

    Raises
    ------
    RegistryError
        If *estimator_id* is already registered.
    """
    _supported = supported_data or ["panel"]

    def decorator(cls: type[BaseEstimator]) -> type[BaseEstimator]:
        if estimator_id in _REGISTRY:
            raise RegistryError(
                f"Estimator ID {estimator_id!r} is already registered "
                f"(by {_REGISTRY[estimator_id].__name__!r}). "
                "Use a different estimator_id or unregister first."
            )
        # Resolve backend: explicit kwarg > class attribute > "unknown"
        _backend = backend or getattr(cls, "backend", "unknown")
        _REGISTRY[estimator_id] = cls
        _REGISTRY_META[estimator_id] = {
            "id":             estimator_id,
            "label":          label or cls.__name__,
            "status":         status,
            "notes":          notes,
            "supported_data": _supported,
            "backend":        _backend,
        }
        cls.estimator_id = estimator_id  # type: ignore[attr-defined]
        return cls

    return decorator


def get_estimator(estimator_id: str) -> type[BaseEstimator]:
    """
    Return the estimator class registered under *estimator_id*.

    Raises
    ------
    RegistryError
        If *estimator_id* is not found.  The error message lists available IDs.
    """
    if estimator_id not in _REGISTRY:
        available = sorted(_REGISTRY)
        raise RegistryError(
            f"No estimator registered as {estimator_id!r}. "
            f"Available estimators: {available}"
        )
    return _REGISTRY[estimator_id]


def list_estimators() -> list[dict[str, Any]]:
    """
    Return a list of dicts describing all registered estimators.

    Each dict has keys: ``id``, ``label``, ``status``, ``notes``,
    ``supported_data``, ``backend``.  Used by ``econflow info`` to populate
    the estimator table.
    """
    return [_REGISTRY_META[eid] for eid in sorted(_REGISTRY_META)]


def list_by_backend(backend: str) -> list[dict[str, Any]]:
    """
    Return registry entries whose ``backend`` matches *backend*.

    Parameters
    ----------
    backend:
        One of the ``BACKEND_*`` constants from
        :mod:`econflow.estimation.protocol` (e.g. ``"linearmodels"``).

    Returns
    -------
    list[dict[str, Any]]
        Subset of :func:`list_estimators` filtered by backend, sorted by id.

    Examples
    --------
    ::

        from econflow.estimation.registry import list_by_backend
        lm_estimators = list_by_backend("linearmodels")
        # [{'id': 'fd', 'backend': 'linearmodels', ...}, ...]
    """
    return [
        meta
        for meta in sorted(_REGISTRY_META.values(), key=lambda m: m["id"])
        if meta.get("backend") == backend
    ]


def unregister(estimator_id: str) -> None:
    """
    Remove an estimator from the registry.  Intended for testing only.

    Raises
    ------
    RegistryError
        If *estimator_id* is not registered.
    """
    if estimator_id not in _REGISTRY:
        raise RegistryError(f"No estimator registered as {estimator_id!r}.")
    _REGISTRY.pop(estimator_id, None)
    _REGISTRY_META.pop(estimator_id, None)
