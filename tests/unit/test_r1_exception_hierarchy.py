"""
Release Sprint R1 — Exception Hierarchy Regression Tests
=========================================================

These tests lock down the unified exception hierarchy introduced in R1 (C-1 fix).
They verify that:

1.  There is exactly ONE ``ModelSpecificationError`` class across all import paths.
2.  The full MRO chain is intact:
        ModelSpecificationError → EstimatorError → EconFlowError → Exception
3.  ``except EconFlowError`` catches both estimator-layer and pipeline-layer raises.
4.  ``except EstimatorError`` catches all estimation failures but NOT pipeline errors.
5.  ``except ModelSpecificationError`` catches raises from every production site
    (fixed_effects.py, pipeline_generic.py, econometrics/panel.py).
6.  Keyword arguments (``estimator_id``, ``cause``) work on the canonical class.
7.  ``__str__`` formatting is correct when ``estimator_id`` is set/unset.
8.  Backward-compatible import paths all resolve to the same class object.
"""

from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _canonical_mse():
    """Import ModelSpecificationError from the canonical location."""
    from econflow.exceptions import ModelSpecificationError
    return ModelSpecificationError


def _canonical_estimator_error():
    """Import EstimatorError from the canonical location."""
    from econflow.exceptions import EstimatorError
    return EstimatorError


def _compat_mse_from_base():
    """Import ModelSpecificationError via the backward-compat re-export."""
    from econflow.estimation.base import ModelSpecificationError
    return ModelSpecificationError


def _compat_estimator_error_from_base():
    """Import EstimatorError via the backward-compat re-export."""
    from econflow.estimation.base import EstimatorError
    return EstimatorError


def _compat_mse_from_estimation():
    """Import ModelSpecificationError from econflow.estimation package."""
    # econflow.estimation.__init__ re-exports via base.py chain
    from econflow.estimation import ModelSpecificationError
    return ModelSpecificationError


def _compat_estimator_error_from_estimation():
    from econflow.estimation import EstimatorError
    return EstimatorError


# ---------------------------------------------------------------------------
# 1. Identity — single class object regardless of import path
# ---------------------------------------------------------------------------

class TestSingleClassIdentity:
    """All import paths must resolve to the same class object (R1: no duplicate)."""

    def test_mse_canonical_same_as_base_reexport(self):
        """econflow.exceptions.MSE is econflow.estimation.base.MSE."""
        assert _canonical_mse() is _compat_mse_from_base()

    def test_mse_canonical_same_as_estimation_reexport(self):
        """econflow.exceptions.MSE is econflow.estimation.MSE."""
        assert _canonical_mse() is _compat_mse_from_estimation()

    def test_estimator_error_canonical_same_as_base_reexport(self):
        """econflow.exceptions.EstimatorError is econflow.estimation.base.EstimatorError."""
        assert _canonical_estimator_error() is _compat_estimator_error_from_base()

    def test_estimator_error_canonical_same_as_estimation_reexport(self):
        assert _canonical_estimator_error() is _compat_estimator_error_from_estimation()

    def test_no_separate_mse_in_estimation_base_module(self):
        """estimation.base must NOT define its own ModelSpecificationError class."""
        import econflow.estimation.base as base_module
        import inspect
        # The MSE in base must NOT be defined in the base module's own source file
        mse = base_module.ModelSpecificationError
        # It must be defined in econflow/exceptions.py
        source_file = inspect.getfile(mse)
        assert "exceptions.py" in source_file, (
            f"ModelSpecificationError must be defined in exceptions.py, "
            f"but found in {source_file}"
        )

    def test_no_separate_estimator_error_in_estimation_base_module(self):
        """estimation.base must NOT define its own EstimatorError class."""
        import econflow.estimation.base as base_module
        import inspect
        ee = base_module.EstimatorError
        source_file = inspect.getfile(ee)
        assert "exceptions.py" in source_file, (
            f"EstimatorError must be defined in exceptions.py, "
            f"but found in {source_file}"
        )


# ---------------------------------------------------------------------------
# 2. MRO chain
# ---------------------------------------------------------------------------

