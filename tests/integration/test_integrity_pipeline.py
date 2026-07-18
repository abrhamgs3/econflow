"""
Integration tests for the Research Integrity & Reproducibility Framework.

Pipeline: EstimationResult → run checks → build certificate → save/load
       → drift detection → replication package.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pandas as pd
import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_er(estimator_id: str = "ols", nobs: int = 100):
    from econflow.estimation.result import EstimationResult

    idx = pd.Index(["x1", "x2", "x3"])
    return EstimationResult(
        estimator_id=estimator_id,
        estimator_name=estimator_id.upper(),
        params=pd.Series([0.5, -0.2, 0.8], index=idx),
        std_err=pd.Series([0.1, 0.05, 0.15], index=idx),
        conf_int=pd.DataFrame(
            {"lower": [0.3, -0.3, 0.5], "upper": [0.7, -0.1, 1.1]}, index=idx
        ),
        pvalues=pd.Series([0.001, 0.04, 0.10], index=idx),
        nobs=nobs,
        ngroups=20,
        df_resid=nobs - 4,
        rsquared=0.65,
        rsquared_adj=0.63,
    )


def _write_csv(path: Path, rows: int = 50) -> Path:
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["id", "year", "y", "x1"])
        for i in range(rows):
            w.writerow([i % 10, 2000 + i // 10, i * 0.1, i * 0.5])
    return path


# ---------------------------------------------------------------------------
# Full pipeline: checks → certificate → save → load
# ---------------------------------------------------------------------------


class TestCertifyPipeline:
    def test_build_cert_with_checks(self, tmp_path):
        """Build a certificate with all 3 checks run on a real EstimationResult."""
        from econflow.integrity import ReproducibilityCertificate
        from econflow.integrity.checks import get_check, list_checks

        er = _make_er()
        check_results = []
        for meta in list_checks():
            if meta["status"] == "implemented":
                check = get_check(meta["id"])()
                check_results.append(check.run(er))

        assert len(check_results) == 3

        cert = ReproducibilityCertificate.build(
            project_name="Integration Test",
            check_results=check_results,
        )
        assert cert.overall_status in ("pass", "warn", "fail")
        assert len(cert.check_results) == 3

        # Save and reload
        path = tmp_path / "cert.json"
        cert.save(path)
        cert2 = ReproducibilityCertificate.load(path)
        assert cert2.certificate_id == cert.certificate_id
        assert cert2.overall_status == cert.overall_status
        assert len(cert2.check_results) == 3

    def test_cert_with_data_and_config(self, tmp_path):
        """Data fingerprint and config fingerprint round-trip through certificate."""
        from econflow.integrity import ReproducibilityCertificate

        data_file = _write_csv(tmp_path / "data.csv", rows=100)
        config_file = tmp_path / "config.yaml"
        config_file.write_text("project:\n  name: Test\n", encoding="utf-8")

        cert = ReproducibilityCertificate.build(
            project_name="Data + Config Test",
            data_paths=[str(data_file)],
            config_path=str(config_file),
        )

        assert len(cert.data) == 1
        assert cert.data[0].sha256 is not None
        assert cert.data[0].row_count == 100
        assert cert.config is not None
        assert cert.config.sha256 is not None

        path = tmp_path / "cert.json"
        cert.save(path)
        cert2 = ReproducibilityCertificate.load(path)
        assert cert2.data[0].sha256 == cert.data[0].sha256
        assert cert2.config.sha256 == cert.config.sha256


# ---------------------------------------------------------------------------
# Drift detection pipeline
# ---------------------------------------------------------------------------


class TestDriftPipeline:
    def test_same_cert_no_drift(self):
        """Two identical certificates produce a pass report."""
        from econflow.integrity import ReproducibilityCertificate, detect_drift

        cert = ReproducibilityCertificate.build(project_name="Same")
        report = detect_drift(cert.to_dict(), cert.to_dict())
        assert report.overall_status == "pass"

    def test_data_sha_drift_detected(self, tmp_path):
        """Changing file content between two certs produces a fail drift item."""
        from econflow.integrity import ReproducibilityCertificate, detect_drift

        data_v1 = _write_csv(tmp_path / "v1.csv", rows=50)
        data_v2 = _write_csv(tmp_path / "v2.csv", rows=60)
        # Same path in cert but different content (simulate same dataset changed)
        cert1 = ReproducibilityCertificate.build(data_paths=[str(data_v1)])
        cert2 = ReproducibilityCertificate.build(data_paths=[str(data_v2)])

        # Patch paths to be identical so drift compares them
        d1 = cert1.to_dict()
        d2 = cert2.to_dict()
        d1["data"][0]["path"] = "data/panel.csv"
        d2["data"][0]["path"] = "data/panel.csv"

        report = detect_drift(d1, d2)
        fail_items = [i for i in report.items if i.severity == "fail"]
        assert len(fail_items) >= 1

    def test_drift_report_saved_as_json(self, tmp_path):
        from econflow.integrity import ReproducibilityCertificate, detect_drift

        cert = ReproducibilityCertificate.build()
        d1 = cert.to_dict()
        d2 = cert.to_dict()
        d2["environment"]["git"]["commit"] = "newcommit"

        report = detect_drift(d1, d2)
        out = tmp_path / "drift.json"
        report.save(out)

        loaded = json.loads(out.read_text())
        assert "items" in loaded
        assert loaded["overall_status"] in ("pass", "warn", "fail")


# ---------------------------------------------------------------------------
# ReplicationPackage pipeline
# ---------------------------------------------------------------------------


class TestReplicationPackagePipeline:
    def test_build_minimal_package(self, tmp_path):
        """Package builds without certificate."""
        from econflow.integrity import ReplicationPackage

        pkg = ReplicationPackage(tmp_path / "pkg")
        manifest = pkg.build()

        assert (tmp_path / "pkg" / "README.md").exists()
        assert (tmp_path / "pkg" / "environment.txt").exists()
        assert (tmp_path / "pkg" / "manifest.json").exists()
        assert manifest["econflow_replication_package"] is True

    def test_build_full_package(self, tmp_path):
        """Package with certificate, config, and script."""
        from econflow.integrity import (
            ReplicationPackage,
            ReproducibilityCertificate,
        )

        cert = ReproducibilityCertificate.build(project_name="Full Package")

        config_file = tmp_path / "config.yaml"
        config_file.write_text("project:\n  name: Full Package\n")

        script_file = tmp_path / "run.py"
        script_file.write_text("# main script\nprint('hello')\n")

        pkg = (
            ReplicationPackage(tmp_path / "pkg")
            .set_certificate(cert)
            .add_config(config_file)
            .add_script(script_file, label="Step 1: Run pipeline")
            .set_data_readme("Data available on request.")
        )
        manifest = pkg.build()

        assert (tmp_path / "pkg" / "certificate.json").exists()
        assert (tmp_path / "pkg" / "config" / "config.yaml").exists()
        assert (tmp_path / "pkg" / "scripts" / "run.py").exists()
        assert len(manifest["configs"]) == 1
        assert len(manifest["scripts"]) == 1

        # README should mention the data note
        readme = (tmp_path / "pkg" / "README.md").read_text()
        assert "Data available on request" in readme

    def test_overwrite_false_raises(self, tmp_path):
        from econflow.integrity import ReplicationPackage

        out = tmp_path / "pkg"
        out.mkdir()
        with pytest.raises(FileExistsError):
            ReplicationPackage(out, overwrite=False).build()

    def test_environment_txt_has_packages(self, tmp_path):
        from econflow.integrity import (
            ReplicationPackage,
            ReproducibilityCertificate,
        )

        cert = ReproducibilityCertificate.build()
        pkg = ReplicationPackage(tmp_path / "pkg").set_certificate(cert)
        pkg.build()

        env_txt = (tmp_path / "pkg" / "environment.txt").read_text()
        # pandas should appear
        assert "pandas" in env_txt


# ---------------------------------------------------------------------------
# End-to-end: EstimationResult → certify → verify
# ---------------------------------------------------------------------------


class TestEndToEndCertifyVerify:
    def test_verify_identical_passes(self, tmp_path):
        """Verify returns pass when current == baseline."""
        from econflow.integrity import ReproducibilityCertificate, detect_drift

        cert = ReproducibilityCertificate.build(project_name="E2E")
        path = tmp_path / "cert.json"
        cert.save(path)

        # Load and compare against itself
        baseline = ReproducibilityCertificate.load(path)
        report = detect_drift(baseline.to_dict(), baseline.to_dict())
        assert report.overall_status == "pass"

    def test_checks_reflect_estimation_quality(self):
        """A tiny sample should produce a fail check result in the certificate."""
        from econflow.integrity import ReproducibilityCertificate
        from econflow.integrity.checks import get_check

        tiny_er = _make_er(nobs=3)
        check = get_check("sample_size")()
        result = check.run(tiny_er, warn_threshold=30, fail_threshold=10)
        assert result.status == "fail"

        cert = ReproducibilityCertificate.build(check_results=[result])
        assert cert.overall_status == "fail"
