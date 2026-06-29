"""
Unit tests for econflow.integrity.certificate.

Covers ReproducibilityCertificate:
  - build() factory
  - to_dict / from_dict round-trip
  - save / load persistence
  - overall_status aggregation
  - CertificateError on bad path
"""

from __future__ import annotations

import json
import uuid

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _check_result(status: str = "pass", check_id: str = "test"):
    from econflow.integrity.checks.base import IntegrityCheckResult
    return IntegrityCheckResult(
        check_id=check_id,
        name=check_id.replace("_", " ").title(),
        status=status,
        message=f"{status} message",
    )


# ---------------------------------------------------------------------------
# Build and basic attributes
# ---------------------------------------------------------------------------


class TestReproducibilityCertificateBuild:
    def test_build_returns_instance(self):
        from econflow.integrity.certificate import ReproducibilityCertificate
        cert = ReproducibilityCertificate.build(project_name="Test")
        assert isinstance(cert, ReproducibilityCertificate)

    def test_certificate_id_is_uuid4(self):
        from econflow.integrity.certificate import ReproducibilityCertificate
        cert = ReproducibilityCertificate.build()
        parsed = uuid.UUID(cert.certificate_id)
        assert parsed.version == 4

    def test_schema_version(self):
        from econflow.integrity.certificate import (
            CERTIFICATE_SCHEMA_VERSION,
            ReproducibilityCertificate,
        )
        cert = ReproducibilityCertificate.build()
        assert cert.schema_version == CERTIFICATE_SCHEMA_VERSION

    def test_project_name_stored(self):
        from econflow.integrity.certificate import ReproducibilityCertificate
        cert = ReproducibilityCertificate.build(project_name="My Study")
        assert cert.project_name == "My Study"

    def test_data_fingerprints_empty_when_no_paths(self):
        from econflow.integrity.certificate import ReproducibilityCertificate
        cert = ReproducibilityCertificate.build()
        assert cert.data == []

    def test_data_fingerprints_created_for_paths(self, tmp_path):
        import csv

        from econflow.integrity.certificate import ReproducibilityCertificate
        f = tmp_path / "data.csv"
        with open(f, "w", newline="") as fh:
            csv.writer(fh).writerows([["x"], [1], [2]])
        cert = ReproducibilityCertificate.build(data_paths=[str(f)])
        assert len(cert.data) == 1
        assert cert.data[0].sha256 is not None

    def test_config_fingerprint_none_when_not_supplied(self):
        from econflow.integrity.certificate import ReproducibilityCertificate
        cert = ReproducibilityCertificate.build()
        assert cert.config is None

    def test_config_fingerprint_set_when_supplied(self, tmp_path):
        from econflow.integrity.certificate import ReproducibilityCertificate
        cfg = tmp_path / "config.yaml"
        cfg.write_text("project:\n  name: x\n")
        cert = ReproducibilityCertificate.build(config_path=str(cfg))
        assert cert.config is not None
        assert cert.config.sha256 is not None


# ---------------------------------------------------------------------------
# Overall status aggregation
# ---------------------------------------------------------------------------


class TestCertificateStatus:
    def test_no_checks_is_pass(self):
        from econflow.integrity.certificate import ReproducibilityCertificate
        cert = ReproducibilityCertificate.build(check_results=[])
        assert cert.overall_status == "pass"

    def test_all_pass_is_pass(self):
        from econflow.integrity.certificate import ReproducibilityCertificate
        results = [_check_result("pass"), _check_result("pass")]
        cert = ReproducibilityCertificate.build(check_results=results)
        assert cert.overall_status == "pass"

    def test_any_warn_is_warn(self):
        from econflow.integrity.certificate import ReproducibilityCertificate
        results = [_check_result("pass"), _check_result("warn")]
        cert = ReproducibilityCertificate.build(check_results=results)
        assert cert.overall_status == "warn"

    def test_any_fail_is_fail(self):
        from econflow.integrity.certificate import ReproducibilityCertificate
        results = [_check_result("warn"), _check_result("fail")]
        cert = ReproducibilityCertificate.build(check_results=results)
        assert cert.overall_status == "fail"

    def test_skip_does_not_raise_status(self):
        from econflow.integrity.certificate import ReproducibilityCertificate
        results = [_check_result("skip"), _check_result("pass")]
        cert = ReproducibilityCertificate.build(check_results=results)
        assert cert.overall_status == "pass"


