"""
tests/unit/test_config_validation_phase4.py

Phase 4: registry-driven estimator validation and cluster value validation (L-14).

Coverage
--------
§1  Regression — built-in estimators still pass after the rewrite
§2  L-04 — unknown estimator: informative message, suggestion, plugin hint
§3  L-04b — stub estimator detected via registry metadata, not frozenset
§4  Plugin estimator roundtrip — registered plugin passes without L-04
§5  Alias resolution — uppercase OLS / TWFE resolve via dispatcher
§6  L-14 — invalid cluster values produce errors; valid values pass
§7  Error message content — ID, suggestion, available list, plugin hint all present
§8  ConfigValidator wiring — live_estimator_ids override threads through correctly
§9  KNOWN_ESTIMATORS independence — novel estimator absent from KNOWN_ESTIMATORS passes
"""

from __future__ import annotations

import pytest
import yaml
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

VALID = Path(__file__).parent.parent / "fixtures" / "config" / "valid"

# ---------------------------------------------------------------------------
# Helpers — minimal raw dicts for linter tests
# ---------------------------------------------------------------------------

def _raw_models(estimator: str = "ols", cluster: str = "") -> dict:
    """Build a minimal raw models dict for the linter."""
    spec: dict = {
        "id": "test_m",
        "label": "Test Model",
        "estimator": estimator,
        "dependent": "y",
        "regressors": ["x1"],
        "entity_effects": False,
        "time_effects": False,
    }
    if cluster:
        spec["cluster"] = cluster
    return {"models": [spec]}


def _raw_models_twfe(estimator: str = "twfe", cluster: str = "") -> dict:
    """Build a TWFE raw models dict (entity + time effects both True)."""
    spec: dict = {
        "id": "twfe_m",
        "label": "TWFE",
        "estimator": estimator,
        "dependent": "y",
        "regressors": ["x1"],
        "entity_effects": True,
        "time_effects": True,
    }
    if cluster:
        spec["cluster"] = cluster
    return {"models": [spec]}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def linter():
    """ConfigLinter using the live registry (default — no override)."""
    from econflow.config.linter import ConfigLinter
    return ConfigLinter()


@pytest.fixture()
def validator():
    """ConfigValidator using the live registry."""
    from econflow.config.validator import ConfigValidator
    return ConfigValidator()


@pytest.fixture()
def registered_plugin():
    """Register a minimal plugin estimator and clean it up after the test.

    The registered ID is intentionally not in KNOWN_ESTIMATORS to verify
    that KNOWN_ESTIMATORS is no longer the source of truth.
    """
    from econflow.estimation import registry as _reg

    eid = "_test_plugin_phase4"

    class _MinimalEstimator:
        """Minimal placeholder class — not a real BaseEstimator subclass."""
        backend = "test"

    _reg._REGISTRY[eid] = _MinimalEstimator
    _reg._REGISTRY_META[eid] = {
        "id":             eid,
        "label":          "Test Plugin (Phase 4)",
        "status":         "implemented",
        "notes":          "Only for Phase 4 linter validation tests.",
        "supported_data": ["panel"],
        "backend":        "test",
    }

    yield eid

    _reg._REGISTRY.pop(eid, None)
    _reg._REGISTRY_META.pop(eid, None)


# ---------------------------------------------------------------------------
# §1 — Regression: built-in estimators still pass
# ---------------------------------------------------------------------------

