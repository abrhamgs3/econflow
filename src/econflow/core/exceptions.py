"""
econflow.core.exceptions — Scaffold exception hierarchy.

All EconFlow scaffold exceptions inherit from :class:`EconFlowCoreError` so
callers can catch the whole family with a single ``except EconFlowCoreError``
clause while still discriminating on sub-types when needed.

Exception tree
--------------
EconFlowError (econflow.exceptions)
└── EconFlowCoreError
├── ConfigurationError
│   ├── MissingConfigKeyError
│   └── ConfigValidationError
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
├── OutputError
└── IntegrityError
    └── CertificateError

Backward compatibility
----------------------
``APRPError`` is kept as a deprecated alias for ``EconFlowCoreError``.
It will be removed in v0.3.0.
"""

from __future__ import annotations

import warnings

from econflow.exceptions import EconFlowError  # noqa: E402

# ---------------------------------------------------------------------------
# Root
# ---------------------------------------------------------------------------


class EconFlowCoreError(EconFlowError):
    """Base class for all EconFlow scaffold (core) exceptions.

    Inherits from :class:`~econflow.exceptions.EconFlowError` so that a
    single ``except EconFlowError`` clause catches both pipeline-layer and
    core-layer exceptions.
    """


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


class ConfigValidationError(ConfigurationError):
    """
    Raised when one or more configuration files fail validation.

    Carries every :class:`~econflow.config.validator.ValidationIssue` that was
    collected across all four validation stages (YAML syntax, Pydantic schema,
    semantic, cross-file).  Only *errors* (not warnings) trigger this exception.

    Parameters
    ----------
    issues:
        All validation issues collected (errors + warnings).
    config_path:
        Path to the primary ``config.yaml`` file, used in the message.

    Attributes
    ----------
    issues : list
        All :class:`~econflow.config.validator.ValidationIssue` objects.
    errors : list
        Subset with ``severity == "error"``.
    warnings : list
        Subset with ``severity == "warning"``.
    error_count : int
        Number of errors.
    """

    def __init__(self, issues: list, config_path: object = None) -> None:
        self.issues = issues
        errors = [i for i in issues if getattr(i, "severity", None) == "error"]
        warnings = [i for i in issues if getattr(i, "severity", None) == "warning"]
        self.errors = errors
        self.warnings = warnings
        self.error_count = len(errors)

        location = f" ({config_path})" if config_path else ""
        lines = [
            f"Configuration validation failed{location}: "
            f"{len(errors)} error(s), {len(warnings)} warning(s).",
        ]
        for issue in errors[:10]:
            lines.append(
                f"  [{getattr(issue, 'stage', '?')}] {getattr(issue, 'source', '')} "
                f"{getattr(issue, 'location', '')}: {getattr(issue, 'message', issue)}"
            )
        if len(errors) > 10:
            lines.append(f"  … and {len(errors) - 10} more error(s).")
        super().__init__("\n".join(lines))


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


# ---------------------------------------------------------------------------
# Integrity
# ---------------------------------------------------------------------------


class IntegrityError(EconFlowCoreError):
    """Raised for research integrity and reproducibility failures."""


class CertificateError(IntegrityError):
    """Raised when a ReproducibilityCertificate cannot be read or written."""
