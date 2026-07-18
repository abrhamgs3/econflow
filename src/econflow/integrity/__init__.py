"""
econflow.integrity — Research Integrity & Reproducibility Framework.

This sub-package provides four capabilities:

1. **Fingerprinting** — environment, data, and config snapshots.
2. **Certificates** — serialisable records of a full pipeline run.
3. **Drift detection** — compare two certificates to find changes.
4. **Integrity checks** — post-estimation signal-quality plugins.
5. **Replication packages** — journal-ready archival bundles.

Quick start::

    from econflow.integrity import (
        ReproducibilityCertificate,
        ReplicationPackage,
        detect_drift,
        get_check,
        list_checks,
    )

    cert = ReproducibilityCertificate.build(
        project_name="My Study",
        data_paths=["data/processed/panel.csv"],
        config_path="config/config.yaml",
    )
    cert.save("outputs/certificate.json")
"""

from econflow.integrity.certificate import (
    CERTIFICATE_SCHEMA_VERSION,
    ReproducibilityCertificate,
)
from econflow.integrity.checks import (
    BaseIntegrityCheck,
    IntegrityCheckResult,
    get_check,
    list_checks,
    register_integrity_check,
    unregister_check,
    unregister_integrity_check,
)
from econflow.integrity.drift import DriftItem, DriftReport, detect_drift
from econflow.integrity.fingerprint import (
    ConfigFingerprint,
    DataFingerprint,
    EnvironmentFingerprint,
)
from econflow.integrity.package import ReplicationPackage

__all__ = [
    # certificate
    "CERTIFICATE_SCHEMA_VERSION",
    "ReproducibilityCertificate",
    # checks
    "BaseIntegrityCheck",
    "IntegrityCheckResult",
    "get_check",
    "list_checks",
    "register_integrity_check",
    "unregister_integrity_check",
    # Deprecated alias kept for backward compat
    "unregister_check",
    # drift
    "DriftItem",
    "DriftReport",
    "detect_drift",
    # fingerprint
    "ConfigFingerprint",
    "DataFingerprint",
    "EnvironmentFingerprint",
    # package
    "ReplicationPackage",
]