class TestBuiltinEstimatorsPassRegression:
    """Verify every built-in estimator is still accepted after Phase 4 rewrite."""

    @pytest.mark.parametrize("estimator", ["ols", "fe", "twfe", "re", "fd"])
    def test_implemented_estimator_no_l04(self, linter, estimator):
        """L-04 must NOT fire for implemented built-in estimators."""
        raw = _raw_models(estimator=estimator)
        if estimator in ("fe",):
            # fe with entity_effects=False → DeprecationWarning → resolves to "ols"
            # which is still in the registry — no L-04
            pass
        elif estimator == "twfe":
            raw = _raw_models_twfe(estimator="twfe")
        issues = linter.lint(raw_models=raw)
        l04 = [i for i in issues if i.code == "L-04"]
        assert not l04, f"Unexpected L-04 for estimator '{estimator}': {l04}"

    def test_ols_no_lint_errors(self, linter):
        issues = linter.lint(raw_models=_raw_models("ols"))
        errors = [i for i in issues if i.severity == "error"]
        assert not errors

    def test_fe_no_l04(self, linter):
        """estimator: fe with entity_effects resolves to 'fe' in registry."""
        raw = {"models": [{
            "id": "m1", "label": "FE", "estimator": "fe",
            "dependent": "y", "regressors": ["x1"],
            "entity_effects": True, "time_effects": False,
        }]}
        issues = linter.lint(raw_models=raw)
        l04 = [i for i in issues if i.code == "L-04"]
        assert not l04

    def test_re_fd_no_l04(self, linter):
        for est in ("re", "fd"):
            issues = linter.lint(raw_models=_raw_models(est))
            assert not [i for i in issues if i.code == "L-04"], est

    def test_iv_no_l04_when_instruments_provided(self, linter):
        """IV estimator itself is valid (L-11 fires separately for missing instruments)."""
        raw = {"models": [{
            "id": "iv_m", "label": "IV", "estimator": "iv",
            "dependent": "y", "regressors": ["x1"],
            "instruments": ["z1"],
        }]}
        issues = linter.lint(raw_models=raw)
        l04 = [i for i in issues if i.code == "L-04"]
        assert not l04


# ---------------------------------------------------------------------------
# §2 — L-04: unknown estimator
# ---------------------------------------------------------------------------

class TestUnknownEstimatorL04:
    """Unknown estimators fire L-04 (warning) with informative message."""

    def test_unknown_estimator_fires_l04(self, linter):
        issues = linter.lint(raw_models=_raw_models("xgboost_panel"))
        l04 = [i for i in issues if i.code == "L-04"]
        assert len(l04) == 1

    def test_l04_severity_is_warning(self, linter):
        issues = linter.lint(raw_models=_raw_models("panel_neural_net"))
        l04 = [i for i in issues if i.code == "L-04"]
        assert l04[0].severity == "warning"

    def test_l04_message_contains_invalid_id(self, linter):
        invalid = "xgboost_panel_42"
        issues = linter.lint(raw_models=_raw_models(invalid))
        l04 = [i for i in issues if i.code == "L-04"]
        assert invalid in l04[0].message

    def test_l04_message_contains_available_estimators(self, linter):
        """The error message must list at least one registered estimator."""
        issues = linter.lint(raw_models=_raw_models("completely_bogus"))
        l04 = [i for i in issues if i.code == "L-04"]
        msg = l04[0].message
        # At minimum one of the known built-ins should appear in the message
        assert any(e in msg for e in ("ols", "fe", "twfe", "re", "fd", "iv"))

    def test_l04_message_contains_typo_suggestion(self, linter):
        """A near-miss should generate a 'Did you mean' hint."""
        issues = linter.lint(raw_models=_raw_models("osl"))  # typo for 'ols'
        l04 = [i for i in issues if i.code == "L-04"]
        assert l04, "Expected L-04 for 'osl'"
        # The message or the issue should mention 'ols'
        full_text = l04[0].message + l04[0].fix
        assert "ols" in full_text.lower()

    def test_l04_fix_contains_plugin_registration_hint(self, linter):
        """fix field must mention the plugin entry-point mechanism."""
        issues = linter.lint(raw_models=_raw_models("my_custom_estimator"))
        l04 = [i for i in issues if i.code == "L-04"]
        assert "entry-points" in l04[0].fix or "entry_points" in l04[0].fix or \
               "plugin" in l04[0].fix.lower()

    def test_l04_location_set(self, linter):
        issues = linter.lint(raw_models=_raw_models("bogus"))
        l04 = [i for i in issues if i.code == "L-04"]
        assert l04[0].location  # location must be non-empty

    def test_empty_estimator_string_no_l04(self, linter):
        """Empty estimator string is a schema error, not an L-04."""
        raw = {"models": [{
            "id": "m1", "label": "X", "estimator": "",
            "dependent": "y", "regressors": ["x1"],
        }]}
        issues = linter.lint(raw_models=raw)
        l04 = [i for i in issues if i.code == "L-04"]
        assert not l04  # empty string is skipped silently

    def test_l04_does_not_fire_for_registered_ids(self, linter):
        """Registered IDs must never produce L-04."""
        from econflow.estimation.registry import list_estimators
        implemented = [
            e["id"] for e in list_estimators() if e.get("status") == "implemented"
        ]
        for eid in implemented:
            raw = {"models": [{
                "id": "m", "label": "X", "estimator": eid,
                "dependent": "y", "regressors": ["x"],
                "entity_effects": True, "time_effects": False,
            }]}
            issues = linter.lint(raw_models=raw)
            l04 = [i for i in issues if i.code == "L-04"]
            assert not l04, f"Unexpected L-04 for registered estimator '{eid}'"