class TestMROChain:
    """ModelSpecificationError → EstimatorError → EconFlowError → Exception."""

    def test_mse_is_subclass_of_estimator_error(self):
        from econflow.exceptions import EstimatorError, ModelSpecificationError
        assert issubclass(ModelSpecificationError, EstimatorError)

    def test_mse_is_subclass_of_econflow_error(self):
        from econflow.exceptions import EconFlowError, ModelSpecificationError
        assert issubclass(ModelSpecificationError, EconFlowError)

    def test_mse_is_subclass_of_exception(self):
        from econflow.exceptions import ModelSpecificationError
        assert issubclass(ModelSpecificationError, Exception)

    def test_estimator_error_is_subclass_of_econflow_error(self):
        """EstimatorError now sits under EconFlowError (R1 hierarchy fix)."""
        from econflow.exceptions import EconFlowError, EstimatorError
        assert issubclass(EstimatorError, EconFlowError)

    def test_estimator_error_is_subclass_of_exception(self):
        from econflow.exceptions import EstimatorError
        assert issubclass(EstimatorError, Exception)

    def test_mse_not_subclass_of_data_validation_error(self):
        from econflow.exceptions import DataValidationError, ModelSpecificationError
        assert not issubclass(ModelSpecificationError, DataValidationError)

    def test_mse_not_subclass_of_pipeline_error(self):
        from econflow.exceptions import ModelSpecificationError, PipelineError
        assert not issubclass(ModelSpecificationError, PipelineError)

    def test_mse_not_subclass_of_merge_error(self):
        from econflow.exceptions import MergeError, ModelSpecificationError
        assert not issubclass(ModelSpecificationError, MergeError)

    def test_mse_via_compat_path_same_mro(self):
        """MRO is identical regardless of import path."""
        from econflow.exceptions import ModelSpecificationError as E1
        from econflow.estimation.base import ModelSpecificationError as E2
        assert E1.__mro__ == E2.__mro__


# ---------------------------------------------------------------------------
# 3. except EconFlowError catches both estimator and pipeline raises
# ---------------------------------------------------------------------------

class TestEconFlowErrorCatchesAll:
    """Top-level except EconFlowError must catch every library exception."""

    def test_catches_model_specification_error(self):
        from econflow.exceptions import EconFlowError, ModelSpecificationError
        with pytest.raises(EconFlowError):
            raise ModelSpecificationError("collinear regressors")

    def test_catches_estimator_error(self):
        from econflow.exceptions import EconFlowError, EstimatorError
        with pytest.raises(EconFlowError):
            raise EstimatorError("fit failed", estimator_id="fe")

    def test_catches_model_specification_error_from_base_import(self):
        """Same check with exception raised via compat import path."""
        from econflow.estimation.base import ModelSpecificationError
        from econflow.exceptions import EconFlowError
        with pytest.raises(EconFlowError):
            raise ModelSpecificationError("time-invariant regressor", estimator_id="fe")

    def test_catches_pipeline_error(self):
        from econflow.exceptions import EconFlowError, PipelineError
        with pytest.raises(EconFlowError):
            raise PipelineError("intermediate file missing")

    def test_catches_data_validation_error(self):
        from econflow.exceptions import DataValidationError, EconFlowError
        with pytest.raises(EconFlowError):
            raise DataValidationError("required column missing")

    def test_catches_merge_error(self):
        from econflow.exceptions import EconFlowError, MergeError
        with pytest.raises(EconFlowError):
            raise MergeError("entity key not found")


# ---------------------------------------------------------------------------
# 4. except EstimatorError catches estimation errors but not pipeline errors
# ---------------------------------------------------------------------------

class TestEstimatorErrorScope:
    """EstimatorError catches estimation failures but not pipeline/data errors."""

    def test_catches_model_specification_error(self):
        from econflow.exceptions import EstimatorError, ModelSpecificationError
        with pytest.raises(EstimatorError):
            raise ModelSpecificationError("bad spec", estimator_id="twfe")

    def test_catches_base_estimator_error(self):
        from econflow.exceptions import EstimatorError
        with pytest.raises(EstimatorError):
            raise EstimatorError("fit failed")

    def test_does_not_catch_pipeline_error(self):
        """PipelineError is NOT a subclass of EstimatorError."""
        from econflow.exceptions import EstimatorError, PipelineError
        with pytest.raises(PipelineError):
            try:
                raise PipelineError("step failed")
            except EstimatorError:
                pytest.fail("EstimatorError must not catch PipelineError")

    def test_does_not_catch_data_validation_error(self):
        from econflow.exceptions import DataValidationError, EstimatorError
        with pytest.raises(DataValidationError):
            try:
                raise DataValidationError("missing column")
            except EstimatorError:
                pytest.fail("EstimatorError must not catch DataValidationError")

    def test_does_not_catch_merge_error(self):
        from econflow.exceptions import EstimatorError, MergeError
        with pytest.raises(MergeError):
            try:
                raise MergeError("key collision")
            except EstimatorError:
                pytest.fail("EstimatorError must not catch MergeError")


# ---------------------------------------------------------------------------
# 5. except ModelSpecificationError catches from all production raise sites
# ---------------------------------------------------------------------------

