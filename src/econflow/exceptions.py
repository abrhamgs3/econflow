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
├── EstimatorError           ← estimator cannot complete its work (R1: moved here)
│   └── ModelSpecificationError  ← formula invalid, collinear regressors, absorbed vars
└── [other domain errors]

Backward compatibility
----------------------
``AIProdError`` was the name used before v0.1.0.  It is now an alias for
``EconFlowError`` (they are the *same class object*) so all existing
``except AIProdError`` clauses continue to work without modification.
The alias will be removed in v0.3.0.

``EstimatorError`` was previously defined in ``econflow.estimation.base``.
It is re-exported from that module unchanged so all existing imports continue
to work.  The class now inherits from ``EconFlowError`` so that a top-level
``except EconFlowError`` catches estimation failures alongside pipeline and
data errors (Release Sprint R1, C-1 fix).
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
# Estimator exceptions (R1: moved from econflow.estimation.base so that
# EstimatorError sits under the root EconFlowError hierarchy)
# ---------------------------------------------------------------------------

class EstimatorError(EconFlowError):
    """Raised when an estimator cannot complete its work.

    All EconFlow estimator exceptions inherit from this class.  Because
    ``EstimatorError`` is itself a subclass of :class:`EconFlowError`, a
    single ``except EconFlowError`` clause at the application level catches
    both pipeline-layer and estimation-layer errors.

    Parameters
    ----------
    message:
        Human-readable description of the failure.
    estimator_id:
        Registry ID of the failing estimator (e.g. ``"fe"``, ``"iv"``).
    cause:
        Original exception, if any.

    Notes
    -----
    Previously defined in ``econflow.estimation.base``; moved here in
    Release Sprint R1 to complete the ``EconFlowError`` root hierarchy.
    ``econflow.estimation.base`` re-exports this class unchanged for full
    backward compatibility.
    """

    def __init__(
        self,
        message: str,
        *,
        estimator_id: str = "",
        cause: Exception | None = None,
    ) -> None:
        super().__init__(message)
        self.estimator_id = estimator_id
        self.cause = cause

    def __str__(self) -> str:
        base = super().__str__()
        if self.estimator_id:
            base = f"[{self.estimator_id}] {base}"
        if self.cause:
            base = f"{base}\nCaused by: {self.cause!r}"
        return base


class ModelSpecificationError(EstimatorError):
    """Raised when an econometric model cannot be estimated as specified.

    Subclass of :class:`EstimatorError` for errors that arise from the
    *configuration* of the model rather than from runtime fitting or data
    loading.  Because :class:`EstimatorError` is itself a subclass of
    :class:`EconFlowError`, all three ``except`` forms work correctly::

        except ModelSpecificationError: ...  # most specific
        except EstimatorError:          ...  # catches all estimator errors
        except EconFlowError:           ...  # catches all library errors

    Parameters
    ----------
    message:
        Human-readable description of the misspecification.
    estimator_id:
        Registry ID of the estimator that raised the error.
    cause:
        Original exception, if any.

    Examples
    --------
    - A regressor is perfectly collinear with the entity fixed effects.
    - The formula string cannot be parsed by the backend.
    - The panel has fewer observations than parameters after demeaning.
    - A time-invariant regressor is included in a fixed-effects model.

    Notes
    -----
    Previously a separate class definition existed in
    ``econflow.estimation.base`` (inheriting from ``EstimatorError``) and in
    ``econflow.exceptions`` (inheriting from ``EconFlowError``).  Both are now
    unified into this single canonical class (Release Sprint R1, C-1 fix).
    ``econflow.estimation.base`` re-exports this class for full backward
    compatibility.
    """


# ---------------------------------------------------------------------------
# Other concrete exception types
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