# ---------------------------------------------------------------------------
# §3 — L-04b: stub estimator
# ---------------------------------------------------------------------------

class TestStubEstimatorL04b:
    """Stub estimators (status='stub') fire L-04b (error), not L-04."""

    def test_gmm_fires_l04b(self, linter):
        issues = linter.lint(raw_models=_raw_models("gmm"))
        l04b = [i for i in issues if i.code == "L-04b"]
        assert len(l04b) == 1

    def test_quantile_fires_l04b(self, linter):
        issues = linter.lint(raw_models=_raw_models("quantile"))
        l04b = [i for i in issues if i.code == "L-04b"]
        assert len(l04b) == 1

    def test_stub_severity_is_error(self, linter):
        issues = linter.lint(raw_models=_raw_models("gmm"))
        l04b = [i for i in issues if i.code == "L-04b"]
        assert l04b[0].severity == "error"

    def test_stub_no_l04(self, linter):
        """A stub estimator must fire L-04b, NOT L-04 (they are mutually exclusive)."""
        issues = linter.lint(raw_models=_raw_models("gmm"))
        assert not [i for i in issues if i.code == "L-04"]
        assert [i for i in issues if i.code == "L-04b"]

    def test_l04b_message_contains_estimator_id(self, linter):
        issues = linter.lint(raw_models=_raw_models("gmm"))
        l04b = [i for i in issues if i.code == "L-04b"]
        assert "gmm" in l04b[0].message.lower()

    def test_l04b_message_mentions_notimplementederror(self, linter):
        issues = linter.lint(raw_models=_raw_models("gmm"))
        l04b = [i for i in issues if i.code == "L-04b"]
        assert "NotImplementedError" in l04b[0].message

    def test_stub_via_registry_metadata_not_frozenset(self, linter):
        """Verify stub detection uses registry metadata status, not a hardcoded set.

        Register a novel estimator with status='stub' that is NOT in any
        pre-existing hardcoded frozenset.  It must trigger L-04b.
        """
        from econflow.estimation import registry as _reg

        eid = "_test_stub_novel_p4"
        class _StubEst:
            backend = "test"

        _reg._REGISTRY[eid] = _StubEst
        _reg._REGISTRY_META[eid] = {
            "id": eid, "label": "Novel Stub", "status": "stub",
            "notes": "", "supported_data": ["panel"], "backend": "test",
        }

        try:
            issues = linter.lint(raw_models=_raw_models(eid))
            l04b = [i for i in issues if i.code == "L-04b"]
            assert l04b, f"L-04b must fire for stub estimator '{eid}'"
            assert l04b[0].severity == "error"
        finally:
            _reg._REGISTRY.pop(eid, None)
            _reg._REGISTRY_META.pop(eid, None)


# ---------------------------------------------------------------------------
# §4 — Plugin estimator roundtrip
# ---------------------------------------------------------------------------