class TestModelSpecificationErrorCrossPathCatch:
    """
    A single except ModelSpecificationError must catch exceptions raised using
    any import path — whether from econflow.exceptions or econflow.estimation.base.
    This is the core C-1 regression guard.
    """

    def test_catches_when_raised_via_exceptions_import(self):
        """Production path: pipeline_generic.py raises from econflow.exceptions."""
        from econflow.exceptions import ModelSpecificationError
        # Simulate the pipeline_generic.py raise pattern (no estimator_id)
        def simulate_pipeline_raise():
            from econflow.exceptions import ModelSpecificationError as MSE
            raise MSE("estimator 'gmm' is a stub")

        with pytest.raises(ModelSpecificationError):
            simulate_pipeline_raise()

    def test_catches_when_raised_via_base_import(self):
        """Production path: fixed_effects.py raises from econflow.estimation.base."""
        from econflow.exceptions import ModelSpecificationError
        # Simulate the fixed_effects.py raise pattern (with estimator_id)
        def simulate_fe_raise():
            from econflow.estimation.base import ModelSpecificationError as MSE
            raise MSE(
                "Regressors ['const'] have zero within-entity variance",
                estimator_id="fe",
            )

        with pytest.raises(ModelSpecificationError):
            simulate_fe_raise()

    def test_exceptions_and_base_raise_same_exception_type(self):
        """Raise via exceptions.py; catch via econflow.estimation.base import."""
        from econflow.estimation.base import ModelSpecificationError as MSE_base

        def simulate_exceptions_raise():
            from econflow.exceptions import ModelSpecificationError as MSE_exc
            raise MSE_exc("pipeline misspecification")

        with pytest.raises(MSE_base):
            simulate_exceptions_raise()

    def test_base_and_exceptions_raise_same_exception_type_reversed(self):
        """Raise via estimation.base; catch via econflow.exceptions import."""
        from econflow.exceptions import ModelSpecificationError as MSE_exc

        def simulate_base_raise():
            from econflow.estimation.base import ModelSpecificationError as MSE_base
            raise MSE_base("time-invariant regressor", estimator_id="twfe")

        with pytest.raises(MSE_exc):
            simulate_base_raise()


# ---------------------------------------------------------------------------
# 6. Keyword arguments
# ---------------------------------------------------------------------------

class TestKeywordArguments:
    """EstimatorError-inherited keyword args work on ModelSpecificationError."""

    def test_estimator_id_stored(self):
        from econflow.exceptions import ModelSpecificationError
        exc = ModelSpecificationError("bad spec", estimator_id="fe")
        assert exc.estimator_id == "fe"

    def test_cause_stored(self):
        from econflow.exceptions import ModelSpecificationError
        original = ValueError("underlying cause")
        exc = ModelSpecificationError("wrapping error", cause=original)
        assert exc.cause is original

    def test_no_kwargs_works(self):
        """Plain message-only construction still works."""
        from econflow.exceptions import ModelSpecificationError
        exc = ModelSpecificationError("plain message")
        assert exc.estimator_id == ""
        assert exc.cause is None

    def test_estimator_error_kwargs(self):
        from econflow.exceptions import EstimatorError
        exc = EstimatorError("fit failed", estimator_id="gmm", cause=RuntimeError("x"))
        assert exc.estimator_id == "gmm"
        assert isinstance(exc.cause, RuntimeError)


# ---------------------------------------------------------------------------
# 7. __str__ formatting
# ---------------------------------------------------------------------------

class TestStrFormatting:
    """__str__ follows EstimatorError convention."""

    def test_plain_message_no_prefix(self):
        from econflow.exceptions import ModelSpecificationError
        exc = ModelSpecificationError("collinear regressors")
        assert str(exc) == "collinear regressors"

    def test_estimator_id_prefix(self):
        from econflow.exceptions import ModelSpecificationError
        exc = ModelSpecificationError("time-invariant var", estimator_id="fe")
        assert str(exc) == "[fe] time-invariant var"

    def test_cause_appended(self):
        from econflow.exceptions import ModelSpecificationError
        cause = ValueError("original")
        exc = ModelSpecificationError("wrapped", cause=cause)
        s = str(exc)
        assert "Caused by:" in s
        assert "wrapped" in s

    def test_estimator_error_str_plain(self):
        from econflow.exceptions import EstimatorError
        exc = EstimatorError("fit diverged")
        assert str(exc) == "fit diverged"

    def test_estimator_error_str_with_id(self):
        from econflow.exceptions import EstimatorError
        exc = EstimatorError("fit diverged", estimator_id="iv")
        assert str(exc) == "[iv] fit diverged"


# ---------------------------------------------------------------------------
# 8. Backward-compat: isinstance checks across import paths
# ---------------------------------------------------------------------------

