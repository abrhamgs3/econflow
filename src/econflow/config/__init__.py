"""
econflow.config — Configuration models, linting, and documentation.

Public API
----------
Models (Pydantic v2)
~~~~~~~~~~~~~~~~~~~~
.. autoclass:: econflow.config.models.ProjectConfig
.. autoclass:: econflow.config.models.ModelsConfig
.. autoclass:: econflow.config.models.OutputsConfig
.. autoclass:: econflow.config.models.ModelSpec

Linting
~~~~~~~
.. autoclass:: econflow.config.linter.ConfigLinter
.. autoclass:: econflow.config.linter.LintIssue

Reference documentation
~~~~~~~~~~~~~~~~~~~~~~~
.. autofunction:: econflow.config.docs.generate_config_reference
.. autofunction:: econflow.config.docs.write_config_reference
"""

from __future__ import annotations

from econflow.config.docs import generate_config_reference, write_config_reference
from econflow.config.linter import ConfigLinter, LintIssue
from econflow.config.models import (
    ModelsConfig,
    ModelSpec,
    OutputsConfig,
    ProjectConfig,
)
from econflow.config.validator import ConfigValidator, ValidationIssue, ValidationResult

__all__ = [
    # Models
    "ProjectConfig",
    "ModelsConfig",
    "OutputsConfig",
    "ModelSpec",
    # Linting
    "ConfigLinter",
    "LintIssue",
    # Documentation generation
    "generate_config_reference",
    "write_config_reference",
    # Validator
    "ConfigValidator",
    "ValidationResult",
    "ValidationIssue",
]
