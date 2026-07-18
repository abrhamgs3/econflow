"""
econflow.estimation.dispatcher — EstimationDispatcher and PipelineContext.

STATUS: Active — sole production dispatch layer as of Phase 5C (2026-07-10).

``pipeline_generic.run_from_config()`` calls
``EstimationDispatcher.dispatch()`` for every model spec.
``config/validator.py`` calls ``EstimationDispatcher.resolve_id()`` during
pre-flight validation to check estimator keys against the live registry.

Architecture Freeze compliance
-------------------------------
``PipelineContext`` implements the specification frozen in
``ARCHITECTURE_FREEZE_v1.md §1.4`` exactly.  ``EstimationDispatcher``
implements the specification frozen in ``§1.5`` exactly.  The cluster-
translation invariant in §1.5 is the authoritative source of truth for
the covariance defaults; see ``_translate_cov()`` for the mapping.

Covariance defaults
-------------------
The pipeline covariance defaults, implemented in ``_translate_cov()``:

    - cluster == "entity"         → cov_type="clustered", cluster_entity=True
    - cluster == "time"           → cov_type="clustered", cluster_time=True
    - no cluster, OLS family      → cov_type="unadjusted"
    - no cluster, other           → cov_type="robust"

``build()`` always sets ``cov_type`` explicitly, overriding any
``optional_parameters`` default on the estimator class.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import pandas as pd

if TYPE_CHECKING:  # pragma: no cover
    from econflow.estimation.base import BaseEstimator, EstimationResult


# ---------------------------------------------------------------------------
# Registry key families for cov_type default logic
# ---------------------------------------------------------------------------

#: Estimator IDs whose pipeline default is cov_type="unadjusted" when no
#: cluster field is present.  This matches pipeline_generic._run_model()
#: line 153: ``model.fit(cov_type="unadjusted")`` for estimator == "OLS".
#: All other estimators default to cov_type="robust" when no cluster is given.
_OLS_IDS: frozenset[str] = frozenset({"ols"})


# ---------------------------------------------------------------------------
# PipelineContext
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PipelineContext:
    """
    Immutable project-level context injected into every dispatcher call.

    This dataclass carries configuration that applies to ALL models in a
    pipeline run.  Per-model configuration (estimator type, regressors,
    cluster) lives in the model spec dict (models.yaml), not here.

    The required fields (``entity_col``, ``time_col``) match the minimum
    specification in ``ARCHITECTURE_FREEZE_v1.md §1.4``.  Optional fields
    are all safe-defaulted so that the frozen=True constraint is permanent
    and backward-compatible extension is always possible.

    Parameters
    ----------
    entity_col:
        Column name for the entity dimension (e.g. ``"firm"``).  Required.
    time_col:
        Column name for the time dimension (e.g. ``"year"``).  Required.
    decimal_places:
        Number of decimal places for formatted output tables.  Must match the
        pipeline default (``Architecture Freeze F-9``).  Default: ``4``.
    weights_col:
        Column name for observation weights, or ``None`` for unweighted
        estimation.  Default: ``None``.
    """

    # Required (Architecture Freeze §1.4)
    entity_col: str
    time_col: str

    # Optional — safe defaults; added per Architecture Freeze §1.4 extension
    # rule: "If additional project-level parameters are needed in a later
    # phase, they are added as optional fields with defaults."
    decimal_places: int = 4
    weights_col: str | None = None


# ---------------------------------------------------------------------------
# Private helper — covariance translation
# ---------------------------------------------------------------------------


def _translate_cov(spec: dict[str, Any], estimator_id: str) -> dict[str, Any]:
    """
    Translate the YAML ``cluster`` field into estimator cov params.

    This is the canonical, single-location implementation of the pipeline
    covariance defaults (``Architecture Freeze §1.5`` cluster-translation
    invariant).  ``EstimationDispatcher.build()`` always calls this function;
    no other code should re-implement this mapping.

    Mapping (mirrors ``pipeline_generic._run_model()`` exactly):

    +-----------------+----------------------------------------------------+
    | cluster value   | translated params                                  |
    +=================+====================================================+
    | ``"entity"``    | ``cov_type="clustered"``, ``cluster_entity=True``  |
    +-----------------+----------------------------------------------------+
    | ``"time"``      | ``cov_type="clustered"``, ``cluster_time=True``    |
    +-----------------+----------------------------------------------------+
    | absent, OLS     | ``cov_type="unadjusted"``                          |
    | family          |                                                    |
    +-----------------+----------------------------------------------------+
    | absent, other   | ``cov_type="robust"``                              |
    +-----------------+----------------------------------------------------+

    Parameters
    ----------
    spec:
        Model specification dict (may contain a ``"cluster"`` key).
    estimator_id:
        Resolved registry key (e.g. ``"ols"``, ``"fe"``, ``"twfe"``).

    Returns
    -------
    dict
        Partial params dict ready to be merged into the full params dict.
    """
    cluster = spec.get("cluster", None)

    if cluster == "entity":
        return {"cov_type": "clustered", "cluster_entity": True}
    if cluster == "time":
        return {"cov_type": "clustered", "cluster_time": True}

    # No cluster key present: default depends on estimator family.
    # OLS-family: "unadjusted" (matches pipeline_generic line 153).
    # Everything else: "robust" (matches pipeline_generic line 167).
    if estimator_id in _OLS_IDS:
        return {"cov_type": "unadjusted"}
    return {"cov_type": "robust"}


# ---------------------------------------------------------------------------
# EstimationDispatcher
# ---------------------------------------------------------------------------


class EstimationDispatcher:
    """
    Translates YAML model specs into instantiated, run-ready estimators.

    All methods are ``@staticmethod``: the dispatcher holds no state and is
    a pure namespace for three translation operations.  This satisfies
    ``Architecture Freeze §1.5`` and makes the class trivially testable
    without instantiation.

    Usage::

        context = PipelineContext(entity_col="firm", time_col="year")
        spec = {"estimator": "FE", "entity_effects": True,
                "time_effects": False, "cluster": "entity",
                "dependent": "invest", "regressors": ["value", "capital"]}
        result = EstimationDispatcher.dispatch(spec, df, context)
    """

    @staticmethod
    def resolve_id(spec: dict[str, Any]) -> str:
        """
        Translate a YAML estimator string to a registry key.

        Rules applied in order:

        1. Strip whitespace and lowercase the ``"estimator"`` value.
           (Default: ``"fe"`` if the key is absent.)
        2. If the result is ``"fe"``, apply the FE adapter:

           - ``entity_effects=True``, ``time_effects=True``  → ``"twfe"``
           - ``entity_effects=True``, ``time_effects=False`` → ``"fe"``
           - ``entity_effects=False``, ``time_effects=False`` → ``"ols"``
             + :class:`DeprecationWarning`

        3. Pass all other strings through as-is (lowercased).

        Parameters
        ----------
        spec:
            Model specification dict as parsed from models.yaml.  Must
            contain an ``"estimator"`` key (defaults to ``"fe"`` if absent).

        Returns
        -------
        str
            Registry key suitable for :func:`get_estimator`.

        Warns
        -----
        DeprecationWarning
            When ``estimator="FE"`` with both effects False.  This mapping
            is semantically equivalent to ``"ols"`` and the explicit key
            should be used instead.

        Examples
        --------
        >>> EstimationDispatcher.resolve_id({"estimator": "OLS"})
        'ols'
        >>> EstimationDispatcher.resolve_id(
        ...     {"estimator": "FE", "entity_effects": True, "time_effects": True}
        ... )
        'twfe'
        """
        raw = spec.get("estimator", "fe")
        key = str(raw).strip().lower()

        if key == "fe":
            entity_effects = bool(spec.get("entity_effects", False))
            time_effects = bool(spec.get("time_effects", False))

            if entity_effects and time_effects:
                return "twfe"
            if entity_effects:
                return "fe"
            # Both False: FE with no effects is equivalent to PooledOLS.
            warnings.warn(
                "estimator='FE' with entity_effects=False and "
                "time_effects=False is equivalent to PooledOLS.  "
                "Use estimator='OLS' explicitly.  "
                "This implicit mapping will be removed in EconFlow v2.0.",
                DeprecationWarning,
                stacklevel=2,
            )
            return "ols"

        return key

    @staticmethod
    def build(spec: dict[str, Any], context: PipelineContext) -> BaseEstimator:
        """
        Translate a model spec + context into an instantiated (unrun) estimator.

        The returned estimator has ``params`` fully populated with all required
        and translated values.  Call ``.run(df)`` on the result to fit the
        model.

        The ``spec`` dict is **not mutated**.

        Covariance handling
        -------------------
        The ``cov_type`` in the returned estimator's params is always set
        explicitly via :func:`_translate_cov`.  This overrides any
        ``optional_parameters`` default on the estimator class.  This is the
        fix for the covariance mismatch documented in
        ``ARCHITECTURE_FREEZE_v1.md §1.5``.

        Parameters
        ----------
        spec:
            Model specification dict from models.yaml.  Must contain
            ``"dependent"`` and ``"regressors"`` keys.
        context:
            Project-level context supplying ``entity_col``, ``time_col``,
            and optional fitting settings.

        Returns
        -------
        BaseEstimator
            An instantiated but unrun estimator with params populated.

        Raises
        ------
        econflow.core.exceptions.RegistryError
            If the resolved estimator ID is not in the registry.
        KeyError
            If ``"dependent"`` or ``"regressors"`` is missing from ``spec``.
        """
        # Lazy import: avoids making this module's top-level import order
        # sensitive to estimation package initialisation order.
        from econflow.estimation.registry import get_estimator  # noqa: PLC0415

        estimator_id = EstimationDispatcher.resolve_id(spec)
        EstimatorClass = get_estimator(estimator_id)

        # Build params from scratch (never mutate spec).
        cov_params = _translate_cov(spec, estimator_id)

        params: dict[str, Any] = {
            # Required fields — all concrete estimators expect these.
            "dependent": spec["dependent"],
            "regressors": list(spec["regressors"]),
            # Project context — injected from PipelineContext.
            "entity_col": context.entity_col,
            "time_col": context.time_col,
            # Covariance — always explicit; overrides estimator defaults.
            **cov_params,
            # Effects — passed through from spec for documentation and
            # forward-compatibility with Phase 5 estimator updates.
            # Note: the behaviour is determined by the *class* (EntityFE vs
            # TwoWayFE), not by these params values, in the current framework.
            "entity_effects": bool(spec.get("entity_effects", False)),
            "time_effects": bool(spec.get("time_effects", False)),
        }

        # Optional: weights
        if context.weights_col is not None:
            params["weights_col"] = context.weights_col

        return EstimatorClass(params=params)

    @staticmethod
    def dispatch(
        spec: dict[str, Any],
        df: pd.DataFrame,
        context: PipelineContext,
    ) -> EstimationResult:
        """
        Build the estimator and run it.

        The sole production call site for model estimation as of Phase 5C.
        Its contract is exactly two lines: build then run
        (``Architecture Freeze §1.5``).

        Parameters
        ----------
        spec:
            Model specification dict from models.yaml.
        df:
            Raw (non-indexed) panel DataFrame.
        context:
            Project-level context.

        Returns
        -------
        EstimationResult
            Fully populated result with diagnostics attached.

        Raises
        ------
        econflow.core.exceptions.RegistryError
            If the estimator key is not in the registry.
        econflow.estimation.base.EstimatorError
            If estimation fails.
        """
        estimator = EstimationDispatcher.build(spec, context)
        return estimator.run(df)
