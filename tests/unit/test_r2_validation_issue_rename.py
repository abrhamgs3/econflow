"""
tests/unit/test_r2_validation_issue_rename.py — R2 regression suite.

Guards against C-3 regression: two unrelated public classes sharing the name
``ValidationIssue`` in ``econflow.config`` and ``econflow.ingestion``.

Coverage dimensions:
    1. Class identity  — each new name is a unique object; the two are distinct
    2. MRO / isinstance — both are dataclasses; neither is a subclass of the other
    3. Import paths    — canonical + backward-compat alias in every public module
    4. Serialization   — correct field sets survive round-trip via to_dict/to_json
    5. Cross-module disambiguation — can import BOTH simultaneously without collision
    6. Deprecated-alias identity   — alias *is* the canonical class, not a copy
    7. __all__ exports — both canonical names appear in their package __all__
    8. String representation — __str__ behaviour matches documented contract
    9. DataValidationReport integration — issues list typed to DataValidationIssue
   10. ConfigValidationIssue integration — ValidationResult.issues typed correctly
"""

from __future__ import annotations

import dataclasses
import json
from typing import Any

import pytest

# ---------------------------------------------------------------------------
# 1. Class identity — each canonical name is unique; both names are distinct
# ---------------------------------------------------------------------------

class TestClassIdentity:
    def test_config_validation_issue_exists(self) -> None:
        from econflow.config.validator import ConfigValidationIssue
        assert ConfigValidationIssue is not None

    def test_data_validation_issue_exists(self) -> None:
        from econflow.ingestion.validation import DataValidationIssue
        assert DataValidationIssue is not None

    def test_two_classes_are_distinct_objects(self) -> None:
        from econflow.config.validator import ConfigValidationIssue
        from econflow.ingestion.validation import DataValidationIssue
        assert ConfigValidationIssue is not DataValidationIssue

    def test_class_names_are_distinct(self) -> None:
        from econflow.config.validator import ConfigValidationIssue
        from econflow.ingestion.validation import DataValidationIssue
        assert ConfigValidationIssue.__name__ == "ConfigValidationIssue"
        assert DataValidationIssue.__name__ == "DataValidationIssue"

    def test_class_qualnames_are_distinct(self) -> None:
        from econflow.config.validator import ConfigValidationIssue
        from econflow.ingestion.validation import DataValidationIssue
        assert ConfigValidationIssue.__qualname__ != DataValidationIssue.__qualname__


# ---------------------------------------------------------------------------
# 2. MRO / isinstance — neither inherits from the other
# ---------------------------------------------------------------------------

class TestMROAndIsinstance:
    def test_config_issue_is_dataclass(self) -> None:
        from econflow.config.validator import ConfigValidationIssue
        assert dataclasses.is_dataclass(ConfigValidationIssue)

    def test_data_issue_is_dataclass(self) -> None:
        from econflow.ingestion.validation import DataValidationIssue
        assert dataclasses.is_dataclass(DataValidationIssue)

    def test_config_issue_not_subclass_of_data_issue(self) -> None:
        from econflow.config.validator import ConfigValidationIssue
        from econflow.ingestion.validation import DataValidationIssue
        assert not issubclass(ConfigValidationIssue, DataValidationIssue)

    def test_data_issue_not_subclass_of_config_issue(self) -> None:
        from econflow.config.validator import ConfigValidationIssue
        from econflow.ingestion.validation import DataValidationIssue
        assert not issubclass(DataValidationIssue, ConfigValidationIssue)

    def test_config_instance_not_isinstance_data(self) -> None:
        from econflow.config.validator import ConfigValidationIssue
        from econflow.ingestion.validation import DataValidationIssue
        cfg_issue = ConfigValidationIssue(
            stage="schema", severity="error",
            source="config.yaml", location="x", message="m",
        )
        assert not isinstance(cfg_issue, DataValidationIssue)

    def test_data_instance_not_isinstance_config(self) -> None:
        from econflow.config.validator import ConfigValidationIssue
        from econflow.ingestion.validation import DataValidationIssue
        data_issue = DataValidationIssue(
            code="V-01", check="required_columns", level="error", message="Missing"
        )
        assert not isinstance(data_issue, ConfigValidationIssue)