# ---------------------------------------------------------------------------
# Serialisation round-trip
# ---------------------------------------------------------------------------


class TestCertificateSerialisation:
    def test_to_dict_has_required_keys(self):
        from econflow.integrity.certificate import ReproducibilityCertificate
        cert = ReproducibilityCertificate.build(project_name="X")
        d = cert.to_dict()
        required = {
            "certificate_id", "schema_version", "created_utc",
            "project_name", "econflow_version", "overall_status",
            "environment", "data", "config", "check_results",
        }
        assert required <= set(d.keys())

    def test_to_json_valid_json(self):
        from econflow.integrity.certificate import ReproducibilityCertificate
        cert = ReproducibilityCertificate.build()
        raw = cert.to_json()
        parsed = json.loads(raw)
        assert parsed["certificate_id"] == cert.certificate_id

    def test_from_dict_round_trip(self):
        from econflow.integrity.certificate import ReproducibilityCertificate
        cert = ReproducibilityCertificate.build(
            project_name="Round Trip",
            check_results=[_check_result("warn")],
        )
        d = cert.to_dict()
        cert2 = ReproducibilityCertificate.from_dict(d)
        assert cert2.certificate_id == cert.certificate_id
        assert cert2.project_name == cert.project_name
        assert cert2.overall_status == cert.overall_status
        assert len(cert2.check_results) == 1
        assert cert2.check_results[0].status == "warn"

    def test_from_dict_config_none(self):
        from econflow.integrity.certificate import ReproducibilityCertificate
        cert = ReproducibilityCertificate.build()
        d = cert.to_dict()
        assert d["config"] is None
        cert2 = ReproducibilityCertificate.from_dict(d)
        assert cert2.config is None


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------


class TestCertificatePersistence:
    def test_save_and_load(self, tmp_path):
        from econflow.integrity.certificate import ReproducibilityCertificate
        cert = ReproducibilityCertificate.build(project_name="Persist Test")
        path = tmp_path / "cert.json"
        cert.save(path)
        assert path.exists()
        cert2 = ReproducibilityCertificate.load(path)
        assert cert2.certificate_id == cert.certificate_id
        assert cert2.project_name == cert.project_name

    def test_save_creates_parent_dirs(self, tmp_path):
        from econflow.integrity.certificate import ReproducibilityCertificate
        cert = ReproducibilityCertificate.build()
        path = tmp_path / "deep" / "nested" / "cert.json"
        cert.save(path)
        assert path.exists()

    def test_load_invalid_json_raises(self, tmp_path):
        from econflow.core.exceptions import CertificateError
        from econflow.integrity.certificate import ReproducibilityCertificate
        path = tmp_path / "bad.json"
        path.write_text("not json {{{{")
        with pytest.raises(CertificateError):
            ReproducibilityCertificate.load(path)

    def test_load_missing_file_raises(self, tmp_path):
        from econflow.core.exceptions import CertificateError
        from econflow.integrity.certificate import ReproducibilityCertificate
        with pytest.raises(CertificateError):
            ReproducibilityCertificate.load(tmp_path / "missing.json")

    def test_repr(self):
        from econflow.integrity.certificate import ReproducibilityCertificate
        cert = ReproducibilityCertificate.build(project_name="X")
        r = repr(cert)
        assert "ReproducibilityCertificate" in r
        assert "X" in r