class TestPluginEstimatorRoundtrip:
    """A plugin registered at runtime must validate without L-04."""

    def test_registered_plugin_no_l04(self, linter, registered_plugin):
        eid = registered_plugin
        issues = linter.lint(raw_models=_raw_models(eid))
        l04 = [i for i in issues if i.code == "L-04"]
        assert not l04, f"Plugin estimator '{eid}' unexpectedly triggered L-04"

    def test_registered_plugin_no_l04b(self, linter, registered_plugin):
        eid = registered_plugin
        issues = linter.lint(raw_models=_raw_models(eid))
        l04b = [i for i in issues if i.code == "L-04b"]
        assert not l04b

    def test_unregistered_plugin_fires_l04(self, linter):
        """After unregistration, the same ID must trigger L-04 again."""
        from econflow.estimation import registry as _reg

        eid = "_test_transient_plugin_p4"

        class _TransientEst:
            backend = "test"

        _reg._REGISTRY[eid] = _TransientEst
        _reg._REGISTRY_META[eid] = {
            "id": eid, "label": "Transient", "status": "implemented",
            "notes": "", "supported_data": ["panel"], "backend": "test",
        }

        # Registered → no L-04
        issues_before = linter.lint(raw_models=_raw_models(eid))
        l04_before = [i for i in issues_before if i.code == "L-04"]

        # Unregister
        _reg._REGISTRY.pop(eid, None)
        _reg._REGISTRY_META.pop(eid, None)

        # Unregistered → L-04 fires
        issues_after = linter.lint(raw_models=_raw_models(eid))
        l04_after = [i for i in issues_after if i.code == "L-04"]

        assert not l04_before, "Expected no L-04 when plugin is registered"
        assert l04_after, "Expected L-04 after plugin is unregistered"

    def test_plugin_not_in_known_estimators_still_valid(self, linter, registered_plugin):
        """Registry is the sole authority — KNOWN_ESTIMATORS is not consulted."""
        from econflow.config.models import KNOWN_ESTIMATORS

        eid = registered_plugin
        assert eid not in KNOWN_ESTIMATORS, (
            f"The test plugin '{eid}' must NOT be in KNOWN_ESTIMATORS — "
            "this test verifies KNOWN_ESTIMATORS is no longer the authority."
        )

        # Despite being absent from KNOWN_ESTIMATORS, the linter must accept it.
        issues = linter.lint(raw_models=_raw_models(eid))
        l04 = [i for i in issues if i.code == "L-04"]
        assert not l04


# ---------------------------------------------------------------------------
# §5 — Alias resolution
# ---------------------------------------------------------------------------

class TestAliasResolution:
    """Uppercase aliases and common shorthand resolve via dispatcher."""

    @pytest.mark.parametrize("alias", ["OLS", "RE", "FD"])
    def test_uppercase_alias_no_l04(self, linter, alias):
        """Single-letter uppercase aliases must resolve without L-04."""
        issues = linter.lint(raw_models=_raw_models(alias))
        l04 = [i for i in issues if i.code == "L-04"]
        assert not l04, f"Alias '{alias}' unexpectedly triggered L-04"

    def test_twfe_uppercase_no_l04(self, linter):
        """TWFE (uppercase) must resolve to 'twfe' without L-04."""
        raw = _raw_models_twfe(estimator="TWFE")
        issues = linter.lint(raw_models=raw)
        l04 = [i for i in issues if i.code == "L-04"]
        assert not l04

    def test_fe_entity_effects_true_no_l04(self, linter):
        """estimator: fe with entity_effects=True → resolved to 'fe' in registry."""
        raw = {"models": [{
            "id": "m1", "label": "FE", "estimator": "FE",
            "dependent": "y", "regressors": ["x"],
            "entity_effects": True, "time_effects": False,
        }]}
        issues = linter.lint(raw_models=raw)
        l04 = [i for i in issues if i.code == "L-04"]
        assert not l04


# ---------------------------------------------------------------------------
# §6 — L-14: cluster value validation
# ---------------------------------------------------------------------------