# ---------------------------------------------------------------------------
# 3. Import paths — all public access routes
# ---------------------------------------------------------------------------

class TestImportPaths:
    # Config canonical paths
    def test_config_canonical_from_validator_module(self) -> None:
        from econflow.config.validator import ConfigValidationIssue
        assert ConfigValidationIssue.__name__ == "ConfigValidationIssue"

    def test_config_canonical_from_config_package(self) -> None:
        from econflow.config import ConfigValidationIssue
        from econflow.config.validator import ConfigValidationIssue as CVI_ref
        assert ConfigValidationIssue is CVI_ref

    # Ingestion canonical paths
    def test_data_canonical_from_validation_module(self) -> None:
        from econflow.ingestion.validation import DataValidationIssue
        assert DataValidationIssue.__name__ == "DataValidationIssue"

    def test_data_canonical_from_ingestion_package(self) -> None:
        from econflow.ingestion import DataValidationIssue
        from econflow.ingestion.validation import DataValidationIssue as DVI_ref
        assert DataValidationIssue is DVI_ref

    # Deprecated alias — config
    def test_config_deprecated_alias_from_validator_module(self) -> None:
        from econflow.config.validator import ConfigValidationIssue, ValidationIssue
        assert ValidationIssue is ConfigValidationIssue

    def test_config_deprecated_alias_from_config_package(self) -> None:
        from econflow.config import ConfigValidationIssue, ValidationIssue
        assert ValidationIssue is ConfigValidationIssue

    # Deprecated alias — ingestion
    def test_ingestion_deprecated_alias_from_validation_module(self) -> None:
        from econflow.ingestion.validation import DataValidationIssue, ValidationIssue
        assert ValidationIssue is DataValidationIssue

    def test_ingestion_deprecated_alias_from_ingestion_package(self) -> None:
        from econflow.ingestion import DataValidationIssue, ValidationIssue
        assert ValidationIssue is DataValidationIssue


# ---------------------------------------------------------------------------
# 4. Serialization — correct fields survive construction
# ---------------------------------------------------------------------------

class TestFieldSets:
    """Each class has the right fields and only its own fields."""

    def test_config_issue_has_stage_field(self) -> None:
        from econflow.config.validator import ConfigValidationIssue
        fields = {f.name for f in dataclasses.fields(ConfigValidationIssue)}
        assert "stage" in fields

    def test_config_issue_has_severity_field(self) -> None:
        from econflow.config.validator import ConfigValidationIssue
        fields = {f.name for f in dataclasses.fields(ConfigValidationIssue)}
        assert "severity" in fields

    def test_config_issue_does_not_have_code_as_required(self) -> None:
        """code is optional (defaults to '') in ConfigValidationIssue."""
        from econflow.config.validator import ConfigValidationIssue
        # Should not raise — code has default
        issue = ConfigValidationIssue(
            stage="schema", severity="error",
            source="f.yaml", location="x", message="m",
        )
        assert issue.code == ""

    def test_data_issue_has_code_field(self) -> None:
        from econflow.ingestion.validation import DataValidationIssue
        fields = {f.name for f in dataclasses.fields(DataValidationIssue)}
        assert "code" in fields

    def test_data_issue_has_check_field(self) -> None:
        from econflow.ingestion.validation import DataValidationIssue
        fields = {f.name for f in dataclasses.fields(DataValidationIssue)}
        assert "check" in fields

    def test_data_issue_has_level_field(self) -> None:
        from econflow.ingestion.validation import DataValidationIssue
        fields = {f.name for f in dataclasses.fields(DataValidationIssue)}
        assert "level" in fields

    def test_data_issue_does_not_have_stage_field(self) -> None:
        from econflow.ingestion.validation import DataValidationIssue
        fields = {f.name for f in dataclasses.fields(DataValidationIssue)}
        assert "stage" not in fields

    def test_config_issue_does_not_have_check_field(self) -> None:
        from econflow.config.validator import ConfigValidationIssue
        fields = {f.name for f in dataclasses.fields(ConfigValidationIssue)}
        assert "check" not in fields

    def test_config_issue_full_construction(self) -> None:
        from econflow.config.validator import ConfigValidationIssue
        issue = ConfigValidationIssue(
            stage="semantic", severity="warning",
            source="models.yaml", location="models[0].id",
            message="Duplicate model ID", fix="rename it", code="L-09",
        )
        assert issue.stage == "semantic"
        assert issue.severity == "warning"
        assert issue.fix == "rename it"
        assert issue.code == "L-09"

    def test_data_issue_full_construction(self) -> None:
        from econflow.ingestion.validation import DataValidationIssue
        issue = DataValidationIssue(
            code="V-02", check="no_duplicate_keys",
            level="error", message="3 duplicates", detail="check prep script",
        )
        assert issue.code == "V-02"
        assert issue.check == "no_duplicate_keys"
        assert issue.level == "error"
        assert issue.detail == "check prep script"


