"""
econflow.estimation.protocol — Library-agnostic Estimator Protocol.

Architecture Stabilization Milestone 3.

This module defines:

* :data:`BACKEND_*` string constants — canonical identifiers for supported
  estimation libraries.
* :class:`BackendCapabilities` — a dataclass advertising what a backend can do.
* :class:`EstimatorProtocol` — a ``typing.Protocol`` that **any** estimator
  class must structurally satisfy, regardless of whether it inherits from
  :class:`~econflow.estimation.base.BaseEstimator`.

Design intent
-------------
The previous ``BaseEstimator`` ABC referenced ``pd.DataFrame`` in every
abstract-method signature and contained ``_to_panel()``, a helper that
creates the ``(entity, time)`` MultiIndex required by ``linearmodels``.
This made the *interface* implicitly dependent on a single library even
though concrete estimators already used lazy imports.

``EstimatorProtocol`` decouples the *structural contract* from the
*implementation detail*:

* A ``linearmodels``-backed class satisfies the protocol.
* A ``statsmodels``-, ``pyfixest``-, ``DoubleML``-, or ``PyMC``-backed
  class satisfies the protocol.
* A fully custom class satisfies the protocol — no inheritance required.

Backward compatibility
----------------------
Nothing in this module modifies ``BaseEstimator``.  All existing estimators
automatically satisfy ``EstimatorProtocol`` because they already implement
``fit``, ``validate``, ``diagnostics``, and ``run``.  Checking
``isinstance(est, EstimatorProtocol)`` therefore returns ``True`` for every
registered estimator without any code changes to those classes.

Usage
-----
::

    from econflow.estimation.protocol import EstimatorProtocol, BACKEND_LINEARMODELS

    # Structural check (no inheritance required)
    assert isinstance(my_estimator, EstimatorProtocol)

    # Custom estimator from any library
    class MyStatsmodelsEstimator:
        estimator_id = "my_ols"
        name        = "My OLS"
        backend     = BACKEND_STATSMODELS

        def fit(self, data) -> EstimationResult:       ...
        def validate(self, data) -> None:              ...
        def diagnostics(self, result) -> list:         ...
        def run(self, data) -> EstimationResult:       ...

    assert isinstance(MyStatsmodelsEstimator(), EstimatorProtocol)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from econflow.estimation.result import DiagnosticResult, EstimationResult

__all__ = [
    # Backend constants
    "BACKEND_LINEARMODELS",
    "BACKEND_STATSMODELS",
    "BACKEND_PYFIXEST",
    "BACKEND_DOUBLEML",
    "BACKEND_PYMC",
    "BACKEND_CUSTOM",
    "KNOWN_BACKENDS",
    # Types
    "BackendCapabilities",
    "EstimatorProtocol",
]


# ---------------------------------------------------------------------------
# Backend constants
# ---------------------------------------------------------------------------

#: Canonical identifier for the ``linearmodels`` backend.
BACKEND_LINEARMODELS: str = "linearmodels"

#: Canonical identifier for the ``statsmodels`` backend.
BACKEND_STATSMODELS: str = "statsmodels"

#: Canonical identifier for the ``pyfixest`` backend.
BACKEND_PYFIXEST: str = "pyfixest"

#: Canonical identifier for the ``DoubleML`` backend.
BACKEND_DOUBLEML: str = "doubleml"

#: Canonical identifier for the ``PyMC`` backend.
BACKEND_PYMC: str = "pymc"

#: Canonical identifier for fully custom (no external library) estimators.
BACKEND_CUSTOM: str = "custom"

#: The set of all recognised backend identifiers.
KNOWN_BACKENDS: frozenset[str] = frozenset(
    {
        BACKEND_LINEARMODELS,
        BACKEND_STATSMODELS,
        BACKEND_PYFIXEST,
        BACKEND_DOUBLEML,
        BACKEND_PYMC,
        BACKEND_CUSTOM,
    }
)


# ---------------------------------------------------------------------------
# BackendCapabilities
# ---------------------------------------------------------------------------


@dataclass
class BackendCapabilities:
    """
    Declares the estimation capabilities supported by a backend.

    An estimator's ``_backend_capabilities()`` method returns one of these
    objects so that higher-level runners (sensitivity suites, replication
    engines) can skip specifications that the backend does not support.

    Attributes
    ----------
    backend:
        One of the ``BACKEND_*`` constants.
    supports_panel:
        True if the backend can handle (entity, time) panel structures.
    supports_cross_section:
        True if cross-sectional data (no time dimension) is accepted.
    supports_time_series:
        True if single-entity time-series data is accepted.
    supports_spatial:
        True if spatial (lat/lon) dependencies can be modelled.
    supports_bayesian:
        True if the backend produces posterior distributions (PyMC etc.).
    supports_iv:
        True if instrumental-variable / 2SLS estimation is available.
    supports_quantile:
        True if quantile regression is available.
    supports_gmm:
        True if GMM / Arellano-Bond dynamic panel estimation is available.
    """

    backend: str = BACKEND_CUSTOM
    supports_panel: bool = False
    supports_cross_section: bool = False
    supports_time_series: bool = False
    supports_spatial: bool = False
    supports_bayesian: bool = False
    supports_iv: bool = False
    supports_quantile: bool = False
    supports_gmm: bool = False

    def __post_init__(self) -> None:
        if self.backend not in KNOWN_BACKENDS:
            raise ValueError(
                f"Unknown backend {self.backend!r}. "
                f"Known backends: {sorted(KNOWN_BACKENDS)}"
            )


# ---------------------------------------------------------------------------
# EstimatorProtocol
# ---------------------------------------------------------------------------


@runtime_checkable
class EstimatorProtocol(Protocol):
    """
    Structural protocol that every EconFlow estimator must satisfy.

    This is a ``typing.Protocol`` — conformance is **structural**, not
    nominal.  Any class that implements the four methods and two attributes
    below is automatically a valid estimator, regardless of whether it
    inherits from :class:`~econflow.estimation.base.BaseEstimator`.

    Required attributes
    -------------------
    estimator_id : str
        Unique short identifier registered in the estimator registry
        (e.g. ``"twfe"``).
    name : str
        Human-readable display name (e.g. ``"Two-Way Fixed Effects"``).
    backend : str
        The underlying estimation library; one of the ``BACKEND_*`` constants.

    Required methods
    ----------------
    validate(data) → None
        Validate *data* and estimator parameters; raise on failure.
    fit(data) → EstimationResult
        Fit the model and return a populated result.
    diagnostics(result) → list[DiagnosticResult]
        Compute post-fit diagnostics; return ``[]`` if none.
    run(data) → EstimationResult
        Full pipeline: ``validate → fit → diagnostics``.

    Notes
    -----
    ``@runtime_checkable`` enables ``isinstance(obj, EstimatorProtocol)``
    checks at runtime.  This only tests for the presence of the required
    attributes and methods — it does **not** verify method signatures or
    return types.  Use static type checkers (mypy / pyright) for full
    protocol conformance verification.

    Examples
    --------
    Registering a custom statsmodels-backed estimator::

        from econflow.estimation.protocol import EstimatorProtocol, BACKEND_STATSMODELS
        from econflow.estimation.result import EstimationResult, DiagnosticResult

        class MyOLS:
            estimator_id = "my_ols"
            name         = "My OLS (statsmodels)"
            backend      = BACKEND_STATSMODELS

            def fit(self, data) -> EstimationResult:       ...
            def validate(self, data) -> None:              ...
            def diagnostics(self, result) -> list:         ...
            def run(self, data) -> EstimationResult:       ...

        assert isinstance(MyOLS(), EstimatorProtocol)   # True — no ABC needed
    """

    # ----- required attributes -----
    estimator_id: str
    name: str
    backend: str

    # ----- required methods -----
    def fit(self, data: Any) -> "EstimationResult": ...
    def validate(self, data: Any) -> None: ...
    def diagnostics(self, result: "EstimationResult") -> "list[DiagnosticResult]": ...
    def run(self, data: Any) -> "EstimationResult": ...