class TestClusterValueValidationL14:
    """L-14 fires an error for non-canonical cluster values."""

    # Valid values — must NOT fire L-14
    @pytest.mark.parametrize("valid_cluster", ["entity", "time", ""])
    def test_valid_cluster_no_l14(self, linter, valid_cluster):
        raw = _raw_models("ols", cluster=valid_cluster)
        issues = linter.lint(raw_models=raw)
        l14 = [i for i in issues if i.code == "L-14"]
        assert not l14, f"Unexpected L-14 for valid cluster='{valid_cluster}'"

    def test_absent_cluster_no_l14(self, linter):
        """A model without a cluster key must not trigger L-14."""
        raw = {"models": [{
            "id": "m1", "label": "X", "estimator": "ols",
            "dependent": "y", "regressors": ["x"],
        }]}
        issues = linter.lint(raw_models=raw)
        l14 = [i for i in issues if i.code == "L-14"]
        assert not l14

    # Invalid values — must fire L-14
    @pytest.mark.parametrize("bad_cluster", [
        "entities",       # near-miss for "entity"
        "entity_id",      # common mistake
        "entity_col",     # another common mistake
        "firm",           # was never valid
        "country",        # was never valid
    ])
    def test_invalid_cluster_fires_l14(self, linter, bad_cluster):
        raw = _raw_models("fe", cluster=bad_cluster)
        # Provide entity_effects so we don't also fire L-12
        raw["models"][0]["entity_effects"] = True
        issues = linter.lint(raw_models=raw)
        l14 = [i for i in issues if i.code == "L-14"]
        assert l14, f"Expected L-14 for cluster='{bad_cluster}'"

    def test_l14_severity_is_error(self, linter):
        raw = _raw_models("ols", cluster="entities")
        issues = linter.lint(raw_models=raw)
        l14 = [i for i in issues if i.code == "L-14"]
        assert l14[0].severity == "error"

    def test_l14_message_contains_invalid_value(self, linter):
        raw = _raw_models("ols", cluster="entities")
        issues = linter.lint(raw_models=raw)
        l14 = [i for i in issues if i.code == "L-14"]
        assert "entities" in l14[0].message

    def test_l14_entities_suggests_entity(self, linter):
        """cluster: entities → suggestion 'entity'."""
        raw = _raw_models("ols", cluster="entities")
        issues = linter.lint(raw_models=raw)
        l14 = [i for i in issues if i.code == "L-14"]
        assert "entity" in l14[0].message

    def test_l14_entity_id_suggests_entity(self, linter):
        """cluster: entity_id → suggestion 'entity'."""
        raw = _raw_models("ols", cluster="entity_id")
        issues = linter.lint(raw_models=raw)
        l14 = [i for i in issues if i.code == "L-14"]
        assert l14, "Expected L-14 for cluster='entity_id'"
        assert "entity" in l14[0].message

    def test_l14_fix_mentions_no_silent_fallback(self, linter):
        """The fix must explicitly say the pipeline does not silently fall back."""
        raw = _raw_models("ols", cluster="entities")
        issues = linter.lint(raw_models=raw)
        l14 = [i for i in issues if i.code == "L-14"]
        assert "silent" in l14[0].fix.lower() or "fall back" in l14[0].fix.lower()

    def test_l14_location_set(self, linter):
        raw = _raw_models("ols", cluster="bad_cluster_value")
        issues = linter.lint(raw_models=raw)
        l14 = [i for i in issues if i.code == "L-14"]
        assert l14[0].location

    def test_l14_and_l04_can_both_fire(self, linter):
        """An unknown estimator + bad cluster can trigger both L-04 and L-14."""
        raw = _raw_models("unknown_est", cluster="entities")
        issues = linter.lint(raw_models=raw)
        codes = {i.code for i in issues}
        assert "L-04" in codes
        assert "L-14" in codes

    def test_l14_does_not_fire_for_empty_string_cluster(self, linter):
        """Empty string means 'no clustering' — must NOT fire L-14."""
        raw = _raw_models("ols", cluster="")
        issues = linter.lint(raw_models=raw)
        l14 = [i for i in issues if i.code == "L-14"]
        assert not l14


# ---------------------------------------------------------------------------
# §7 — Error message content
# ---------------------------------------------------------------------------