# ---------------------------------------------------------------------------
# 5. Cross-module disambiguation — import BOTH simultaneously
# ---------------------------------------------------------------------------

class TestCrossModuleDisambiguation:
    def test_can_import_both_canonical_names_simultaneously(self) -> None:
        from econflow.config.validator import ConfigValidationIssue
        from econflow.ingestion.validation import DataValidationIssue
        # Both are importable in the same scope with no collision
        cfg = ConfigValidationIssue(
            stage="schema", severity="error",
            source="config.yaml", location="x", message="m",
        )
        data = DataValidationIssue(
            code="V-01", check="required_columns", level="error", message="missing"
        )
        assert type(cfg) is ConfigValidationIssue
        assert type(data) is DataValidationIssue
        assert type(cfg) is not type(data)

    def test_isinstance_discriminates_correctly(self) -> None:
        from econflow.config.validator import ConfigValidationIssue
        from econflow.ingestion.validation import DataValidationIssue
        cfg = ConfigValidationIssue(
            stage="yaml_syntax", severity="info",
            source="config.yaml", location="", message="ok",
        )
        data = DataValidationIssue(
            code="V-03", check="no_missing_identifiers", level="warning", message="nulls"
        )
        assert isinstance(cfg, ConfigValidationIssue)
        assert not isinstance(cfg, DataValidationIssue)
        assert isinstance(data, DataValidationIssue)
        assert not isinstance(data, ConfigValidationIssue)

    def test_config_package_and_ingestion_package_aliases_are_distinct(self) -> None:
        """The deprecated 'ValidationIssue' in each package points to different classes."""
        from econflow.config import ValidationIssue as ConfigVI
        from econflow.ingestion import ValidationIssue as IngestVI
        assert ConfigVI is not IngestVI


# ---------------------------------------------------------------------------
# 6. Deprecated-alias identity — alias IS the class, not a subclass or copy
# ---------------------------------------------------------------------------

