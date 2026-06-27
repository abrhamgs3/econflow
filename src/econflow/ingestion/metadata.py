"""
econflow.ingestion.metadata — Dataset metadata model.

Every dataset downloaded through an EconFlow connector carries a
:class:`DatasetMetadata` record that captures provenance: where the data
came from, when it was fetched, what its content hash is, and how to cite it.

The record is stored alongside the cached CSV as ``<key>.meta.json``.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class DatasetMetadata:
    """
    Immutable provenance record for a single downloaded dataset.

    Parameters
    ----------
    connector_id:
        Short identifier of the connector that produced this dataset
        (e.g. ``"csv"``, ``"world_bank"``).
    source:
        Human-readable source name (e.g. ``"World Bank Open Data"``).
    download_date:
        ISO-8601 UTC timestamp of when the dataset was downloaded.
        Use :meth:`now` to create with the current time.
    url:
        Canonical URL or file path of the source data.
    version:
        Dataset version string, if available from the source API;
        otherwise ``"unknown"``.
    citation:
        How to cite this dataset in academic work.
    sha256_hash:
        Hex-encoded SHA-256 hash of the cached CSV file content.
        Empty string if not yet computed.
    row_count:
        Number of data rows (excluding header) in the CSV.
    col_count:
        Number of columns in the CSV.
    columns:
        Ordered list of column names.
    params:
        Connector-specific download parameters (indicators, countries,
        year range, etc.) used to produce this exact file.
    """

    connector_id: str
    source: str
    download_date: str
    url: str
    version: str
    citation: str
    sha256_hash: str
    row_count: int
    col_count: int
    columns: list[str] = field(default_factory=list)
    params: dict[str, Any] = field(default_factory=dict)

    # ------------------------------------------------------------------
    # Factory helpers
    # ------------------------------------------------------------------

    @classmethod
    def now(
        cls,
        *,
        connector_id: str,
        source: str,
        url: str,
        version: str = "unknown",
        citation: str = "",
        sha256_hash: str = "",
        row_count: int = 0,
        col_count: int = 0,
        columns: list[str] | None = None,
        params: dict[str, Any] | None = None,
    ) -> DatasetMetadata:
        """Create a metadata record stamped with the current UTC time."""
        return cls(
            connector_id=connector_id,
            source=source,
            download_date=datetime.now(tz=timezone.utc).isoformat(),
            url=url,
            version=version,
            citation=citation,
            sha256_hash=sha256_hash,
            row_count=row_count,
            col_count=col_count,
            columns=columns or [],
            params=params or {},
        )

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """Return a plain dict suitable for JSON serialization."""
        return asdict(self)

    def to_json(self, *, indent: int = 2) -> str:
        """Serialize to a JSON string."""
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DatasetMetadata:
        """Reconstruct from a plain dict (e.g. parsed from JSON)."""
        return cls(
            connector_id=data.get("connector_id", ""),
            source=data.get("source", ""),
            download_date=data.get("download_date", ""),
            url=data.get("url", ""),
            version=data.get("version", "unknown"),
            citation=data.get("citation", ""),
            sha256_hash=data.get("sha256_hash", ""),
            row_count=int(data.get("row_count", 0)),
            col_count=int(data.get("col_count", 0)),
            columns=list(data.get("columns", [])),
            params=dict(data.get("params", {})),
        )

    @classmethod
    def from_json(cls, text: str) -> DatasetMetadata:
        """Reconstruct from a JSON string."""
        return cls.from_dict(json.loads(text))

    # ------------------------------------------------------------------
    # Display
    # ------------------------------------------------------------------

    def __str__(self) -> str:
        return (
            f"DatasetMetadata("
            f"connector={self.connector_id!r}, "
            f"source={self.source!r}, "
            f"rows={self.row_count}, "
            f"cols={self.col_count}, "
            f"sha256={self.sha256_hash[:12]}...)"
        )