class TestIsinstanceConsistency:
    """isinstance() must be consistent across all import paths."""

    def test_mse_from_base_isinstance_of_econflow_error(self):
        from econflow.estimation.base import ModelSpecificationError
        from econflow.exceptions import EconFlowError
        exc = ModelSpecificationError("bad spec")
        assert isinstance(exc, EconFlowError)

    def test_mse_from_base_isinstance_of_estimator_error(self):
        from econflow.estimation.base import EstimatorError, ModelSpecificationError
        exc = ModelSpecificationError("bad spec")
        assert isinstance(exc, EstimatorError)

    def test_mse_from_exceptions_isinstance_of_estimator_error_from_base(self):
        """Cross-path isinstance check — the pre-R1 bug."""
        from econflow.estimation.base import EstimatorError
        from econflow.exceptions import ModelSpecificationError
        exc = ModelSpecificationError("pipeline stub")
        # Pre-R1: this was False because different class objects
        # Post-R1: True because single canonical class
        assert isinstance(exc, EstimatorError)

    def test_mse_from_base_isinstance_of_mse_from_exceptions(self):
        """Cross-path isinstance check — symmetric."""
        from econflow.estimation.base import ModelSpecificationError as MSE_base
        from econflow.exceptions import ModelSpecificationError as MSE_exc
        exc = MSE_base("time-invariant")
        assert isinstance(exc, MSE_exc)


# ---------------------------------------------------------------------------
# 9. Integration — real estimator raises are catchable at all hierarchy levels
# ---------------------------------------------------------------------------

class TestRealEstimatorRaises:
    """
    End-to-end test: EntityFE with time-invariant regressor must raise an
    exception catchable as ModelSpecificationError, EstimatorError, and
    EconFlowError from any import path.
    """

    @pytest.fixture(scope="class")
    def df_with_time_invariant_col(self):
        import pandas as pd
        import numpy as np
        rng = np.random.default_rng(42)
        n_firms = 5
        n_years = 6
        firms = [f"f{i}" for i in range(n_firms)]
        years = list(range(2000, 2000 + n_years))
        rows = []
        for firm in firms:
            for year in years:
                rows.append({
                    "firm": firm,
                    "year": year,
                    "invest": rng.normal(100, 10),
                    "value": rng.normal(500, 50),
                    "const_col": 1.0,  # time-invariant!
                })
        return pd.DataFrame(rows)

    def test_fe_raises_catchable_as_econflow_error(self, df_with_time_invariant_col):
        from econflow.estimation.fixed_effects import EntityFE
        from econflow.exceptions import EconFlowError
        params = {
            "dependent": "invest",
            "regressors": ["value", "const_col"],
            "entity_col": "firm",
            "time_col": "year",
        }
        with pytest.raises(EconFlowError):
            EntityFE(params=params).run(df_with_time_invariant_col)

    def test_fe_raises_catchable_as_estimator_error(self, df_with_time_invariant_col):
        from econflow.estimation.fixed_effects import EntityFE
        from econflow.exceptions import EstimatorError
        params = {
            "dependent": "invest",
            "regressors": ["value", "const_col"],
            "entity_col": "firm",
            "time_col": "year",
        }
        with pytest.raises(EstimatorError):
            EntityFE(params=params).run(df_with_time_invariant_col)

    def test_fe_raises_catchable_as_mse_from_exceptions(self, df_with_time_invariant_col):
        from econflow.estimation.fixed_effects import EntityFE
        from econflow.exceptions import ModelSpecificationError
        params = {
            "dependent": "invest",
            "regressors": ["value", "const_col"],
            "entity_col": "firm",
            "time_col": "year",
        }
        with pytest.raises(ModelSpecificationError):
            EntityFE(params=params).run(df_with_time_invariant_col)

    def test_fe_raises_catchable_as_mse_from_base(self, df_with_time_invariant_col):
        from econflow.estimation.base import ModelSpecificationError
        from econflow.estimation.fixed_effects import EntityFE
        params = {
            "dependent": "invest",
            "regressors": ["value", "const_col"],
            "entity_col": "firm",
            "time_col": "year",
        }
        with pytest.raises(ModelSpecificationError):
            EntityFE(params=params).run(df_with_time_invariant_col)

    def test_fe_raised_exception_has_estimator_id(self, df_with_time_invariant_col):
        """The raised exception carries estimator_id="fe"."""
        from econflow.estimation.fixed_effects import EntityFE
        from econflow.exceptions import ModelSpecificationError
        params = {
            "dependent": "invest",
            "regressors": ["value", "const_col"],
            "entity_col": "firm",
            "time_col": "year",
        }
        with pytest.raises(ModelSpecificationError) as exc_info:
            EntityFE(params=params).run(df_with_time_invariant_col)
        assert exc_info.value.estimator_id == "fe"
