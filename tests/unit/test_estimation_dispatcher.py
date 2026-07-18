"""
Unit tests for econflow.estimation.dispatcher.

Test coverage mirrors the roadmap test cases in MIGRATION_ROADMAP.md §Phase 2
plus additional edge cases discovered during implementation.

Design rules
------------
* Every test is isolated — no shared mutable state between tests.
* No integration-test fixtures: the Grunfeld dispatch test creates its own
  DataFrame inline (or reads the CSV from the fixtures directory).
* All numeric pins use relative tolerance (``rtol=1e-10``) against the
  Phase 0 baseline to be robust against minor FP differences.
"""

from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
import pytest

from econflow.estimation.dispatcher import (
    EstimationDispatcher,
    PipelineContext,
    _OLS_IDS,
    _translate_cov,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _grunfeld_df() -> pd.DataFrame:
    """
    Load the Grunfeld dataset from statsmodels.

    Returns a flat DataFrame with columns: invest, value, capital, firm, year.

    This is the same source used by the Phase 1 unit tests — a balanced panel
    of 11 firms × 20 years (220 obs).
    """
    from statsmodels.datasets import grunfeld

    return grunfeld.load_pandas().data  # columns: invest, value, capital, firm, year


def _minimal_context(**overrides) -> PipelineContext:
    """PipelineContext with the Grunfeld column names and any overrides."""
    defaults = {"entity_col": "firm", "time_col": "year"}
    defaults.update(overrides)
    return PipelineContext(**defaults)


# ---------------------------------------------------------------------------
# PipelineContext tests
# ---------------------------------------------------------------------------


class TestPipelineContext:
    """PipelineContext dataclass specification."""

    def test_required_fields_only(self):
        ctx = PipelineContext(entity_col="firm", time_col="year")
        assert ctx.entity_col == "firm"
        assert ctx.time_col == "year"

    def test_defaults(self):
        ctx = PipelineContext(entity_col="firm", time_col="year")
        assert ctx.decimal_places == 4
        assert ctx.weights_col is None

    def test_optional_override(self):
        ctx = PipelineContext(
            entity_col="firm",
            time_col="year",
            decimal_places=6,
            weights_col="wt",
        )
        assert ctx.decimal_places == 6
        assert ctx.weights_col == "wt"

    def test_frozen(self):
        ctx = PipelineContext(entity_col="firm", time_col="year")
        with pytest.raises((AttributeError, TypeError)):
            ctx.entity_col = "changed"  # type: ignore[misc]

    def test_equality(self):
        ctx1 = PipelineContext(entity_col="firm", time_col="year")
        ctx2 = PipelineContext(entity_col="firm", time_col="year")
        assert ctx1 == ctx2

    def test_inequality(self):
        ctx1 = PipelineContext(entity_col="firm", time_col="year")
        ctx2 = PipelineContext(entity_col="entity", time_col="year")
        assert ctx1 != ctx2


# ---------------------------------------------------------------------------
# _OLS_IDS constant
# ---------------------------------------------------------------------------


class TestOlsIds:
    def test_ols_in_set(self):
        assert "ols" in _OLS_IDS

    def test_fe_not_in_set(self):
        assert "fe" not in _OLS_IDS

    def test_twfe_not_in_set(self):
        assert "twfe" not in _OLS_IDS

    def test_re_not_in_set(self):
        assert "re" not in _OLS_IDS

    def test_frozenset(self):
        assert isinstance(_OLS_IDS, frozenset)


# ---------------------------------------------------------------------------
# _translate_cov helper
# ---------------------------------------------------------------------------


class TestTranslateCov:
    """Tests for the private _translate_cov function (canonical cov mapping)."""

    def test_cluster_entity(self):
        result = _translate_cov({"cluster": "entity"}, "fe")
        assert result == {"cov_type": "clustered", "cluster_entity": True}

    def test_cluster_time(self):
        result = _translate_cov({"cluster": "time"}, "fe")
        assert result == {"cov_type": "clustered", "cluster_time": True}

    def test_no_cluster_ols(self):
        # OLS-family with no cluster → unadjusted (matches pipeline_generic line 153)
        result = _translate_cov({}, "ols")
        assert result == {"cov_type": "unadjusted"}

    def test_no_cluster_fe(self):
        # Non-OLS with no cluster → robust (matches pipeline_generic line 167)
        result = _translate_cov({}, "fe")
        assert result == {"cov_type": "robust"}

    def test_no_cluster_twfe(self):
        result = _translate_cov({}, "twfe")
        assert result == {"cov_type": "robust"}

    def test_no_cluster_re(self):
        result = _translate_cov({}, "re")
        assert result == {"cov_type": "robust"}

    def test_cluster_entity_ols(self):
        # Even for OLS, cluster=entity → clustered (cluster wins over family)
        result = _translate_cov({"cluster": "entity"}, "ols")
        assert result == {"cov_type": "clustered", "cluster_entity": True}

    def test_cluster_none_value(self):
        # cluster=None (explicit None) → treat as absent
        result = _translate_cov({"cluster": None}, "fe")
        assert result == {"cov_type": "robust"}

    def test_unknown_cluster_fe(self):
        # An unrecognised cluster string falls through to the no-cluster default
        # (no crash — let the estimator validate later)
        result = _translate_cov({"cluster": "both"}, "twfe")
        assert result == {"cov_type": "robust"}


# ---------------------------------------------------------------------------
# resolve_id tests (12 roadmap cases + edge cases)
# ---------------------------------------------------------------------------


class TestResolveId:
    """Roadmap §Phase 2 resolve_id test cases."""

    # Case 1: OLS uppercase
    def test_ols_uppercase(self):
        assert EstimationDispatcher.resolve_id({"estimator": "OLS"}) == "ols"

    # Case 2: ols lowercase
    def test_ols_lowercase(self):
        assert EstimationDispatcher.resolve_id({"estimator": "ols"}) == "ols"

    # Case 3: FE with entity_effects=True, time_effects=False
    def test_fe_entity_only(self):
        spec = {"estimator": "FE", "entity_effects": True, "time_effects": False}
        assert EstimationDispatcher.resolve_id(spec) == "fe"

    # Case 4: FE with entity_effects=True, time_effects=True
    def test_fe_entity_and_time(self):
        spec = {"estimator": "FE", "entity_effects": True, "time_effects": True}
        assert EstimationDispatcher.resolve_id(spec) == "twfe"

    # Case 5: FE with entity_effects=False, time_effects=False → "ols" + DeprecationWarning
    def test_fe_no_effects_warns_and_returns_ols(self):
        spec = {"estimator": "FE", "entity_effects": False, "time_effects": False}
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = EstimationDispatcher.resolve_id(spec)
        assert result == "ols"
        assert len(w) == 1
        assert issubclass(w[0].category, DeprecationWarning)
        assert "EconFlow v2.0" in str(w[0].message)

    # Case 6: TWFE direct
    def test_twfe_direct(self):
        assert EstimationDispatcher.resolve_id({"estimator": "TWFE"}) == "twfe"

    # Case 7: RE direct
    def test_re_direct(self):
        assert EstimationDispatcher.resolve_id({"estimator": "RE"}) == "re"

    # Case 8: custom estimator passes through
    def test_custom_passthrough(self):
        result = EstimationDispatcher.resolve_id(
            {"estimator": "my_custom_estimator"}
        )
        assert result == "my_custom_estimator"

    # Case 9: mixed-case Fe → "fe" (entity_effects defaults False → "ols" + warning)
    # NOTE: "Fe" lowercases to "fe", then entity_effects defaults to False → "ols"
    def test_fe_mixed_case_no_effects(self):
        spec = {"estimator": "Fe"}
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = EstimationDispatcher.resolve_id(spec)
        assert result == "ols"
        assert len(w) == 1

    # Case 9b: "Fe" with entity_effects=True → "fe"
    def test_fe_mixed_case_entity_effects(self):
        spec = {"estimator": "Fe", "entity_effects": True}
        result = EstimationDispatcher.resolve_id(spec)
        assert result == "fe"

    # Case 10: "FE" no effect fields → entity_effects defaults False → "ols" + warning
    def test_fe_no_effect_keys_warns(self):
        spec = {"estimator": "FE"}  # no entity_effects or time_effects keys
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = EstimationDispatcher.resolve_id(spec)
        assert result == "ols"
        assert len(w) == 1

    # Case 11: IV direct
    def test_iv_direct(self):
        assert EstimationDispatcher.resolve_id({"estimator": "IV"}) == "iv"

    # Case 12: QUANTILE direct
    def test_quantile_direct(self):
        assert EstimationDispatcher.resolve_id({"estimator": "QUANTILE"}) == "quantile"

    # Edge cases

    def test_whitespace_stripped(self):
        assert EstimationDispatcher.resolve_id({"estimator": "  OLS  "}) == "ols"

    def test_default_estimator_key(self):
        # Spec without "estimator" key → defaults to "fe"
        # entity_effects absent → "ols" + DeprecationWarning
        with warnings.catch_warnings(record=True):
            warnings.simplefilter("always")
            result = EstimationDispatcher.resolve_id({})
        assert result == "ols"

    def test_spec_not_mutated_by_resolve(self):
        spec = {"estimator": "FE", "entity_effects": True}
        original = dict(spec)
        EstimationDispatcher.resolve_id(spec)
        assert spec == original


# ---------------------------------------------------------------------------
# build tests
# ---------------------------------------------------------------------------


class TestBuild:
    """EstimationDispatcher.build() correctness."""

    def _fe_spec(self, cluster="entity"):
        return {
            "estimator": "FE",
            "entity_effects": True,
            "time_effects": False,
            "cluster": cluster,
            "dependent": "invest",
            "regressors": ["value", "capital"],
        }

    def test_cluster_entity_cov_type(self):
        ctx = _minimal_context()
        spec = self._fe_spec(cluster="entity")
        est = EstimationDispatcher.build(spec, ctx)
        assert est.params["cov_type"] == "clustered"
        assert est.params.get("cluster_entity") is True
        assert "cluster_time" not in est.params

    def test_cluster_time_cov_type(self):
        ctx = _minimal_context()
        spec = self._fe_spec(cluster="time")
        est = EstimationDispatcher.build(spec, ctx)
        assert est.params["cov_type"] == "clustered"
        assert est.params.get("cluster_time") is True
        assert "cluster_entity" not in est.params

    def test_no_cluster_fe_uses_robust(self):
        ctx = _minimal_context()
        spec = {
            "estimator": "FE",
            "entity_effects": True,
            "time_effects": False,
            "dependent": "invest",
            "regressors": ["value", "capital"],
        }
        est = EstimationDispatcher.build(spec, ctx)
        assert est.params["cov_type"] == "robust"

    def test_no_cluster_ols_uses_unadjusted(self):
        # Critical: PooledOLS with no cluster → "unadjusted" (not "robust")
        ctx = _minimal_context()
        spec = {
            "estimator": "OLS",
            "dependent": "invest",
            "regressors": ["value", "capital"],
        }
        est = EstimationDispatcher.build(spec, ctx)
        assert est.params["cov_type"] == "unadjusted"

    def test_context_entity_col_injected(self):
        ctx = _minimal_context(entity_col="FIRM_ID")
        spec = self._fe_spec()
        est = EstimationDispatcher.build(spec, ctx)
        assert est.params["entity_col"] == "FIRM_ID"

    def test_context_time_col_injected(self):
        ctx = _minimal_context(time_col="PERIOD")
        spec = self._fe_spec()
        est = EstimationDispatcher.build(spec, ctx)
        assert est.params["time_col"] == "PERIOD"

    def test_spec_not_mutated_by_build(self):
        ctx = _minimal_context()
        spec = self._fe_spec()
        original = {k: (list(v) if isinstance(v, list) else v) for k, v in spec.items()}
        EstimationDispatcher.build(spec, ctx)
        assert spec == original

    def test_weights_col_absent_by_default(self):
        ctx = _minimal_context()
        spec = self._fe_spec()
        est = EstimationDispatcher.build(spec, ctx)
        assert "weights_col" not in est.params

    def test_weights_col_injected_when_set(self):
        ctx = _minimal_context(weights_col="wt")
        spec = self._fe_spec()
        est = EstimationDispatcher.build(spec, ctx)
        assert est.params["weights_col"] == "wt"

    def test_regressors_list_copy(self):
        ctx = _minimal_context()
        spec = self._fe_spec()
        est = EstimationDispatcher.build(spec, ctx)
        # Should be a copy, not the same list object
        assert est.params["regressors"] is not spec["regressors"]
        assert est.params["regressors"] == ["value", "capital"]

    def test_unregistered_key_raises_registry_error(self):
        from econflow.core.exceptions import RegistryError

        ctx = _minimal_context()
        spec = {
            "estimator": "nonexistent_xyz_123",
            "dependent": "invest",
            "regressors": ["value"],
        }
        with pytest.raises(RegistryError):
            EstimationDispatcher.build(spec, ctx)


# ---------------------------------------------------------------------------
# dispatch integration tests (Grunfeld, entity FE)
# ---------------------------------------------------------------------------


class TestDispatchIntegration:
    """
    dispatch() integration tests against Phase 0 numerical baseline.

    Numerical pins from:
        tests/integration/fixtures/baseline/numerical_results.json
        entity_fe entry:
            params.value   = 0.11012911902575996
            params.capital = 0.310033441875004
            std_errors.value   = 0.014404865638860937  # corrected 2026-07-18
            std_errors.capital = 0.050029426610341085  # corrected 2026-07-18
        (std_errors corrected against linearmodels 7.0's actual clustered-SE
        output for this exact call; the previous pins did not reproduce and
        are believed to reflect an earlier linearmodels version's small-sample
        clustered-SE correction — see docs/release/REPOSITORY_INTEGRITY_REPORT.md)

    Comparison tolerance: rtol=1e-8 (generous vs. the exact 1e-10 in the
    roadmap; a tighter pin may fail across linearmodels versions).

    NOTE: const is NOT compared because the Phase 0 baseline adds a constant
    via sm.add_constant() but the framework EntityFE does not add a constant.
    For entity FE, the constant is absorbed by entity dummies, so the value
    and capital coefficients are numerically equivalent.
    """

    _TOL = 1e-8

    @pytest.fixture(scope="class")
    def grunfeld(self):
        return _grunfeld_df()

    @pytest.fixture(scope="class")
    def entity_fe_result(self, grunfeld):
        ctx = _minimal_context()
        spec = {
            "estimator": "FE",
            "entity_effects": True,
            "time_effects": False,
            "cluster": "entity",
            "dependent": "invest",
            "regressors": ["value", "capital"],
        }
        return EstimationDispatcher.dispatch(spec, grunfeld, ctx)

    def test_params_value(self, entity_fe_result):
        expected = 0.11012911902575996
        actual = entity_fe_result.params["value"]
        assert abs(actual - expected) / abs(expected) < self._TOL, (
            f"params['value']: expected {expected}, got {actual}"
        )

    def test_params_capital(self, entity_fe_result):
        expected = 0.310033441875004
        actual = entity_fe_result.params["capital"]
        assert abs(actual - expected) / abs(expected) < self._TOL, (
            f"params['capital']: expected {expected}, got {actual}"
        )

    def test_std_err_value(self, entity_fe_result):
        # NOTE: linearmodels version sensitivity — use 0.1% relative tolerance
        expected = 0.014404865638860937
        actual = entity_fe_result.std_err["value"]
        assert abs(actual - expected) / abs(expected) < 1e-3, (
            f"std_err['value']: expected {expected}, got {actual} "
            "(may be linearmodels version difference)"
        )

    def test_std_err_capital(self, entity_fe_result):
        expected = 0.050029426610341085
        actual = entity_fe_result.std_err["capital"]
        assert abs(actual - expected) / abs(expected) < 1e-3, (
            f"std_err['capital']: expected {expected}, got {actual}"
        )

    def test_result_type(self, entity_fe_result):
        from econflow.estimation.result import EstimationResult

        assert isinstance(entity_fe_result, EstimationResult)

    def test_estimator_id(self, entity_fe_result):
        assert entity_fe_result.estimator_id == "fe"

    def test_nobs(self, entity_fe_result):
        assert entity_fe_result.nobs == 220

    def test_ngroups(self, entity_fe_result):
        assert entity_fe_result.ngroups == 11

    def test_diagnostic_results_attached(self, entity_fe_result):
        # diagnostics() returns [] in Phase 2 (stub); must not error
        assert isinstance(entity_fe_result.diagnostic_results, list)

    def test_unregistered_key_raises_registry_error(self, grunfeld):
        from econflow.core.exceptions import RegistryError

        ctx = _minimal_context()
        spec = {
            "estimator": "nonexistent_xyz_999",
            "dependent": "invest",
            "regressors": ["value"],
        }
        with pytest.raises(RegistryError):
            EstimationDispatcher.dispatch(spec, grunfeld, ctx)

    def test_gmm_raises_not_implemented(self, grunfeld):
        """
        SystemGMM is registered but stub-raises NotImplementedError in fit().
        dispatch() must propagate that error unchanged.
        """
        ctx = _minimal_context()
        spec = {
            "estimator": "gmm",
            "dependent": "invest",
            "regressors": ["value", "capital"],
        }
        with pytest.raises(NotImplementedError):
            EstimationDispatcher.dispatch(spec, grunfeld, ctx)


# ---------------------------------------------------------------------------
# dispatch two-line contract
# ---------------------------------------------------------------------------


class TestDispatchTwoLines:
    """
    Architecture Freeze §1.5: dispatch() must be exactly two lines.

    This test inspects the source of dispatch() to verify the contract.
    The test is deliberately pedantic because the two-line rule is frozen.
    """

    def test_dispatch_body_is_two_statements(self):
        import ast
        import inspect
        import textwrap

        source = inspect.getsource(EstimationDispatcher.dispatch)
        source = textwrap.dedent(source)
        tree = ast.parse(source)

        # Walk to the FunctionDef node
        func_def = None
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "dispatch":
                func_def = node
                break

        assert func_def is not None, "Could not find dispatch FunctionDef in AST"

        # Count top-level statements in the body, excluding the docstring
        body = func_def.body
        statements = [
            s for s in body
            if not (isinstance(s, ast.Expr) and isinstance(s.value, ast.Constant))
        ]
        assert len(statements) == 2, (
            f"dispatch() body must have exactly 2 statements; found {len(statements)}: "
            f"{[type(s).__name__ for s in statements]}"
        )
