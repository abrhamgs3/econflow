"""
tests/integration/test_validator_registry.py

Phase 4 integration tests: ConfigValidator + live estimator registry.

These tests verify the full validation pipeline (YAML → Pydantic → Linter)
using the live registry as the authority for estimator IDs.  Unlike unit
tests that call ConfigLinter directly, these tests go through ConfigValidator
to ensure the live_estimator_ids threading is correct end-to-end.

Test scenarios
--------------
I-01  Built-in estimators pass the complete 4-stage validation pipeline.
I-02  A plugin estimator registered at test time passes validation through
      the full pipeline.
I-03  An unknown estimator triggers L-04 (surfaced in the validator result).
I-04  A stub estimator triggers L-04b (surfaced as an error in the result).
I-05  cluster: entities triggers L-14 (error) surfaced in the validator result.
I-06  cluster: entity passes validation end-to-end.
I-07  ConfigValidator.validate_strict() raises ConfigValidationError on L-14.
I-08  Registry is single authority — plugin absent from KNOWN_ESTIMATORS passes.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

# ---------------------------------------------------------------------------
# Fixtures — canonical valid config file paths
# ---------------------------------------------------------------------------

VALID = Path(__file__).parent.parent / "fixtures" / "config" / "valid"


@pytest.fixture()
def validator():
    from econflow.config.validator import ConfigValidator
    return ConfigValidator()


@pytest.fixture()
def registered_integration_plugin():
    """Register and yield a plugin estimator; unregister on teardown."""
    from econflow.estimation import registry as _reg

    eid = "_integration_plugin_p4"

    class _IntegrationPlugin:
        backend = "test"

    _reg._REGISTRY[eid] = _IntegrationPlugin
    _reg._REGISTRY_META[eid] = {
        "id":             eid,
        "label":          "Integration Plugin (Phase 4)",
        "status":         "implemented",
        "notes":          "Registered only for integration tests.",
        "supported_data": ["panel"],
        "backend":        "test",
    }

    yield eid

    _reg._REGISTRY.pop(eid, None)
    _reg._REGISTRY_META.pop(eid, None)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_models(path: Path, estimator: str, cluster: str = "") -> None:
    """Write a minimal models.yaml to *path*."""
    cluster_line = f"    cluster: \"{cluster}\"\n" if cluster else ""
    path.write_text(
        "models:\n"
        "  - id: \"m1\"\n"
        "    label: \"Integration Test Model\"\n"
        f"    estimator: \"{estimator}\"\n"
        "    dependent: \"outcome\"\n"
        "    regressors: [\"treatment\"]\n"
        "    entity_effects: true\n"
        "    time_effects: false\n"
        + cluster_line,
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# I-01 — Built-in estimators pass full pipeline
# ---------------------------------------------------------------------------

class TestBuiltinEstimatorsFullPipeline:
    """I-01: built-in estimators must pass stages 1–4 without L-04 or L-04b."""

    @pytest.mark.parametrize("estimator", ["ols", "fe", "twfe", "re", "fd"])
    def test_builtin_no_l04_via_validator(self, validator, tmp_path, estimator):
        models = tmp_path / "models.yaml"
        if estimator == "twfe":
            (tmp_path / "models.yaml").write_text(
                "models:\n"
                "  - id: \"m1\"\n"
                "    label: \"TWFE\"\n"
                "    estimator: \"twfe\"\n"
                "    dependent: \"outcome\"\n"
                "    regressors: [\"treatment\"]\n"
                "    entity_effects: true\n"
                "    time_effects: true\n",
                encoding="utf-8",
            )
        else:
            _write_models(models, estimator)

        result = validator.validate(VALID / "config.yaml", models, VALID / "outputs.yaml")
        l04 = [i for i in result.issues if i.code == "L-04"]
        l04b = [i for i in result.issues if i.code == "L-04b"]
        assert not l04,  f"Unexpected L-04 for built-in '{estimator}'"
        assert not l04b, f"Unexpected L-04b for built-in '{estimator}'"


# ---------------------------------------------------------------------------
# I-02 — Plugin estimator passes full pipeline
# ---------------------------------------------------------------------------

class TestPluginEstimatorFullPipeline:
    """I-02: plugin registered at test time must validate without L-04."""

    def test_plugin_passes_validator(
        self, validator, tmp_path, registered_integration_plugin
    ):
        eid = registered_integration_plugin
        models = tmp_path / "models.yaml"
        _write_models(models, eid)

        result = validator.validate(VALID / "config.yaml", models, VALID / "outputs.yaml")
        l04 = [i for i in result.issues if i.code == "L-04"]
        assert not l04, (
            f"Plugin estimator '{eid}' triggered L-04 through full validator: {l04}"
        )

    def test_plugin_absent_from_known_estimators_passes(
        self, validator, tmp_path, registered_integration_plugin
    ):
        """Registry is single authority: KNOWN_ESTIMATORS not consulted."""
        from econflow.config.models import KNOWN_ESTIMATORS

        eid = registered_integration_plugin
        assert eid not in KNOWN_ESTIMATORS

        models = tmp_path / "models.yaml"
        _write_models(models, eid)

        result = validator.validate(VALID / "config.yaml", models, VALID / "outputs.yaml")
        l04 = [i for i in result.issues if i.code == "L-04"]
        assert not l04


# ---------------------------------------------------------------------------
# I-03 — Unknown estimator triggers L-04 in full pipeline
# ---------------------------------------------------------------------------

class TestUnknownEstimatorFullPipeline:
    """I-03: unknown estimators must surface L-04 in the validator result."""

    def test_unknown_estimator_l04_in_result(self, validator, tmp_path):
        models = tmp_path / "models.yaml"
        _write_models(models, "xgboost_panel_iv")

        result = validator.validate(VALID / "config.yaml", models, VALID / "outputs.yaml")
        l04 = [i for i in result.issues if i.code == "L-04"]
        assert l04, "Expected L-04 for unknown estimator in full pipeline"
        assert l04[0].stage == "semantic"

    def test_unknown_estimator_result_still_ok_warning(self, validator, tmp_path):
        """L-04 is a warning; result.ok may still be True unless other errors exist."""
        models = tmp_path / "models.yaml"
        _write_models(models, "not_a_real_estimator")
        # VALID/outputs.yaml references model ids "pooled_ols"/"entity_fe", but
        # _write_models() always writes id "m1" -- using VALID/outputs.yaml here
        # would introduce an unrelated cross-file X-01 error that has nothing to
        # do with the L-04 check this test exercises (same root cause already
        # documented and fixed for TestValidateStrictRaisesOnL14 below).
        outputs = tmp_path / "outputs.yaml"
        TestValidateStrictRaisesOnL14._write_outputs_for_m1(outputs)

        result = validator.validate(VALID / "config.yaml", models, outputs)
        l04 = [i for i in result.issues if i.code == "L-04"]
        assert l04
        # L-04 is severity="warning" → result.ok is True (no errors)
        errors_excl_l04 = [i for i in result.issues if i.severity == "error" and i.code != "L-04"]
        assert not errors_excl_l04, "Unexpected error-severity issues besides L-04"
        assert result.ok, "L-04 is a warning and must not make result.ok False"
        assert all(i.severity == "warning" or i.severity == "info" for i in l04)


# ---------------------------------------------------------------------------
# I-04 — Stub estimator triggers L-04b
# ---------------------------------------------------------------------------

class TestStubEstimatorFullPipeline:
    """I-04: stub estimators trigger L-04b (error) and fail result.ok."""

    def test_gmm_triggers_l04b_and_fails_result(self, validator, tmp_path):
        models = tmp_path / "models.yaml"
        _write_models(models, "gmm")

        result = validator.validate(VALID / "config.yaml", models, VALID / "outputs.yaml")
        l04b = [i for i in result.issues if i.code == "L-04b"]
        assert l04b, "Expected L-04b for stub estimator 'gmm'"
        assert l04b[0].severity == "error"
        assert not result.ok  # error → validation fails

    def test_stub_no_l04_only_l04b(self, validator, tmp_path):
        """Stub must fire L-04b, NOT L-04."""
        models = tmp_path / "models.yaml"
        _write_models(models, "quantile")

        result = validator.validate(VALID / "config.yaml", models, VALID / "outputs.yaml")
        l04  = [i for i in result.issues if i.code == "L-04"]
        l04b = [i for i in result.issues if i.code == "L-04b"]
        assert not l04,  "Stub must not trigger L-04"
        assert l04b,     "Stub must trigger L-04b"


# ---------------------------------------------------------------------------
# I-05 — L-14: cluster: entities triggers error
# ---------------------------------------------------------------------------

class TestClusterValidationFullPipeline:
    """I-05/I-06: cluster validation in full pipeline."""

    def test_invalid_cluster_entities_triggers_l14(self, validator, tmp_path):
        models = tmp_path / "models.yaml"
        _write_models(models, "ols", cluster="entities")

        result = validator.validate(VALID / "config.yaml", models, VALID / "outputs.yaml")
        l14 = [i for i in result.issues if i.code == "L-14"]
        assert l14, "Expected L-14 for cluster='entities'"
        assert l14[0].stage == "semantic"
        assert l14[0].severity == "error"

    def test_invalid_cluster_entity_id_triggers_l14_with_suggestion(
        self, validator, tmp_path
    ):
        models = tmp_path / "models.yaml"
        _write_models(models, "ols", cluster="entity_id")

        result = validator.validate(VALID / "config.yaml", models, VALID / "outputs.yaml")
        l14 = [i for i in result.issues if i.code == "L-14"]
        assert l14
        # Suggestion "entity" must be in the message
        assert "entity" in l14[0].message

    @pytest.mark.parametrize("valid_cluster", ["entity", "time"])
    def test_valid_cluster_no_l14(self, validator, tmp_path, valid_cluster):
        models = tmp_path / "models.yaml"
        _write_models(models, "ols", cluster=valid_cluster)

        result = validator.validate(VALID / "config.yaml", models, VALID / "outputs.yaml")
        l14 = [i for i in result.issues if i.code == "L-14"]
        assert not l14, f"Unexpected L-14 for valid cluster='{valid_cluster}'"

    def test_no_cluster_field_no_l14(self, validator, tmp_path):
        """No cluster field → no L-14."""
        models = tmp_path / "models.yaml"
        _write_models(models, "ols", cluster="")  # empty → treated as absent

        result = validator.validate(VALID / "config.yaml", models, VALID / "outputs.yaml")
        l14 = [i for i in result.issues if i.code == "L-14"]
        assert not l14


# ---------------------------------------------------------------------------
# I-07 — validate_strict raises on L-14
# ---------------------------------------------------------------------------

class TestValidateStrictRaisesOnL14:
    """I-07: validate_strict must raise ConfigValidationError when L-14 fires."""

    @staticmethod
    def _write_outputs_for_m1(path: Path) -> None:
        """outputs.yaml whose comparison_table.models matches _write_models()'s
        "m1" id. VALID/outputs.yaml references "pooled_ols"/"entity_fe" instead
        (a different fixture's model IDs), which fails cross-file validation
        (L-xx unknown-model-ID) against a models.yaml containing only "m1" --
        a mismatch unrelated to the L-14 cluster check these tests exercise.
        Corrected 2026-07-18 (Repository Integrity Repair)."""
        path.write_text(
            "outputs:\n"
            "  base_dir: \"outputs\"\n"
            "  tables:\n"
            "    dir: \"outputs/tables\"\n"
            "    formats: [\"csv\"]\n"
            "    comparison_table:\n"
            "      filename: \"table_main\"\n"
            "      models: [\"m1\"]\n"
            "      stars: true\n"
            "      se_type: \"robust\"\n"
            "  figures:\n"
            "    dir: \"outputs/figures\"\n"
            "    enabled: false\n",
            encoding="utf-8",
        )

    def test_validate_strict_raises_on_invalid_cluster(self, validator, tmp_path):
        from econflow.core.exceptions import ConfigValidationError

        models = tmp_path / "models.yaml"
        _write_models(models, "ols", cluster="entities")
        outputs = tmp_path / "outputs.yaml"
        self._write_outputs_for_m1(outputs)

        with pytest.raises(ConfigValidationError):
            validator.validate_strict(VALID / "config.yaml", models, outputs)

    def test_validate_strict_succeeds_on_valid_cluster(self, validator, tmp_path):
        """validate_strict must NOT raise when cluster is valid."""
        models = tmp_path / "models.yaml"
        _write_models(models, "ols", cluster="entity")
        outputs = tmp_path / "outputs.yaml"
        self._write_outputs_for_m1(outputs)

        # Should not raise
        result = validator.validate_strict(VALID / "config.yaml", models, outputs)
        assert result is not None  # returns (project_cfg, models_cfg, outputs_cfg)


# ---------------------------------------------------------------------------
# I-08 — Registry is single authority
# ---------------------------------------------------------------------------

class TestRegistrySingleAuthority:
    """I-08: the live registry, not KNOWN_ESTIMATORS, is the sole authority."""

    def test_runtime_registry_governs_validation_not_known_estimators(
        self, tmp_path, registered_integration_plugin
    ):
        """Modify only the registry; validation outcome must follow it."""
        from econflow.config.validator import ConfigValidator
        from econflow.config.models import KNOWN_ESTIMATORS
        from econflow.estimation import registry as _reg

        eid = registered_integration_plugin
        assert eid not in KNOWN_ESTIMATORS  # not in deprecated static set

        models = tmp_path / "models.yaml"
        _write_models(models, eid)

        # Default validator uses live registry → should accept plugin
        result_registered = ConfigValidator().validate(
            VALID / "config.yaml", models, VALID / "outputs.yaml"
        )

        # Remove plugin from registry
        saved_cls  = _reg._REGISTRY.pop(eid)
        saved_meta = _reg._REGISTRY_META.pop(eid)

        try:
            # Without the registration → should reject
            result_unregistered = ConfigValidator().validate(
                VALID / "config.yaml", models, VALID / "outputs.yaml"
            )
        finally:
            # Restore for fixture teardown
            _reg._REGISTRY[eid]      = saved_cls
            _reg._REGISTRY_META[eid] = saved_meta

        l04_registered   = [i for i in result_registered.issues   if i.code == "L-04"]
        l04_unregistered = [i for i in result_unregistered.issues if i.code == "L-04"]

        assert not l04_registered, "Plugin should pass when registered"
        assert l04_unregistered,   "Plugin should fail when unregistered"
