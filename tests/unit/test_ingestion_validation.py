"""
tests/unit/test_ingestion_validation.py — Unit tests for DataValidator.

Covers all 6 validation checks (V-00 through V-06) plus report serialization.
"""

from __future__ import annotations

import csv
from pathlib import Path

from econflow.ingestion.validation import (
    DataValidationConfig,
    DataValidationIssue,
    DataValidationReport,
    DataValidator,
    ValidationIssue,  # deprecated alias — backward-compat import
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_csv(path: Path, rows: list[dict]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        if rows:
            writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        else:
            fh.write("")
    return path


def _panel(n: int = 3) -> list[dict]:
    return [
        {"entity": f"C{i:02d}", "time": str(2000 + i), "value": str(i)}
        for i in range(n)
    ]


# ---------------------------------------------------------------------------
# ValidationIssue
# ---------------------------------------------------------------------------

class TestValidationIssue:
    def test_has_required_fields(self) -> None:
        issue = DataValidationIssue(code="V-01", check="required_columns",
                                    level="error", message="Missing columns")
        assert issue.code == "V-01"
        assert issue.level == "error"
        assert issue.detail == ""

    def test_detail_optional(self) -> None:
        issue = DataValidationIssue(code="V-01", check="c", level="error",
                                    message="m", detail="details here")
        assert issue.detail == "details here"

    def test_alias_is_data_validation_issue(self) -> None:
        """Deprecated alias ValidationIssue resolves to DataValidationIssue."""
        assert ValidationIssue is DataValidationIssue

    def test_ingestion_package_exports_new_name(self) -> None:
        """DataValidationIssue is accessible from econflow.ingestion."""
        from econflow.ingestion import DataValidationIssue as DVI
        assert DVI is DataValidationIssue

    def test_alias_still_importable_from_ingestion_package(self) -> None:
        """Old import path econflow.ingestion.ValidationIssue still works."""
        from econflow.ingestion import ValidationIssue as VI
        assert VI is DataValidationIssue


# ---------------------------------------------------------------------------
# DataValidationReport
# ---------------------------------------------------------------------------

class TestDataValidationReport:
    def _report(self) -> DataValidationReport:
        return DataValidationReport(path="/f.csv", row_count=10, col_count=3,
                                    columns=["a", "b", "c"])

    def test_has_errors_false_initially(self) -> None:
        assert not self._report().has_errors

    def test_add_error_sets_has_errors(self) -> None:
        r = self._report()
        r.add_error("V-01", "required_columns", "Missing col")
        assert r.has_errors

    def test_add_warning_does_not_set_has_errors(self) -> None:
        r = self._report()
        r.add_warning("V-02", "duplicates", "Dup rows")
        assert not r.has_errors

    def test_to_dict_has_expected_keys(self) -> None:
        d = self._report().to_dict()
        for key in ("path", "row_count", "col_count", "columns", "issues"):
            assert key in d

    def test_to_json_round_trips(self) -> None:
        import json
        r = self._report()
        r.add_warning("V-02", "dup", "w")
        j = r.to_json()
        d = json.loads(j)
        assert d["row_count"] == 10
        assert len(d["issues"]) == 1


# ---------------------------------------------------------------------------
# DataValidationConfig defaults
# ---------------------------------------------------------------------------

class TestDataValidationConfig:
    def test_default_entity_col(self) -> None:
        c = DataValidationConfig()
        assert c.entity_col == "entity"

    def test_default_time_col(self) -> None:
        c = DataValidationConfig()
        assert c.time_col == "time"

    def test_default_check_duplicates_true(self) -> None:
        assert DataValidationConfig().check_duplicates

    def test_default_check_missing_identifiers_true(self) -> None:
        assert DataValidationConfig().check_missing_identifiers

    def test_default_check_missing_years_false(self) -> None:
        assert not DataValidationConfig().check_missing_years


# ---------------------------------------------------------------------------
# DataValidator checks
# ---------------------------------------------------------------------------

class TestDataValidatorV00FileExists:
    def test_missing_file_produces_error(self, tmp_path: Path) -> None:
        report = DataValidator().validate_path(tmp_path / "nonexistent.csv")
        assert report.has_errors
        assert any(i.code == "V-00" for i in report.issues)

    def test_existing_file_no_v00_error(self, tmp_path: Path) -> None:
        p = _write_csv(tmp_path / "f.csv", _panel())
        report = DataValidator().validate_path(p)
        assert not any(i.code == "V-00" for i in report.issues)


class TestDataValidatorV01RequiredColumns:
    def test_missing_required_column_produces_error(self, tmp_path: Path) -> None:
        rows = [{"entity": "A", "time": "2000"}]  # missing "value"
        p = _write_csv(tmp_path / "f.csv", rows)
        config = DataValidationConfig(required_columns=["entity", "time", "value"])
        report = DataValidator(config).validate_path(p)
        assert any(i.code == "V-01" for i in report.issues)

    def test_all_required_columns_present_no_v01(self, tmp_path: Path) -> None:
        p = _write_csv(tmp_path / "f.csv", _panel())
        config = DataValidationConfig(required_columns=["entity", "time"])
        report = DataValidator(config).validate_path(p)
        assert not any(i.code == "V-01" for i in report.issues)


class TestDataValidatorV02Duplicates:
    def test_duplicate_rows_produce_warning(self, tmp_path: Path) -> None:
        rows = [
            {"entity": "A", "time": "2000", "value": "1"},
            {"entity": "A", "time": "2000", "value": "1"},
        ]
        p = _write_csv(tmp_path / "f.csv", rows)
        config = DataValidationConfig(check_duplicates=True,
                                      entity_col="entity", time_col="time")
        report = DataValidator(config).validate_path(p)
        assert any(i.code == "V-02" for i in report.issues)

    def test_no_duplicates_no_v02(self, tmp_path: Path) -> None:
        p = _write_csv(tmp_path / "f.csv", _panel())
        config = DataValidationConfig(check_duplicates=True,
                                      entity_col="entity", time_col="time")
        report = DataValidator(config).validate_path(p)
        assert not any(i.code == "V-02" for i in report.issues)

    def test_check_duplicates_false_skips(self, tmp_path: Path) -> None:
        rows = [
            {"entity": "A", "time": "2000", "value": "1"},
            {"entity": "A", "time": "2000", "value": "1"},
        ]
        p = _write_csv(tmp_path / "f.csv", rows)
        config = DataValidationConfig(check_duplicates=False,
                                      entity_col="entity", time_col="time")
        report = DataValidator(config).validate_path(p)
        assert not any(i.code == "V-02" for i in report.issues)


class TestDataValidatorV03MissingIdentifiers:
    def test_blank_entity_col_produces_warning(self, tmp_path: Path) -> None:
        rows = [{"entity": "", "time": "2000", "value": "1"}]
        p = _write_csv(tmp_path / "f.csv", rows)
        config = DataValidationConfig(check_missing_identifiers=True,
                                      entity_col="entity", time_col="time")
        report = DataValidator(config).validate_path(p)
        assert any(i.code == "V-03" for i in report.issues)

    def test_no_blank_identifiers_no_v03(self, tmp_path: Path) -> None:
        p = _write_csv(tmp_path / "f.csv", _panel())
        config = DataValidationConfig(check_missing_identifiers=True,
                                      entity_col="entity", time_col="time")
        report = DataValidator(config).validate_path(p)
        assert not any(i.code == "V-03" for i in report.issues)


class TestDataValidatorV06MissingPct:
    def test_high_missing_pct_in_column_produces_warning(self, tmp_path: Path) -> None:
        rows = [{"entity": f"C{i}", "time": str(i), "value": ""} for i in range(10)]
        p = _write_csv(tmp_path / "f.csv", rows)
        config = DataValidationConfig(max_missing_pct=0.5)
        report = DataValidator(config).validate_path(p)
        assert any(i.code == "V-06" for i in report.issues)

    def test_no_missing_values_no_v06(self, tmp_path: Path) -> None:
        p = _write_csv(tmp_path / "f.csv", _panel())
        config = DataValidationConfig(max_missing_pct=1.0)
        report = DataValidator(config).validate_path(p)
        assert not any(i.code == "V-06" for i in report.issues)


class TestDataValidatorValidateDataframe:
    def test_validate_dataframe_happy_path(self) -> None:
        import pandas as pd
        df = pd.DataFrame({"entity": ["A", "B"], "time": [2000, 2001], "v": [1.0, 2.0]})
        report = DataValidator().validate_dataframe(df)
        assert isinstance(report, DataValidationReport)
        assert report.row_count == 2

    def test_validate_dataframe_detects_missing_required_col(self) -> None:
        import pandas as pd
        df = pd.DataFrame({"entity": ["A"], "time": [2000]})
        config = DataValidationConfig(required_columns=["entity", "time", "value"])
        report = DataValidator(config).validate_dataframe(df)
        assert any(i.code == "V-01" for i in report.issues)
