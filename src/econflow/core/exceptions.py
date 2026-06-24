"""
econflow.core.exceptions — Platform-wide exception hierarchy.

All APRP-specific exceptions inherit from :class:`APRPError` so callers can
catch the whole family with a single ``except APRPError`` clause while still
discriminating on sub-types when needed.

Exception tree
--------------
APRPError
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
"""

from __future__ import annotations


# ---------------------------------------------------------------------------
# Root
# ---------------------------------------------------------------------------


class APRPError(Exception):
    """Base class for all APRP exceptions."""


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


class ConfigurationError(APRPError):
    """Raised when a project configuration file is invalid."""


class MissingConfigKeyError(ConfigurationError):
    """Raised when a required configuration key is absent."""

    def __init__(self, key: str) -> None:
        super().__init__(f"Required configuration key is missing: '{key}'")
        self.key = key


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


class RegistryError(APRPError):
    """Raised for project registry lookup failures."""


class ProjectNotFoundError(RegistryError):
    """Raised when a requested project ID does not exist in the registry."""

    def __init__(self, project_id: str) -> None:
        super().__init__(f"No project found with ID: '{project_id}'")
        self.project_id = project_id


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------


class PipelineError(APRPError):
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


class IngestionError(APRPError):
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


class ProcessingError(APRPError):
    """Raised for failures during data processing."""


class HarmonisationError(ProcessingError):
    """Raised when country-ID harmonisation cannot be resolved."""


class TransformationError(ProcessingError):
    """Raised when a variable transformation produces invalid output."""


# ---------------------------------------------------------------------------
# Estimation
# ---------------------------------------------------------------------------


class EstimationError(APRPError):
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


class DiagnosticsError(APRPError):
    """Raised when a diagnostic test cannot be computed."""


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------


class OutputError(APRPError):
    """Raised when an output renderer fails to produce its artifact."""
