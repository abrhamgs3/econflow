"""
econflow.integrity.certificate — ReproducibilityCertificate.

A certificate is a signed record of the exact software environment, input
data fingerprints, configuration file fingerprint, and integrity check
results captured at a specific pipeline run.  Certificates are serialised
as JSON and are suitable for archival alongside publication outputs.

Schema version
--------------
The ``schema_version`` field follows semver.  Minor increments add optional
keys; major increments change or remove existing keys.  Current: ``"1.0.0"``.

Usage
-----
::

    from econflow.integrity.certificate import ReproducibilityCertificate
    from econflow.integrity.fingerprint import (
        EnvironmentFingerprint, DataFingerprint, ConfigFingerprint,
    )

    cert = ReproducibilityCertificate.build(
        project_name="My Study",
        data_paths=["data/processed/panel.csv"],
        config_path="config/config.yaml",
    )
    cert.save("outputs/certificate.json")

    # later:
    cert2 = ReproducibilityCertificate.load("outputs/certificate.json")
"""

from __future__ import annotations

import json
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from econflow.core.exceptions import CertificateError
from econflow.integrity.checks.base import IntegrityCheckResult
from econflow.integrity.fingerprint import (
    ConfigFingerprint,
    DataFingerprint,
    EnvironmentFingerprint,
)

CERTIFICATE_SCHEMA_VERSION: str = "1.0.0"

# Status precedence (highest first)
_STATUS_RANK: dict[str, int] = {"fail": 2, "warn": 1, "pass": 0, "skip": 0}


def _aggregate_status(results: list[IntegrityCheckResult]) -> str:
    """Return the worst status across *results*."""
    if not results:
        return "pass"
    rank = max(_STATUS_RANK.get(r.status, 0) for r in results)
    for status, r in _STATUS_RANK.items():
        if r == rank:
            return status
    return "pass"


# ---------------------------------------------------------------------------
# ReproducibilityCertificate
# ---------------------------------------------------------------------------


