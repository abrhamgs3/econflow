"""
econflow.integrity.fingerprint — Environment, data, and config fingerprinting.

Three lightweight dataclasses, each capturing a different kind of
reproducibility evidence:

:class:`EnvironmentFingerprint`
    Captures the software stack: git commit, Python version, OS, and
    installed package versions.  Delegates to existing helpers in
    :mod:`econflow.provenance` so there is no duplication.

:class:`DataFingerprint`
    Captures the identity of an input dataset: path, SHA-256, file size,
    row/column counts, and column names.  Reads CSV or Parquet natively;
    falls back to file-level metadata for unknown formats.

:class:`ConfigFingerprint`
    Captures the identity of a YAML configuration file: path, SHA-256,
    and a 512-character content preview.
"""

from __future__ import annotations

import importlib.metadata as _meta
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Re-use low-level helpers from provenance so there is no duplication.
from econflow.provenance import (
    _git_info,
    _package_versions,
    _platform_info,
    _python_info,
    _sha256_file,
)

# ---------------------------------------------------------------------------
# EnvironmentFingerprint
# ---------------------------------------------------------------------------


@dataclass
class EnvironmentFingerprint:
    """
    Software-stack snapshot captured at certificate creation time.

    Parameters
    ----------
    git:
        Dict with keys ``commit``, ``branch``, ``dirty``, ``tags``.
    python:
        Dict with keys ``version``, ``implementation``, ``executable``.
    platform:
        Dict with keys ``system``, ``release``, ``machine``, ``node_hash``.
    packages:
        Mapping of package name → installed version (``None`` if absent).
    econflow_version:
        The installed EconFlow version string.
    """

    git: dict[str, Any] = field(default_factory=dict)
    python: dict[str, Any] = field(default_factory=dict)
    platform: dict[str, Any] = field(default_factory=dict)
    packages: dict[str, str | None] = field(default_factory=dict)
    econflow_version: str = ""

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def capture(cls, *, repo_root: str | Path | None = None) -> EnvironmentFingerprint:
        """
        Capture the current environment and return a fingerprint.

        Parameters
        ----------
        repo_root:
            Directory containing the ``.git`` folder.  Defaults to CWD.
        """
        try:
            ef_version = _meta.version("econflow")
        except _meta.PackageNotFoundError:
            ef_version = "unknown"

        return cls(
            git=_git_info(Path(repo_root) if repo_root else None),
            python=_python_info(),
            platform=_platform_info(),
            packages=_package_versions(),
            econflow_version=ef_version,
        )

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        return {
            "git": self.git,
            "python": self.python,
            "platform": self.platform,
            "packages": self.packages,
            "econflow_version": self.econflow_version,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EnvironmentFingerprint:
        return cls(
            git=dict(data.get("git") or {}),
            python=dict(data.get("python") or {}),
            platform=dict(data.get("platform") or {}),
            packages=dict(data.get("packages") or {}),
            econflow_version=str(data.get("econflow_version", "")),
        )


# ---------------------------------------------------------------------------
# DataFingerprint
# ---------------------------------------------------------------------------


def _count_csv_rows_cols(path: Path) -> tuple[int | None, int | None, list[str]]:
    """Return (row_count, col_count, column_names) for a CSV file."""
    try:
        import csv

        with open(path, newline="", encoding="utf-8", errors="replace") as fh:
            reader = csv.reader(fh)
            header = next(reader, None)
            if header is None:
                return 0, 0, []
            columns = [c.strip() for c in header]
            row_count = sum(1 for _ in reader)
        return row_count, len(columns), columns
    except Exception:
        return None, None, []


def _count_parquet_rows_cols(path: Path) -> tuple[int | None, int | None, list[str]]:
    """Return (row_count, col_count, column_names) for a Parquet file."""
    try:
        import pyarrow.parquet as pq

        pf = pq.ParquetFile(path)
        schema = pf.schema_arrow
        columns = schema.names
        row_count = pf.metadata.num_rows
        return row_count, len(columns), list(columns)
    except Exception:
        return None, None, []


@dataclass
class DataFingerprint:
    """
    Identity snapshot for a single input dataset.

    Parameters
    ----------
    path:
        Filesystem path as supplied by the caller.
    sha256:
        Hex SHA-256 digest of the file contents, or ``None`` if the file
        could not be read.
    size_bytes:
        File size in bytes, or ``None``.
    mtime_utc:
        ISO-8601 UTC modification time, or ``None``.
    row_count:
        Number of data rows (excluding the header for CSV), or ``None``.
    column_count:
        Number of columns, or ``None``.
    columns:
        Sorted list of column names (empty list if unavailable).
    format:
        Detected file format (``"csv"``, ``"parquet"``, ``"unknown"``).
    """

    path: str = ""
    sha256: str | None = None
    size_bytes: int | None = None
    mtime_utc: str | None = None
    row_count: int | None = None
    column_count: int | None = None
    columns: list[str] = field(default_factory=list)
    format: str = "unknown"

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def from_path(cls, path: str | Path) -> DataFingerprint:
        """
        Construct a fingerprint by inspecting *path* on disk.

        Supports CSV and Parquet natively; for other formats only file-level
        metadata (SHA-256, size, mtime) is recorded.
        """
        from datetime import datetime, timezone

        p = Path(path)
        sha = _sha256_file(p)

        size_bytes: int | None = None
        mtime_utc: str | None = None
        try:
            stat = p.stat()
            size_bytes = stat.st_size
            mtime_utc = datetime.fromtimestamp(
                stat.st_mtime, tz=timezone.utc
            ).isoformat()
        except OSError:
            pass

        suffix = p.suffix.lower()
        fmt: str
        row_count: int | None
        col_count: int | None
        columns: list[str]

        if suffix == ".csv":
            fmt = "csv"
            row_count, col_count, columns = _count_csv_rows_cols(p)
        elif suffix in (".parquet", ".pq"):
            fmt = "parquet"
            row_count, col_count, columns = _count_parquet_rows_cols(p)
        else:
            fmt = "unknown"
            row_count, col_count, columns = None, None, []

        return cls(
            path=str(p),
            sha256=sha,
            size_bytes=size_bytes,
            mtime_utc=mtime_utc,
            row_count=row_count,
            column_count=col_count,
            columns=sorted(columns),
            format=fmt,
        )

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "sha256": self.sha256,
            "size_bytes": self.size_bytes,
            "mtime_utc": self.mtime_utc,
            "row_count": self.row_count,
            "column_count": self.column_count,
            "columns": self.columns,
            "format": self.format,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DataFingerprint:
        return cls(
            path=str(data.get("path", "")),
            sha256=data.get("sha256"),
            size_bytes=data.get("size_bytes"),
            mtime_utc=data.get("mtime_utc"),
            row_count=data.get("row_count"),
            column_count=data.get("column_count"),
            columns=list(data.get("columns") or []),
            format=str(data.get("format", "unknown")),
        )


# ---------------------------------------------------------------------------
# ConfigFingerprint
# ---------------------------------------------------------------------------


@dataclass
class ConfigFingerprint:
    """
    Identity snapshot for a YAML configuration file.

    Parameters
    ----------
    path:
        Filesystem path as supplied by the caller.
    sha256:
        Hex SHA-256 digest, or ``None`` if the file could not be read.
    content_preview:
        First 512 characters of the file for quick visual inspection,
        or ``None`` if the file could not be read.
    """

    path: str = ""
    sha256: str | None = None
    content_preview: str | None = None

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def from_path(cls, path: str | Path) -> ConfigFingerprint:
        """Construct a fingerprint by reading *path* from disk."""
        p = Path(path)
        sha = _sha256_file(p)
        preview: str | None = None
        try:
            raw = p.read_text(encoding="utf-8", errors="replace")
            preview = raw[:512]
        except OSError:
            pass
        return cls(path=str(p), sha256=sha, content_preview=preview)

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "sha256": self.sha256,
            "content_preview": self.content_preview,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ConfigFingerprint:
        return cls(
            path=str(data.get("path", "")),
            sha256=data.get("sha256"),
            content_preview=data.get("content_preview"),
        )
