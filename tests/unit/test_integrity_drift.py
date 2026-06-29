"""
Unit tests for econflow.integrity.drift.

Covers DriftItem, DriftReport, detect_drift():
  - no-change case returns "pass"
  - git commit change detected as warn
  - package version change detected as warn
  - missing package detected as fail
  - data SHA change detected as fail
  - data row-count change detected as warn
  - config SHA change detected as warn
  - detect_drift accepts file paths
"""

from __future__ import annotations

import json

# ---------------------------------------------------------------------------
# Fixtures — minimal certificate dicts
# ---------------------------------------------------------------------------

def _cert(
    cert_id="cert-a",
    commit="abc123",
    dirty=False,
    packages=None,
    data_path="data.csv",
    data_sha="aaa",
    data_rows=100,
    config_sha="ccc",
):
    return {
        "certificate_id": cert_id,
        "environment": {
            "git": {"commit": commit, "branch": "main", "dirty": dirty, "tags": []},
            "python": {"version": "3.11.0"},
            "platform": {"system": "Linux"},
            "packages": packages or {"pandas": "2.0.0", "numpy": "1.24.0"},
            "econflow_version": "0.1.0",
        },
        "data": [
            {
                "path": data_path,
                "sha256": data_sha,
                "size_bytes": 1024,
                "row_count": data_rows,
                "column_count": 3,
                "columns": ["a", "b", "c"],
                "format": "csv",
            }
        ],
        "config": {"path": "config.yaml", "sha256": config_sha, "content_preview": None},
        "check_results": [],
        "overall_status": "pass",
    }


# ---------------------------------------------------------------------------
# DriftItem and DriftReport
# ---------------------------------------------------------------------------


class TestDriftItem:
    def test_to_dict_keys(self):
        from econflow.integrity.drift import DriftItem
        item = DriftItem(
            field="environment.git.commit",
            baseline_value="abc",
            current_value="def",
            severity="warn",
            message="commit changed",
        )
        d = item.to_dict()
        assert set(d.keys()) == {
            "field", "baseline_value", "current_value",
            "delta", "severity", "message",
        }

    def test_round_trip(self):
        from econflow.integrity.drift import DriftItem
        item = DriftItem(
            field="x", baseline_value=1, current_value=2,
            delta=1, severity="fail", message="changed",
        )
        item2 = DriftItem.from_dict(item.to_dict())
        assert item2.field == item.field
        assert item2.severity == item.severity


class TestDriftReport:
    def test_to_json_valid(self):
        from econflow.integrity.drift import DriftReport
        report = DriftReport(overall_status="pass")
        raw = report.to_json()
        parsed = json.loads(raw)
        assert parsed["overall_status"] == "pass"

    def test_save(self, tmp_path):
        from econflow.integrity.drift import DriftReport
        report = DriftReport(overall_status="warn")
        path = tmp_path / "report.json"
        report.save(path)
        assert path.exists()
        loaded = json.loads(path.read_text())
        assert loaded["overall_status"] == "warn"


# ---------------------------------------------------------------------------
# detect_drift — no change
# ---------------------------------------------------------------------------


class TestDetectDriftNoChange:
    def test_identical_certs_is_pass(self):
        from econflow.integrity.drift import detect_drift
        c = _cert()
        report = detect_drift(c, c)
        assert report.overall_status == "pass"
        # Only informational items (same new packages etc) allowed
        fail_items = [i for i in report.items if i.severity == "fail"]
        assert fail_items == []


# ---------------------------------------------------------------------------
# detect_drift — git changes
# ---------------------------------------------------------------------------


class TestDetectDriftGit:
    def test_commit_change_is_warn(self):
        from econflow.integrity.drift import detect_drift
        baseline = _cert(commit="abc123")
        current = _cert(commit="def456")
        report = detect_drift(baseline, current)
        commit_items = [
            i for i in report.items if "git.commit" in i.field
        ]
        assert len(commit_items) == 1
        assert commit_items[0].severity == "warn"

    def test_dirty_change_is_warn(self):
        from econflow.integrity.drift import detect_drift
        baseline = _cert(dirty=False)
        current = _cert(dirty=True)
        report = detect_drift(baseline, current)
        dirty_items = [i for i in report.items if "dirty" in i.field]
        assert len(dirty_items) == 1
        assert dirty_items[0].severity == "warn"