@dataclass
class ReproducibilityCertificate:
    """
    Comprehensive reproducibility record for a single pipeline run.

    Parameters
    ----------
    certificate_id:
        UUID4 string — unique per certificate.
    schema_version:
        Semver string of the certificate format.
    created_utc:
        ISO-8601 UTC creation timestamp.
    project_name:
        Human-readable project identifier.
    econflow_version:
        EconFlow version at creation time.
    environment:
        :class:`~econflow.integrity.fingerprint.EnvironmentFingerprint`.
    data:
        List of :class:`~econflow.integrity.fingerprint.DataFingerprint`
        objects, one per input dataset.
    config:
        :class:`~econflow.integrity.fingerprint.ConfigFingerprint`, or
        ``None`` when no config path was supplied.
    check_results:
        List of :class:`~econflow.integrity.checks.base.IntegrityCheckResult`
        objects from all integrity checks run.
    overall_status:
        Aggregate status: ``"pass"``, ``"warn"``, or ``"fail"``.
    provenance_run_id:
        Optional link to the :class:`~econflow.provenance.ProvenanceRecorder`
        ``run_id`` for the same pipeline execution.
    notes:
        Free-text annotation.
    """

    certificate_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    schema_version: str = CERTIFICATE_SCHEMA_VERSION
    created_utc: str = field(
        default_factory=lambda: datetime.now(tz=timezone.utc).isoformat()
    )
    project_name: str = ""
    econflow_version: str = ""
    environment: EnvironmentFingerprint = field(
        default_factory=EnvironmentFingerprint
    )
    data: list[DataFingerprint] = field(default_factory=list)
    config: ConfigFingerprint | None = None
    check_results: list[IntegrityCheckResult] = field(default_factory=list)
    overall_status: str = "pass"
    provenance_run_id: str = ""
    notes: str = ""

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def build(
        cls,
        *,
        project_name: str = "",
        data_paths: list[str | Path] | None = None,
        config_path: str | Path | None = None,
        check_results: list[IntegrityCheckResult] | None = None,
        repo_root: str | Path | None = None,
        provenance_run_id: str = "",
        notes: str = "",
    ) -> ReproducibilityCertificate:
        """
        Capture the current environment and build a certificate.

        Parameters
        ----------
        project_name:
            Human-readable name for the project.
        data_paths:
            Paths to input datasets.  Each path is fingerprinted.
        config_path:
            Path to the project configuration YAML.
        check_results:
            Pre-computed integrity check results.  Pass an empty list or
            ``None`` to omit checks from the certificate.
        repo_root:
            ``git`` repository root.  Defaults to the current directory.
        provenance_run_id:
            Link to a :class:`~econflow.provenance.ProvenanceRecorder` run.
        notes:
            Free-text annotation.
        """
        import importlib.metadata as _meta

        try:
            ef_version = _meta.version("econflow")
        except _meta.PackageNotFoundError:
            ef_version = "unknown"

        env = EnvironmentFingerprint.capture(repo_root=repo_root)
        data_fps = [DataFingerprint.from_path(p) for p in (data_paths or [])]
        config_fp = ConfigFingerprint.from_path(config_path) if config_path else None
        results = list(check_results or [])
        status = _aggregate_status(results)

        return cls(
            project_name=project_name,
            econflow_version=ef_version,
            environment=env,
            data=data_fps,
            config=config_fp,
            check_results=results,
            overall_status=status,
            provenance_run_id=provenance_run_id,
            notes=notes,
        )

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        return {
            "certificate_id": self.certificate_id,
            "schema_version": self.schema_version,
            "created_utc": self.created_utc,
            "project_name": self.project_name,
            "econflow_version": self.econflow_version,
            "overall_status": self.overall_status,
            "provenance_run_id": self.provenance_run_id,
            "notes": self.notes,
            "environment": self.environment.to_dict(),
            "data": [d.to_dict() for d in self.data],
            "config": self.config.to_dict() if self.config else None,
            "check_results": [r.to_dict() for r in self.check_results],
        }

    def to_json(self, *, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ReproducibilityCertificate:
        config_raw = data.get("config")
        return cls(
            certificate_id=str(data.get("certificate_id", str(uuid.uuid4()))),
            schema_version=str(
                data.get("schema_version", CERTIFICATE_SCHEMA_VERSION)
            ),
            created_utc=str(data.get("created_utc", "")),
            project_name=str(data.get("project_name", "")),
            econflow_version=str(data.get("econflow_version", "")),
            overall_status=str(data.get("overall_status", "pass")),
            provenance_run_id=str(data.get("provenance_run_id", "")),
            notes=str(data.get("notes", "")),
            environment=EnvironmentFingerprint.from_dict(
                data.get("environment") or {}
            ),
            data=[
                DataFingerprint.from_dict(d) for d in (data.get("data") or [])
            ],
            config=(
                ConfigFingerprint.from_dict(config_raw)
                if config_raw is not None
                else None
            ),
            check_results=[
                IntegrityCheckResult.from_dict(r)
                for r in (data.get("check_results") or [])
            ],
        )

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save(self, path: str | Path) -> None:
        """
        Write the certificate to *path* as a JSON file.

        Raises
        ------
        CertificateError
            If the file cannot be written.
        """
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".tmp")
        try:
            with open(tmp, "w", encoding="utf-8") as fh:
                fh.write(self.to_json())
                fh.write("\n")
                fh.flush()
                os.fsync(fh.fileno())
            tmp.replace(p)
        except Exception as exc:
            try:
                tmp.unlink(missing_ok=True)
            except OSError:
                pass
            raise CertificateError(
                f"Could not write certificate to {p}: {exc}"
            ) from exc

    @classmethod
    def load(cls, path: str | Path) -> ReproducibilityCertificate:
        """
        Load a certificate from a JSON file.

        Raises
        ------
        CertificateError
            If the file cannot be read or parsed.
        """
        p = Path(path)
        try:
            raw = p.read_text(encoding="utf-8")
            data = json.loads(raw)
        except (OSError, json.JSONDecodeError) as exc:
            raise CertificateError(
                f"Could not load certificate from {p}: {exc}"
            ) from exc
        return cls.from_dict(data)

    # ------------------------------------------------------------------
    # Display
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        return (
            f"<ReproducibilityCertificate "
            f"id={self.certificate_id[:8]}... "
            f"project={self.project_name!r} "
            f"status={self.overall_status!r}>"
        )