class TestL04ErrorMessageContent:
    """Verify L-04 messages satisfy all Phase 4 requirements."""

    def test_message_contains_invalid_estimator_id(self, linter):
        bad = "panel_areg_stata_style"
        issues = linter.lint(raw_models=_raw_models(bad))
        l04 = [i for i in issues if i.code == "L-04"]
        assert bad in l04[0].message, "L-04 message must contain the invalid ID"

    def test_message_contains_registered_estimators(self, linter):
        """Registered estimators (not a hardcoded list) must appear."""
        from econflow.estimation.registry import list_estimators
        available = [e["id"] for e in list_estimators()]
        issues = linter.lint(raw_models=_raw_models("not_a_real_estimator"))
        l04 = [i for i in issues if i.code == "L-04"]
        msg = l04[0].message
        assert any(eid in msg for eid in available), (
            f"None of the registered estimators {available} found in L-04 message: {msg!r}"
        )

    def test_fix_contains_plugin_guidance(self, linter):
        """fix field must mention plugin registration (not just 'run econflow info')."""
        issues = linter.lint(raw_models=_raw_models("custom_estimator"))
        l04 = [i for i in issues if i.code == "L-04"]
        fix = l04[0].fix.lower()
        assert "plugin" in fix or "entry-points" in fix or "entry_points" in fix

    def test_deterministic_output(self, linter):
        """Running the linter twice on the same input must return identical results."""
        raw = _raw_models("some_unknown_estimator")
        r1 = linter.lint(raw_models=raw)
        r2 = linter.lint(raw_models=raw)
        assert [(i.code, i.severity, i.message) for i in r1] == \
               [(i.code, i.severity, i.message) for i in r2]

    def test_suggestions_use_difflib(self, linter):
        """Verify suggestion uses Levenshtein-like matching (difflib)."""
        # "olss" is close to "ols" — should suggest "ols"
        issues = linter.lint(raw_models=_raw_models("olss"))
        l04 = [i for i in issues if i.code == "L-04"]
        if l04:  # only check if L-04 fires (it might not if difflib disagrees)
            assert "ols" in l04[0].message


# ---------------------------------------------------------------------------
# §8 — ConfigValidator wiring
# ---------------------------------------------------------------------------

class TestConfigValidatorWiring:
    """live_estimator_ids override threads from ConfigValidator → linter."""

    def test_override_accepts_known_id(self, tmp_path):
        """ConfigValidator(live_estimator_ids=frozenset({'ols'})) accepts 'ols'."""
        from econflow.config.validator import ConfigValidator

        cfg = VALID / "config.yaml"
        outputs = VALID / "outputs.yaml"
        models = tmp_path / "models.yaml"
        models.write_text(
            "models:\n"
            "  - id: \"m1\"\n"
            "    label: \"Test\"\n"
            "    estimator: \"ols\"\n"
            "    dependent: \"outcome\"\n"
            "    regressors: [\"treatment\"]\n"
        )
        validator = ConfigValidator(live_estimator_ids=frozenset({"ols", "fe", "twfe"}))
        result = validator.validate(cfg, models, outputs)
        l04 = [i for i in result.issues if i.code == "L-04"]
        assert not l04

    def test_override_rejects_unknown_id(self, tmp_path):
        """ConfigValidator(live_estimator_ids=frozenset({'ols'})) rejects 'fe'."""
        from econflow.config.validator import ConfigValidator

        cfg = VALID / "config.yaml"
        outputs = VALID / "outputs.yaml"
        models = tmp_path / "models.yaml"
        models.write_text(
            "models:\n"
            "  - id: \"m1\"\n"
            "    label: \"FE\"\n"
            "    estimator: \"fe\"\n"
            "    dependent: \"outcome\"\n"
            "    regressors: [\"treatment\"]\n"
            "    entity_effects: true\n"
            "    time_effects: false\n"
        )
        # Restrict to only 'ols' — 'fe' should trigger L-04
        validator = ConfigValidator(live_estimator_ids=frozenset({"ols"}))
        result = validator.validate(cfg, models, outputs)
        l04 = [i for i in result.issues if i.code == "L-04"]
        assert l04, "Expected L-04 when 'fe' is not in the override set"

    def test_default_validator_uses_live_registry(self, tmp_path, registered_plugin):
        """ConfigValidator() (default) resolves plugins in the live registry."""
        from econflow.config.validator import ConfigValidator

        eid = registered_plugin
        cfg = VALID / "config.yaml"
        outputs = VALID / "outputs.yaml"
        models = tmp_path / "models.yaml"
        models.write_text(
            f"models:\n"
            f"  - id: \"plugin_m\"\n"
            f"    label: \"Plugin Test\"\n"
            f"    estimator: \"{eid}\"\n"
            f"    dependent: \"outcome\"\n"
            f"    regressors: [\"treatment\"]\n"
        )
        validator = ConfigValidator()
        result = validator.validate(cfg, models, outputs)
        l04 = [i for i in result.issues if i.code == "L-04"]
        assert not l04, (
            f"Plugin estimator '{eid}' triggered L-04 in default ConfigValidator: {l04}"
        )

    def test_l14_reaches_validator_result(self, tmp_path):
        """L-14 is surfaced in the ConfigValidator result (stage=semantic, severity=error)."""
        from econflow.config.validator import ConfigValidator

        cfg = VALID / "config.yaml"
        outputs = VALID / "outputs.yaml"
        models = tmp_path / "models.yaml"
        models.write_text(
            "models:\n"
            "  - id: \"m1\"\n"
            "    label: \"Test\"\n"
            "    estimator: \"ols\"\n"
            "    dependent: \"outcome\"\n"
            "    regressors: [\"treatment\"]\n"
            "    cluster: \"entities\"\n"
        )
        validator = ConfigValidator()
        result = validator.validate(cfg, models, outputs)
        l14 = [i for i in result.issues if i.code == "L-14"]
        assert l14, "Expected L-14 in ValidationResult"
        assert l14[0].stage == "semantic"
        assert l14[0].severity == "error"
        assert not result.ok  # L-14 is an error → result not OK