class TestDeprecatedAliasIdentity:
    def test_config_alias_is_not_copy(self) -> None:
        from econflow.config.validator import ConfigValidationIssue, ValidationIssue
        assert ValidationIssue is ConfigValidationIssue

    def test_config_alias_same_id(self) -> None:
        from econflow.config.validator import ConfigValidationIssue, ValidationIssue
        assert id(ValidationIssue) == id(ConfigValidationIssue)

    def test_ingestion_alias_is_not_copy(self) -> None:
        from econflow.ingestion.validation import DataValidationIssue, ValidationIssue
        assert ValidationIssue is DataValidationIssue

    def test_ingestion_alias_same_id(self) -> None:
        from econflow.ingestion.validation import DataValidationIssue, ValidationIssue
        assert id(ValidationIssue) == id(DataValidationIssue)

    def test_instances_created_via_alias_pass_canonical_isinstance(self) -> None:
        from econflow.config.validator import ConfigValidationIssue, ValidationIssue
        # Create via alias
        issue = ValidationIssue(
            stage="schema", severity="error",
            source="f.yaml", location="x", message="m",
        )
        # isinstance check against canonical
        assert isinstance(issue, ConfigValidationIssue)

    def test_ingestion_instances_created_via_alias_pass_canonical_isinstance(self) -> None:
        from econflow.ingestion.validation import DataValidationIssue, ValidationIssue
        issue = ValidationIssue(
            code="V-01", check="c", level="error", message="m"
        )
        assert isinstance(issue, DataValidationIssue)


# ---------------------------------------------------------------------------
# 7. __all__ exports
# ---------------------------------------------------------------------------

class TestAllExports:
    def test_config_validator_module_exports_new_name(self) -> None:
        import econflow.config.validator as m
        assert hasattr(m, "ConfigValidationIssue")

    def test_config_validator_module_exports_alias(self) -> None:
        import econflow.config.validator as m
        assert hasattr(m, "ValidationIssue")

    def test_config_package_all_has_new_name(self) -> None:
        import econflow.config as pkg
        assert "ConfigValidationIssue" in pkg.__all__

    def test_config_package_all_has_deprecated_alias(self) -> None:
        import econflow.config as pkg
        assert "ValidationIssue" in pkg.__all__

    def test_ingestion_validation_module_exports_new_name(self) -> None:
        import econflow.ingestion.validation as m
        assert hasattr(m, "DataValidationIssue")

    def test_ingestion_validation_module_exports_alias(self) -> None:
        import econflow.ingestion.validation as m
        assert hasattr(m, "ValidationIssue")

    def test_ingestion_package_all_has_new_name(self) -> None:
        import econflow.ingestion as pkg
        assert "DataValidationIssue" in pkg.__all__

    def test_ingestion_package_all_has_deprecated_alias(self) -> None:
        import econflow.ingestion as pkg
        assert "ValidationIssue" in pkg.__all__


# ---------------------------------------------------------------------------
# 8. String representation
# ---------------------------------------------------------------------------

class TestStringRepresentation:
    def test_config_issue_str_includes_stage_and_severity(self) -> None:
        from econflow.config.validator import ConfigValidationIssue
        issue = ConfigValidationIssue(
            stage="schema", severity="error",
            source="config.yaml", location="variables",
            message="Missing field", code="",
        )
        s = str(issue)
        assert "schema" in s
        assert "error" in s
        assert "config.yaml" in s

    def test_config_issue_str_includes_code_when_present(self) -> None:
        from econflow.config.validator import ConfigValidationIssue
        issue = ConfigValidationIssue(
            stage="semantic", severity="warning",
            source="models.yaml", location="x",
            message="msg", code="L-09",
        )
        assert "[L-09]" in str(issue)

    def test_config_issue_str_includes_fix_when_present(self) -> None:
        from econflow.config.validator import ConfigValidationIssue
        issue = ConfigValidationIssue(
            stage="cross_file", severity="error",
            source="outputs.yaml", location="x",
            message="bad ref", fix="add the model",
        )
        assert "Fix:" in str(issue)
        assert "add the model" in str(issue)

    def test_data_issue_has_no_str_method_override(self) -> None:
        """DataValidationIssue uses default dataclass __repr__, not a custom __str__."""
        from econflow.ingestion.validation import DataValidationIssue
        issue = DataValidationIssue(code="V-01", check="c", level="error", message="m")
        # Default dataclass __repr__ includes the class name
        r = repr(issue)
        assert "DataValidationIssue" in r


