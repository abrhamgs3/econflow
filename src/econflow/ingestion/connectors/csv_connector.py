"""
econflow.ingestion.connectors.csv_connector -- Local CSV file connector.

The simplest connector: reads a CSV file that already exists on disk.
No network access required.  Useful for:

* Starting a new project with a hand-curated panel dataset.
* Switching from a remote connector to a locally-cached file.
* Testing pipeline code without network dependencies.

Usage
-----
::

    from econflow.ingestion.connectors import LocalCSVConnector
    from econflow.ingestion.cache import CacheManager

    cache = CacheManager(".cache/econflow")
    conn = LocalCSVConnector(
        params={"path": "data/raw/panel.csv", "encoding": "utf-8"},
        cache_manager=cache,
    )
    path, meta = conn.fetch()
    print(meta.row_count, meta.columns)
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from econflow.ingestion.base import AbstractConnector, ConnectorError
from econflow.ingestion.metadata import DatasetMetadata
from econflow.ingestion.registry import register
from econflow.ingestion.validation import DataValidationConfig, DataValidationReport, DataValidator


@register(
    "csv",
    label="Local CSV file",
    status="implemented",
    notes="Reads any UTF-8 panel CSV from the local filesystem",
)
class LocalCSVConnector(AbstractConnector):
    """
    Connector for local CSV files.

    Parameters (``params`` dict keys)
    -----------------------------------
    path : str
        Path to the source CSV file.  Required.
    encoding : str
        File encoding.  Defaults to ``"utf-8"``.
    citation : str
        Citation string included in metadata.  Defaults to empty.
    required_columns : list[str]
        Passed to the validator.  Defaults to ``[]``.
    entity_col : str
        Entity column name for validation.  Defaults to ``"entity"``.
    time_col : str
        Time column name for validation.  Defaults to ``"time"``.
    """

    def __init__(
        self,
        params: dict[str, Any] | None = None,
        cache_manager: Any | None = None,
    ) -> None:
        super().__init__(params, cache_manager)
        raw_path = self.params.get("path", "")
        if not raw_path:
            raise ConnectorError(
                "LocalCSVConnector requires 'path' in params.",
                connector_id="csv",
            )
        self._source_path = Path(str(raw_path))
        self._encoding = self.params.get("encoding", "utf-8")
        self._cached_meta: DatasetMetadata | None = None

    # ------------------------------------------------------------------
    # AbstractConnector interface
    # ------------------------------------------------------------------

    def connect(self) -> None:
        """Verify the source CSV file exists and is readable."""
        if not self._source_path.exists():
            raise ConnectorError(
                f"Source file not found: {self._source_path}",
                connector_id="csv",
            )
        if not self._source_path.is_file():
            raise ConnectorError(
                f"Path is not a file: {self._source_path}",
                connector_id="csv",
            )

    def download(self, *, force: bool = False) -> Path:
        """
        Copy the source CSV into the cache (or return the cached copy).

        Parameters
        ----------
        force:
            Re-copy even if a cached copy already exists.
        """
        key = self.cache_key()

        if self.cache_manager is not None:
            if not force and self.cache_manager.is_cached(key):
                path, meta = self.cache_manager.retrieve(key)
                self._cached_meta = meta
                return path

        # Ensure file is accessible
        self.connect()

        if self.cache_manager is not None:
            meta = DatasetMetadata.now(
                connector_id="csv",
                source="Local CSV file",
                url=str(self._source_path.resolve()),
                citation=str(self.params.get("citation", "")),
                params=self.params,
            )
            stored = self.cache_manager.store(key, self._source_path, meta)
            _, self._cached_meta = self.cache_manager.retrieve(key)
            return stored

        # No cache manager: return source path directly
        self._cached_meta = DatasetMetadata.now(
            connector_id="csv",
            source="Local CSV file",
            url=str(self._source_path.resolve()),
            citation=str(self.params.get("citation", "")),
            sha256_hash=self._compute_hash(self._source_path),
            params=self.params,
        )
        self._populate_counts(self._source_path)
        return self._source_path

    def validate(self, path: Path) -> DataValidationReport:
        """Run configurable validation checks on the CSV at *path*."""
        config = DataValidationConfig(
            required_columns=list(self.params.get("required_columns", [])),
            entity_col=str(self.params.get("entity_col", "entity")),
            time_col=str(self.params.get("time_col", "time")),
            check_duplicates=bool(self.params.get("check_duplicates", True)),
            check_missing_identifiers=bool(
                self.params.get("check_missing_identifiers", True)
            ),
            max_missing_pct=float(self.params.get("max_missing_pct", 1.0)),
        )
        return DataValidator(config).validate_path(path)

    def metadata(self) -> DatasetMetadata:
        """Return metadata for the most recently downloaded file."""
        if self._cached_meta is None:
            raise ConnectorError(
                "No metadata available. Call download() first.",
                connector_id="csv",
            )
        return self._cached_meta

    def cache_key(self) -> str:
        """
        Deterministic key based on the resolved absolute source path.

        Two connectors pointing to the same file produce the same key.
        """
        return self._make_cache_key(
            {"resolved_path": str(self._source_path.resolve())}
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_hash(path: Path) -> str:
        import hashlib
        h = hashlib.sha256()
        with path.open("rb") as fh:
            for chunk in iter(lambda: fh.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()

    def _populate_counts(self, path: Path) -> None:
        """Fill row_count/col_count/columns into self._cached_meta in-place."""
        if self._cached_meta is None:
            return
        import csv as _csv
        try:
            with path.open(encoding=self._encoding, newline="") as fh:
                reader = _csv.reader(fh)
                cols = next(reader, [])
                rows = sum(1 for _ in reader)
            self._cached_meta = DatasetMetadata.from_dict({
                **self._cached_meta.to_dict(),
                "row_count": rows,
                "col_count": len(cols),
                "columns": cols,
            })
        except Exception:
            pass
