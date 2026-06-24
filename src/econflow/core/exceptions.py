"""
econflow.core.exceptions — Scaffold exception hierarchy.

All EconFlow scaffold exceptions inherit from :class:`EconFlowCoreError` so
callers can catch the whole family with a single ``except EconFlowCoreError``
clause while still discriminating on sub-types when needed.

Exception tree
--------------
EconFlowCoreError
├── ConfigurationError
│   └── MissingConfigKeyError
├── RegistryError
│   └── ProjectNotFoundError
├── PipelineError
│   └── StageExecutionError
├── IngestionError
│   ├── DownloadError
│   └── CacheError
├── ProcessingError
│   ├── HarmonisationError
│   └── TransformationError
├── EstimationError
│   └── ConvergenceError
├── DiagnosticsError
└── OutputError

Backward compatibility
----------------------
``APRPError`` is kept as a deprecated alias for ``EconFlowCoreError``.
It will be removed in v0.3.0.
"""

from __future__ import annotations

import warnings


# ---------------------------------------------------------------------------
# Root
# ---------------------------------------------------------------------------


class EconFlowCoreError(Exception):
    """Base class for all EconFlow scaffold (core) exceptions."""


# Deprecated alias
class APRPError(EconFlowCoreError):
    """Deprecated alias for EconFlowCoreError.  Will be removed in v0.3.0."""

    def __init__(self, *args, **kwargs):
        warnings.warn(
            "APRPError is deprecated and will be removed in EconFlow v0.3.0. "
            "Use EconFlowCoreError instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        super().__init__(*args, **kwargs)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


class ConfigurationError(EconFlowCoreError):
    """Raised when a project configuration file is invalid."""


class MissingConfigKeyError(ConfigurationError):
    """Raised when a required configuration key is absent."""

    def __init__(self, key: str) -> None:
        super().__init__(f"Required configuration key is missing: '{key}'")
        self.key = key


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


class RegistryError(EconFlowCoreError):
    """Raised for project registry lookup failures."""


class ProjectNotFoundError(RegistryError):
    """Raised when a requested project ID does not exist in the registry."""

    def __init__(self, project_id: str) -> None:
        super().__init__(f"No project found with ID: '{project_id}'")
        self.project_id = project_id


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------


class PipelineError(EconFlowCoreError):
    """Raised for pipeline orchestration failures."""


class StageExecutionError(PipelineError):
    """Raised when a pipeline stage fails during execution."""

    def __init__(self, stage: str, reason: str) -> None:
        super().__init__(f"Stage '{stage}' failed: {reason}")
        self.stage = stage
        self.reason = reason


# ---------------------------------------------------------------------------
# Ingestion
# ---------------------------------------------------------------------------


class IngestionError(EconFlowCoreError):
    """Raised for failures during data ingestion."""


class DownloadError(IngestionError):
    """Raised when an HTTP download fails."""

    def __init__(self, url: str, status_code: int | None = None) -> None:
        msg = f"Failed to download '{url}'"
        if status_code is not None:
            msg += f" (HTTP {status_code})"
        super().__init__(msg)
        self.url = url
        self.status_code = status_code


class CacheError(IngestionError):
    """Raised when the download cache cannot be read or written."""


# ---------------------------------------------------------------------------
# Processing
# ---------------------------------------------------------------------------


class ProcessingError(EconFlowCoreError):
    """Raised for failures during data processing."""


class HarmonisationError(ProcessingError):
    """Raised when entity-ID harmonisation cannot be resolved."""


class TransformationError(ProcessingError):
    """Raised when a variable transformation produces invalid output."""


# ---------------------------------------------------------------------------
# Estimation
# ---------------------------------------------------------------------------


class EstimationError(EconFlowCoreError):
    """Raised for failures during econometric estimation."""


class ConvergenceError(EstimationError):
    """Raised when an iterative estimator (GMM, quantile) fails to converge."""

    def __init__(self, estimator: str, iterations: int) -> None:
        super().__init__(
            f"Estimator '{estimator}' did not converge after {iterations} iterations."
        )
        self.estimator = estimator
        self.iterations = iterations


# ---------------------------------------------------------------------------
# Diagnostics
# ---------------------------------------------------------------------------


class DiagnosticsError(EconFlowCoreError):
    """Raised when a diagnostic test cannot be computed."""


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------


class OutputError(EconFlowCoreError):
    """Raised when an output renderer fails to produce its artifact."""