# ---------------------------------------------------------------------------
# 9. DataValidationReport integration
# ---------------------------------------------------------------------------

class TestDataValidationReportIntegration:
    def test_report_add_error_creates_data_validation_issue(self) -> None:
        from econflow.ingestion.validation import DataValidationIssue, DataValidationReport
        report = DataValidationReport(path="f.csv", row_count=10, col_count=3)
        report.add_error("V-01", "required_columns", "Missing: ['x']")
        assert len(report.issues) == 1
        assert isinstance(report.issues[0], DataValidationIssue)

    def test_report_add_warning_creates_data_validation_issue(self) -> None:
        from econflow.ingestion.validation import DataValidationIssue, DataValidationReport
        report = DataValidationReport(path="f.csv", row_count=10, col_count=3)
        report.add_warning("V-06", "missing_value_pct", "col x: 30% missing")
        assert isinstance(report.issues[0], DataValidationIssue)

    def test_report_to_dict_serializes_issues(self) -> None:
        from econflow.ingestion.validation import DataValidationReport
        report = DataValidationReport(path="f.csv", row_count=5, col_count=2)
        report.add_error("V-02", "no_duplicate_keys", "3 duplicates")
        d = report.to_dict()
        assert d["issues"][0]["code"] == "V-02"
        assert d["issues"][0]["level"] == "error"

    def test_report_to_json_is_valid_json(self) -> None:
        from econflow.ingestion.validation import DataValidationReport
        report = DataValidationReport(path="f.csv", row_count=5, col_count=2)
        report.add_error("V-01", "required_columns", "missing")
        parsed = json.loads(report.to_json())
        assert parsed["issues"][0]["code"] == "V-01"

    def test_report_issues_not_config_validation_issue(self) -> None:
        from econflow.config.validator import ConfigValidationIssue
        from econflow.ingestion.validation import DataValidationReport
        report = DataValidationReport(path="f.csv", row_count=5, col_count=2)
        report.add_error("V-01", "required_columns", "missing")
        assert not isinstance(report.issues[0], ConfigValidationIssue)


# ---------------------------------------------------------------------------
# 10. ConfigValidationIssue integration via ValidationResult
# ---------------------------------------------------------------------------

class TestConfigValidationIssueIntegration:
    def _make_issue(self, **kwargs: Any):
        from econflow.config.validator import ConfigValidationIssue
        defaults = dict(
            stage="schema", severity="error",
            source="config.yaml", location="x", message="m",
        )
        defaults.update(kwargs)
        return ConfigValidationIssue(**defaults)

    def test_validation_result_issues_typed_correctly(self) -> None:
        from econflow.config.validator import ConfigValidationIssue, ValidationResult
        issue = self._make_issue()
        result = ValidationResult(issues=[issue])
        assert isinstance(result.issues[0], ConfigValidationIssue)

    def test_validation_result_errors_property(self) -> None:
        from econflow.config.validator import ConfigValidationIssue, ValidationResult
        err = self._make_issue(severity="error")
        warn = self._make_issue(severity="warning")
        result = ValidationResult(issues=[err, warn])
        assert len(result.errors) == 1
        assert isinstance(result.errors[0], ConfigValidationIssue)

    def test_validation_result_warnings_property(self) -> None:
        from econflow.config.validator import ConfigValidationIssue, ValidationResult
        warn = self._make_issue(severity="warning")
        result = ValidationResult(issues=[warn])
        assert len(result.warnings) == 1
        assert isinstance(result.warnings[0], ConfigValidationIssue)

    def test_issues_not_data_validation_issue(self) -> None:
        from econflow.config.validator import ValidationResult
        from econflow.ingestion.validation import DataValidationIssue
        issue = self._make_issue()
        result = ValidationResult(issues=[issue])
        assert not isinstance(result.issues[0], DataValidationIssue)
