"""
Unit tests for econflow.integrity.fingerprint.

Covers EnvironmentFingerprint, DataFingerprint, ConfigFingerprint:
  - capture / from_path factory methods
  - to_dict / from_dict round-trips
  - edge cases (missing files, unknown formats)
"""

from __future__ import annotations

import csv
from pathlib import Path

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_csv(path: Path, header: list[str], rows: list[list]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(header)
        w.writerows(rows)


# ---------------------------------------------------------------------------
# EnvironmentFingerprint
# ---------------------------------------------------------------------------


class TestEnvironmentFingerprint:
    def test_capture_returns_instance(self):
        from econflow.integrity.fingerprint import EnvironmentFingerprint
        fp = EnvironmentFingerprint.capture()
        assert isinstance(fp, EnvironmentFingerprint)

    def test_capture_python_version_populated(self):
        from econflow.integrity.fingerprint import EnvironmentFingerprint
        fp = EnvironmentFingerprint.capture()
        assert fp.python.get("version") is not None
        assert "." in fp.python["version"]

    def test_capture_platform_populated(self):
        from econflow.integrity.fingerprint import EnvironmentFingerprint
        fp = EnvironmentFingerprint.capture()
        assert fp.platform.get("system") is not None

    def test_capture_packages_dict(self):
        from econflow.integrity.fingerprint import EnvironmentFingerprint
        fp = EnvironmentFingerprint.capture()
        assert isinstance(fp.packages, dict)
        # pandas should be present in the test environment
        assert "pandas" in fp.packages

    def test_capture_econflow_version_string(self):
        from econflow.integrity.fingerprint import EnvironmentFingerprint
        fp = EnvironmentFingerprint.capture()
        assert isinstance(fp.econflow_version, str)

    def test_to_dict_keys(self):
        from econflow.integrity.fingerprint import EnvironmentFingerprint
        fp = EnvironmentFingerprint.capture()
        d = fp.to_dict()
        assert set(d.keys()) == {"git", "python", "platform", "packages", "econflow_version"}

    def test_round_trip(self):
        from econflow.integrity.fingerprint import EnvironmentFingerprint
        fp = EnvironmentFingerprint.capture()
        d = fp.to_dict()
        fp2 = EnvironmentFingerprint.from_dict(d)
        assert fp2.python == fp.python
        assert fp2.platform == fp.platform
        assert fp2.packages == fp.packages
        assert fp2.econflow_version == fp.econflow_version

    def test_from_dict_empty(self):
        from econflow.integrity.fingerprint import EnvironmentFingerprint
        fp = EnvironmentFingerprint.from_dict({})
        assert fp.packages == {}
        assert fp.econflow_version == ""


# ---------------------------------------------------------------------------
# DataFingerprint
# ---------------------------------------------------------------------------


class TestDataFingerprint:
    def test_from_csv_path(self, tmp_path):
        from econflow.integrity.fingerprint import DataFingerprint
        f = tmp_path / "data.csv"
        _write_csv(f, ["id", "value"], [[1, 10], [2, 20], [3, 30]])
        fp = DataFingerprint.from_path(f)
        assert fp.format == "csv"
        assert fp.sha256 is not None
        assert len(fp.sha256) == 64
        assert fp.row_count == 3
        assert fp.column_count == 2
        assert sorted(fp.columns) == ["id", "value"]

    def test_from_csv_columns_sorted(self, tmp_path):
        from econflow.integrity.fingerprint import DataFingerprint
        f = tmp_path / "data.csv"
        _write_csv(f, ["z_col", "a_col", "m_col"], [[1, 2, 3]])
        fp = DataFingerprint.from_path(f)
        assert fp.columns == sorted(fp.columns)

    def test_from_missing_path(self, tmp_path):
        from econflow.integrity.fingerprint import DataFingerprint
        fp = DataFingerprint.from_path(tmp_path / "nonexistent.csv")
        assert fp.sha256 is None
        assert fp.row_count is None
        assert fp.format == "csv"  # suffix-based

    def test_from_unknown_format(self, tmp_path):
        from econflow.integrity.fingerprint import DataFingerprint
        f = tmp_path / "data.xlsx"
        f.write_bytes(b"\x00\x01\x02")
        fp = DataFingerprint.from_path(f)
        assert fp.format == "unknown"
        assert fp.row_count is None

    def test_to_dict_keys(self, tmp_path):
        from econflow.integrity.fingerprint import DataFingerprint
        f = tmp_path / "data.csv"
        _write_csv(f, ["x"], [[1]])
        fp = DataFingerprint.from_path(f)
        d = fp.to_dict()
        expected = {"path", "sha256", "size_bytes", "mtime_utc",
                    "row_count", "column_count", "columns", "format"}
        assert set(d.keys()) == expected

    def test_round_trip(self, tmp_path):
        from econflow.integrity.fingerprint import DataFingerprint
        f = tmp_path / "data.csv"
        _write_csv(f, ["a", "b"], [[1, 2], [3, 4]])
        fp = DataFingerprint.from_path(f)
        d = fp.to_dict()
        fp2 = DataFingerprint.from_dict(d)
        assert fp2.sha256 == fp.sha256
        assert fp2.row_count == fp.row_count
        assert fp2.columns == fp.columns

    def test_from_dict_empty(self):
        from econflow.integrity.fingerprint import DataFingerprint
        fp = DataFingerprint.from_dict({})
        assert fp.path == ""
        assert fp.sha256 is None
        assert fp.columns == []

    def test_sha256_changes_on_content_change(self, tmp_path):
        from econflow.integrity.fingerprint import DataFingerprint
        f = tmp_path / "data.csv"
        _write_csv(f, ["x"], [[1]])
        fp1 = DataFingerprint.from_path(f)
        _write_csv(f, ["x"], [[999]])
        fp2 = DataFingerprint.from_path(f)
        assert fp1.sha256 != fp2.sha256


# ---------------------------------------------------------------------------
# ConfigFingerprint
# ---------------------------------------------------------------------------


class TestConfigFingerprint:
    def test_from_path(self, tmp_path):
        from econflow.integrity.fingerprint import ConfigFingerprint
        f = tmp_path / "config.yaml"
        f.write_text("project:\n  name: test\n", encoding="utf-8")
        fp = ConfigFingerprint.from_path(f)
        assert fp.sha256 is not None
        assert len(fp.sha256) == 64
        assert "name: test" in (fp.content_preview or "")

    def test_from_missing_path(self, tmp_path):
        from econflow.integrity.fingerprint import ConfigFingerprint
        fp = ConfigFingerprint.from_path(tmp_path / "missing.yaml")
        assert fp.sha256 is None
        assert fp.content_preview is None

    def test_preview_truncated_at_512(self, tmp_path):
        from econflow.integrity.fingerprint import ConfigFingerprint
        f = tmp_path / "config.yaml"
        f.write_text("x: " + "a" * 600, encoding="utf-8")
        fp = ConfigFingerprint.from_path(f)
        assert len(fp.content_preview) == 512

    def test_round_trip(self, tmp_path):
        from econflow.integrity.fingerprint import ConfigFingerprint
        f = tmp_path / "config.yaml"
        f.write_text("key: value\n", encoding="utf-8")
        fp = ConfigFingerprint.from_path(f)
        d = fp.to_dict()
        fp2 = ConfigFingerprint.from_dict(d)
        assert fp2.sha256 == fp.sha256
        assert fp2.content_preview == fp.content_preview

    def test_from_dict_empty(self):
        from econflow.integrity.fingerprint import ConfigFingerprint
        fp = ConfigFingerprint.from_dict({})
        assert fp.path == ""
        assert fp.sha256 is None
