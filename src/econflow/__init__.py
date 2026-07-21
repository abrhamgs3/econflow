"""
EconFlow — Panel Econometrics Research Platform.

A reusable, config-driven framework for reproducible panel econometric research.

Quick start
-----------
    git clone https://github.com/abrhamgs3/econflow.git
    cd econflow
    pip install -e ".[dev]"
    econflow init my_study
    cd my_study
    econflow validate
    econflow run --config config/config.yaml --models config/models.yaml \
                 --outputs config/outputs.yaml

Core estimation API (v0.1.0+)
------------------------------
    from econflow import PooledOLS, EntityFE, TwoWayFE
    from econflow import EstimationResult, DiagnosticResult
    from econflow import register_estimator, list_estimators

Available subpackages
---------------------
ingestion       CSV, World Bank, OECD, PWT, FRED data connectors
estimation      Panel estimators: PooledOLS, EntityFE, TwoWayFE, RE, FD, IV2SLS
diagnostics     Post-estimation tests: Hausman, Breusch-Pagan, Pesaran CD, VIF
outputs         Table, figure, and report renderers (CSV, LaTeX, Markdown, HTML, JSON)
integrity       Provenance certificates, drift detection, replication packages
replication     Blind replication, execution planning, output comparison
config          YAML configuration models, linter, and reference docs

Not yet available (planned for v0.2+)
--------------------------------------
processing      Harmonisation, feature engineering, composite index, TFP (stubs)
sensitivity     SensitivityRunner, ResultsComparison (stubs)
"""

__version__ = "1.0.0"
__author__ = "Ab"
__email__ = "abrhamgs3@gmail.com"

from econflow.core.exceptions import EconFlowCoreError

# Core estimation API — re-exported for top-level discoverability.
# Full API: from econflow.estimation import ...
from econflow.estimation import (
    BaseEstimator,
    DiagnosticResult,
    EntityFE,
    EstimationResult,
    PooledOLS,
    TwoWayFE,
    list_estimators,
    register_estimator,
)
from econflow.exceptions import (
    DataValidationError,
    EconFlowError,
    MergeError,
    ModelSpecificationError,
    PipelineError,
)

__all__ = [
    "__version__",
    # Root exception — catches everything
    "EconFlowError",
    # Core scaffold exceptions (share EconFlowError root)
    "EconFlowCoreError",
    # NOTE: "AIProdError" is intentionally NOT in __all__ (API Freeze C-2,
    # 2026-07-17). Including a name slated for removal in __all__ would
    # commit to it for the life of the 1.0.x series and turn the planned
    # v0.3.0 removal into a semver violation. The name remains importable
    # via `from econflow import AIProdError` (module __getattr__ below)
    # for runtime backward compatibility, but is no longer part of the
    # committed public API surface.
    # Pipeline-layer exception types
    "DataValidationError",
    "MergeError",
    "ModelSpecificationError",
    "PipelineError",
    # Core estimation — top-level convenience re-exports
    "BaseEstimator",
    "EstimationResult",
    "DiagnosticResult",
    "PooledOLS",
    "EntityFE",
    "TwoWayFE",
    "register_estimator",
    "list_estimators",
]


def __getattr__(name: str):
    """PEP 562 module-level attribute access for deprecated names.

    Serves ``AIProdError`` on demand (with a ``DeprecationWarning``) without
    listing it in ``__all__``. This preserves ``from econflow import
    AIProdError`` and ``econflow.AIProdError`` for existing code while
    keeping the name out of the frozen 1.0 API contract (API Freeze C-2).
    The alias is planned for removal in v0.3.0.
    """
    if name == "AIProdError":
        import warnings

        from econflow.exceptions import AIProdError as _AIProdError

        warnings.warn(
            "econflow.AIProdError is a deprecated alias for econflow.EconFlowError "
            "and will be removed in v0.3.0. It is not part of the frozen 1.0 "
            "public API. Use econflow.EconFlowError instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        # Cache on the module so CPython's `from econflow import AIProdError`
        # (which probes the attribute twice internally) only warns once, and
        # subsequent lookups skip __getattr__ entirely.
        globals()[name] = _AIProdError
        return _AIProdError
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