# ---------------------------------------------------------------------------
# detect_drift — package changes
# ---------------------------------------------------------------------------


class TestDetectDriftPackages:
    def test_version_change_is_warn(self):
        from econflow.integrity.drift import detect_drift
        baseline = _cert(packages={"pandas": "2.0.0"})
        current = _cert(packages={"pandas": "2.1.0"})
        report = detect_drift(baseline, current)
        pkg_items = [i for i in report.items if "pandas" in i.field]
        assert len(pkg_items) == 1
        assert pkg_items[0].severity == "warn"

    def test_missing_package_is_fail(self):
        from econflow.integrity.drift import detect_drift
        baseline = _cert(packages={"pandas": "2.0.0", "numpy": "1.24.0"})
        current = _cert(packages={"pandas": "2.0.0"})
        report = detect_drift(baseline, current)
        fail_items = [
            i for i in report.items
            if i.severity == "fail" and "numpy" in i.field
        ]
        assert len(fail_items) == 1

    def test_new_package_is_none_severity(self):
        from econflow.integrity.drift import detect_drift
        baseline = _cert(packages={"pandas": "2.0.0"})
        current = _cert(packages={"pandas": "2.0.0", "scipy": "1.10.0"})
        report = detect_drift(baseline, current)
        info_items = [
            i for i in report.items
            if i.severity == "none" and "scipy" in i.field
        ]
        assert len(info_items) == 1


# ---------------------------------------------------------------------------
# detect_drift — data changes
# ---------------------------------------------------------------------------


class TestDetectDriftData:
    def test_sha_change_is_fail(self):
        from econflow.integrity.drift import detect_drift
        baseline = _cert(data_sha="aaaa")
        current = _cert(data_sha="bbbb")
        report = detect_drift(baseline, current)
        fail_items = [i for i in report.items if i.severity == "fail"]
        assert len(fail_items) >= 1
        assert any("sha256" in i.field for i in fail_items)

    def test_row_count_change_is_warn(self):
        from econflow.integrity.drift import detect_drift
        baseline = _cert(data_sha="same", data_rows=100)
        current = _cert(data_sha="same", data_rows=110)
        report = detect_drift(baseline, current)
        warn_items = [
            i for i in report.items
            if i.severity == "warn" and "row_count" in i.field
        ]
        assert len(warn_items) == 1
        assert warn_items[0].delta == 10


# ---------------------------------------------------------------------------
# detect_drift — config changes
# ---------------------------------------------------------------------------


class TestDetectDriftConfig:
    def test_config_sha_change_is_warn(self):
        from econflow.integrity.drift import detect_drift
        baseline = _cert(config_sha="aaa")
        current = _cert(config_sha="bbb")
        report = detect_drift(baseline, current)
        warn_items = [
            i for i in report.items
            if i.severity == "warn" and "config" in i.field
        ]
        assert len(warn_items) >= 1


# ---------------------------------------------------------------------------
# detect_drift — file path inputs
# ---------------------------------------------------------------------------


class TestDetectDriftFilePaths:
    def test_accepts_json_paths(self, tmp_path):
        from econflow.integrity.drift import detect_drift
        base_path = tmp_path / "base.json"
        curr_path = tmp_path / "curr.json"
        base_path.write_text(json.dumps(_cert(commit="abc")))
        curr_path.write_text(json.dumps(_cert(commit="def")))
        report = detect_drift(base_path, curr_path)
        assert report.baseline_path == str(base_path)
        assert report.current_path == str(curr_path)
        commit_items = [i for i in report.items if "git.commit" in i.field]
        assert len(commit_items) == 1
