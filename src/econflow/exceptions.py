"""
EconFlow framework exception hierarchy.

Why custom exceptions?
----------------------
Generic ``Exception`` or ``ValueError`` tell the user *something* went wrong.
Domain exceptions tell the user *what* went wrong, in terms they understand:
a merge failed, a model is mis-specified, validation blocked the pipeline.

Hierarchy
---------
EconFlowError                ← canonical base (alias of AIProdError for backward compat)
├── DataValidationError      ← required columns missing, duplicates, non-finite values
├── MergeError               ← key-lookup failure, key collision during merge
├── PipelineError            ← step ran out of order, intermediate file missing
└── ModelSpecificationError  ← formula invalid, collinear regressors, insufficient obs

Backward compatibility
----------------------
``AIProdError`` was the name used before v0.1.0.  It is now an alias for
``EconFlowError`` (they are the *same class object*) so all existing
``except AIProdError`` clauses continue to work without modification.
The alias will be removed in v0.3.0.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Root — EconFlowError is the canonical public name.
# AIProdError is kept as a module-level alias (same object) so that
# ``except AIProdError`` still catches all subclasses.
# ---------------------------------------------------------------------------


class EconFlowError(Exception):
    """Base exception for all EconFlow framework errors."""


# Backward-compat alias — same object, so isinstance/except work identically.
# Remove in v0.3.0.
AIProdError = EconFlowError


# ---------------------------------------------------------------------------
# Concrete exception types
# ---------------------------------------------------------------------------

class DataValidationError(EconFlowError):
    """Raised when the panel dataset fails schema or quality checks.

    Examples
    --------
    - A required column is missing from the DataFrame.
    - Duplicate (entity, time) rows detected.
    - A log-transformed variable contains ``-inf`` or ``NaN``.
    """


class MergeError(EconFlowError):
    """Raised when a merge between two data sources cannot be completed safely.

    Examples
    --------
    - An entity key is not found in the reference lookup table.
    - A left-join produces unexpected row duplication.
    - Two sources disagree on a shared key column.
    """


class PipelineError(EconFlowError):
    """Raised when a pipeline step is invoked in an invalid state.

    Examples
    --------
    - A downstream step is called before an upstream step has written output.
    - An intermediate file is missing or empty.
    - A step receives an unexpected data schema from the previous step.
    """


class ModelSpecificationError(EconFlowError):
    """Raised when an econometric model cannot be estimated as specified.

    Examples
    --------
    - A regressor is perfectly collinear with the fixed effects.
    - The formula string cannot be parsed.
    - The entity-time panel has fewer observations than parameters.
    """
