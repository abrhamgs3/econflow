"""
econflow.ingestion.manifest — Dataset manifest model.

A :class:`DatasetManifest` is a project-level registry of all datasets
that a pipeline run acquired.  It records the connector, parameters,
cache key, metadata, and validation outcome for each dataset, so that
the full data acquisition can be reproduced deterministically.

Manifests are written alongside :class:`~econflow.integrity.certificate.ReproducibilityCertificate`
files to form a complete reproducibility record.

Usage
-----
::

    from econflow.ingestion.manifest import DatasetManifest, ManifestEntry

    manifest = DatasetManifest(project="my_project")
    manifest.add_entry(
        connector_id="world_bank",
        cache_key="abc123",
        params={"indicators": ["IT.NET.USER.ZS"]},
        metadata=meta,
        validation_passed=True,
    )
    manifest.save(Path("outputs/manifest.json"))
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from econflow.ingestion.metadata import DatasetMetadata

MANIFEST_SCHEMA_VERSION = "1.0.0"


@dataclass
class ManifestEntry:
    """A single dataset entry in a :class:`DatasetManifest`."""

    connector_id: str
    cache_key: str
    params: dict[str, Any]
    metadata: dict[str, Any]
    validation_passed: bool
    validation_errors: int
    validation_warnings: int
    citation: str = ""
    dataset_version: str = "unknown"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ManifestEntry:
        return cls(
            connector_id=str(data.get("connector_id", "")),
            cache_key=str(data.get("cache_key", "")),
            params=dict(data.get("params", {})),
            metadata=dict(data.get("metadata", {})),
            validation_passed=bool(data.get("validation_passed", True)),
            validation_errors=int(data.get("validation_errors", 0)),
            validation_warnings=int(data.get("validation_warnings", 0)),
            citation=str(data.get("citation", "")),
            dataset_version=str(data.get("dataset_version", "unknown")),
        )


@dataclass
class DatasetManifest:
    """
    Project-level record of all datasets acquired during a pipeline run.

    Parameters
    ----------
    project:
        Human-readable project name.
    created_at:
        ISO-8601 UTC timestamp.  Auto-set if empty.
    schema_version:
        Manifest format version.
    entries:
        List of dataset entries.
    """

    project: str = ""
    created_at: str = ""
    schema_version: str = MANIFEST_SCHEMA_VERSION
    entries: list[ManifestEntry] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.created_at:
            self.created_at = datetime.now(tz=timezone.utc).isoformat()

    # ------------------------------------------------------------------
    # Mutators
    # ------------------------------------------------------------------

    def add_entry(
        self,
        *,
        connector_id: str,
        cache_key: str,
        params: dict[str, Any],
        metadata: DatasetMetadata,
        validation_passed: bool = True,
        validation_errors: int = 0,
        validation_warnings: int = 0,
        citation: str = "",
        dataset_version: str = "unknown",
    ) -> ManifestEntry:
        """
        Add a dataset to the manifest and return the created entry.

        Parameters
        ----------
        connector_id:
            Connector registry ID.
        cache_key:
            Deterministic cache key from the connector.
        params:
            Download parameters used.
        metadata:
            DatasetMetadata record from the connector.
        validation_passed:
            Whether validation found no errors.
        validation_errors:
            Count of validation errors.
        validation_warnings:
            Count of validation warnings.
        citation:
            Academic citation string for this dataset.
        dataset_version:
            Dataset version identifier.
        """
        entry = ManifestEntry(
            connector_id=connector_id,
            cache_key=cache_key,
            params=params,
            metadata=metadata.to_dict(),
            validation_passed=validation_passed,
            validation_errors=validation_errors,
            validation_warnings=validation_warnings,
            citation=citation,
            dataset_version=dataset_version,
        )
        self.entries.append(entry)
        return entry

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "project": self.project,
            "created_at": self.created_at,
            "n_datasets": len(self.entries),
            "entries": [e.to_dict() for e in self.entries],
        }

    def to_json(self, *, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DatasetManifest:
        obj = cls(
            project=str(data.get("project", "")),
            created_at=str(data.get("created_at", "")),
            schema_version=str(data.get("schema_version", MANIFEST_SCHEMA_VERSION)),
        )
        for e in data.get("entries", []):
            obj.entries.append(ManifestEntry.from_dict(e))
        return obj

    @classmethod
    def from_json(cls, text: str) -> DatasetManifest:
        return cls.from_dict(json.loads(text))

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save(self, path: Path | str) -> Path:
        """
        Atomically write the manifest to *path* as JSON.

        Parameters
        ----------
        path:
            Destination file path (created with parent dirs).

        Returns
        -------
        Path
            The resolved destination path.
        """
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(self.to_json(), encoding="utf-8")
        with tmp.open("rb") as fh:
            os.fsync(fh.fileno())
        tmp.replace(path)
        return path

    @classmethod
    def load(cls, path: Path | str) -> DatasetManifest:
        """Load a manifest from *path*."""
        return cls.from_json(Path(path).read_text(encoding="utf-8"))

    # ------------------------------------------------------------------
    # Summary helpers
    # ------------------------------------------------------------------

    @property
    def all_passed(self) -> bool:
        """True if every entry passed validation."""
        return all(e.validation_passed for e in self.entries)

    @property
    def total_errors(self) -> int:
        return sum(e.validation_errors for e in self.entries)

    @property
    def total_warnings(self) -> int:
        return sum(e.validation_warnings for e in self.entries)

    def citations(self) -> list[str]:
        """Return non-empty citation strings for all datasets."""
        return [e.citation for e in self.entries if e.citation]

    def __len__(self) -> int:
        return len(self.entries)

    def __repr__(self) -> str:
        return (
            f"<DatasetManifest project={self.project!r} "
            f"datasets={len(self.entries)} "
            f"all_passed={self.all_passed}>"
        )
