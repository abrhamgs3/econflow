"""
Tests for the EconFlow exception hierarchy.

These tests verify:
1. ``EconFlowError`` is the canonical base class — it catches all domain exceptions.
2. ``AIProdError`` is a backward-compat alias (same object) — it also catches all.
3. Exception messages are preserved.
4. Exception types do not cross-catch siblings.
"""

import pytest

from econflow.exceptions import (
    AIProdError,  # backward-compat alias (same object as EconFlowError)
    DataValidationError,
    EconFlowError,
    MergeError,
    ModelSpecificationError,
    PipelineError,
)


class TestEconFlowErrorHierarchy:
    """All domain exceptions must be subclasses of EconFlowError (canonical base)."""

    def test_data_validation_error_is_econflow_error(self):
        with pytest.raises(EconFlowError):
            raise DataValidationError("required column missing")

    def test_merge_error_is_econflow_error(self):
        with pytest.raises(EconFlowError):
            raise MergeError("entity key not found")

    def test_pipeline_error_is_econflow_error(self):
        with pytest.raises(EconFlowError):
            raise PipelineError("intermediate file missing")

    def test_model_specification_error_is_econflow_error(self):
        with pytest.raises(EconFlowError):
            raise ModelSpecificationError("collinear regressors")


class TestAIProdErrorAlias:
    """AIProdError must be the same object as EconFlowError (alias, not subclass)."""

    def test_aiprod_error_is_same_class_as_econflow_error(self):
        """AIProdError IS EconFlowError — they are the same class object."""
        assert AIProdError is EconFlowError

    def test_data_validation_error_caught_by_aiprod_alias(self):
        """Backward-compat: existing code with 'except AIProdError' still works."""
        with pytest.raises(AIProdError):
            raise DataValidationError("column missing")

    def test_merge_error_caught_by_aiprod_alias(self):
        with pytest.raises(AIProdError):
            raise MergeError("key not found")

    def test_pipeline_error_caught_by_aiprod_alias(self):
        with pytest.raises(AIProdError):
            raise PipelineError("missing file")

    def test_model_specification_error_caught_by_aiprod_alias(self):
        with pytest.raises(AIProdError):
            raise ModelSpecificationError("bad formula")

    def test_aiprod_error_is_subclass_of_exception(self):
        assert issubclass(AIProdError, Exception)


class TestExceptionMessages:
    """Exception messages should be preserved and readable."""

    def test_data_validation_error_message(self):
        msg = "duplicate (entity, time) rows: 3 detected"
        assert str(DataValidationError(msg)) == msg

    def test_merge_error_message(self):
        msg = "left join produced 42 unexpected duplicate rows"
        assert str(MergeError(msg)) == msg

    def test_pipeline_error_message(self):
        msg = "step 3 requires step 2 output"
        assert str(PipelineError(msg)) == msg

    def test_model_specification_error_message(self):
        msg = "formula contains duplicate term"
        assert str(ModelSpecificationError(msg)) == msg


class TestExceptionSpecificity:
    """Each exception should only catch its own type, not siblings."""

    def test_merge_error_not_caught_as_data_validation(self):
        with pytest.raises(MergeError):
            try:
                raise MergeError("wrong key")
            except DataValidationError:
                pass  # must NOT execute

    def test_pipeline_error_not_caught_as_model_specification(self):
        with pytest.raises(PipelineError):
            try:
                raise PipelineError("missing file")
            except ModelSpecificationError:
                pass  # must NOT execute