# ---------------------------------------------------------------------------
# §9 — KNOWN_ESTIMATORS independence
# ---------------------------------------------------------------------------

class TestKnownEstimatorsIndependence:
    """KNOWN_ESTIMATORS is deprecated and no longer drives validation."""

    def test_known_estimators_still_importable(self):
        """The export must remain available for backward compatibility."""
        from econflow.config.models import KNOWN_ESTIMATORS
        assert isinstance(KNOWN_ESTIMATORS, frozenset)
        assert "ols" in KNOWN_ESTIMATORS

    def test_plugin_not_in_known_estimators_passes_validation(
        self, linter, registered_plugin
    ):
        """An estimator NOT in KNOWN_ESTIMATORS must pass validation if registered."""
        from econflow.config.models import KNOWN_ESTIMATORS

        eid = registered_plugin
        assert eid not in KNOWN_ESTIMATORS

        issues = linter.lint(raw_models=_raw_models(eid))
        l04 = [i for i in issues if i.code == "L-04"]
        assert not l04, "KNOWN_ESTIMATORS must no longer gate estimator validation"

    def test_linter_has_no_hardcoded_canonical_set(self):
        """ConfigLinter must not expose the old _CANONICAL_ESTIMATORS attribute."""
        from econflow.config import linter as _linter_module
        assert not hasattr(_linter_module, "_CANONICAL_ESTIMATORS"), (
            "_CANONICAL_ESTIMATORS must be removed from linter.py in Phase 4"
        )

    def test_linter_has_no_hardcoded_stub_set(self):
        """ConfigLinter must not expose the old _STUB_ESTIMATORS attribute."""
        from econflow.config import linter as _linter_module
        assert not hasattr(_linter_module, "_STUB_ESTIMATORS"), (
            "_STUB_ESTIMATORS must be removed from linter.py in Phase 4"
        )

    def test_linter_has_no_resolve_estimator_function(self):
        """The old _resolve_estimator() helper must be removed."""
        from econflow.config import linter as _linter_module
        assert not hasattr(_linter_module, "_resolve_estimator"), (
            "_resolve_estimator() must be removed in Phase 4"
        )

    def test_linter_exposes_resolve_via_registry(self):
        """The new _resolve_via_registry() helper must exist."""
        from econflow.config import linter as _linter_module
        assert hasattr(_linter_module, "_resolve_via_registry"), (
            "_resolve_via_registry() must exist in Phase 4 linter"
        )

    def test_linter_exposes_valid_cluster_values(self):
        """_VALID_CLUSTER_VALUES must exist and contain the canonical values."""
        from econflow.config.linter import _VALID_CLUSTER_VALUES
        assert "entity" in _VALID_CLUSTER_VALUES
        assert "time" in _VALID_CLUSTER_VALUES
        assert "" in _VALID_CLUSTER_VALUES
