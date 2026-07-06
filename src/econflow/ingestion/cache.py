"""
econflow.ingestion.cache -- Reproducible filesystem cache for downloaded datasets.

Design
------
Each cached dataset occupies two files under ``<cache_dir>/<key>/``:

* ``data.csv``    -- the downloaded CSV (UTF-8, with header row).
* ``meta.json``   -- the :class:`~econflow.ingestion.metadata.DatasetMetadata`
  record serialized as JSON.

Cache keys are deterministic hex strings derived from the connector ID and
download parameters (see :meth:`AbstractConnector._make_cache_key`).  This
guarantees that the same query always maps to the same cache slot.

Hash verification
-----------------
On :meth:`retrieve`, the SHA-256 hash of ``data.csv`` is verified against the
value stored in ``meta.json``.  A mismatch raises :class:`CacheCorruptionError`
so the caller can force a re-download rather than silently using corrupt data.

Usage
-----
::

    from econflow.ingestion.cache import CacheManager

    cache = CacheManager(".cache/econflow")

    # Store a downloaded file
    meta = DatasetMetadata.now(connector_id="csv", source="Local CSV", ...)
    stored_path = cache.store(key="abc123", source_path=Path("panel.csv"), metadata=meta)

    # Check and retrieve
    if cache.is_cached("abc123"):
        path, meta = cache.retrieve("abc123")
"""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

from econflow.ingestion.metadata import DatasetMetadata

# ---------------------------------------------------------------------------
# Exception
# ---------------------------------------------------------------------------

class CacheCorruptionError(Exception):
    """Raised when a cached file fails its hash verification check."""


# ---------------------------------------------------------------------------
# Cache manager
# ---------------------------------------------------------------------------

class CacheManager:
    """
    Filesystem cache for downloaded datasets.

    Parameters
    ----------
    cache_dir:
        Root directory.  Created on first write if it does not exist.
    """

    _DATA_FILENAME = "data.csv"
    _META_FILENAME = "meta.json"

    def __init__(self, cache_dir: str | Path) -> None:
        self.cache_dir = Path(cache_dir)

    # ------------------------------------------------------------------
    # Path helpers
    # ------------------------------------------------------------------

    def _slot_dir(self, key: str) -> Path:
        """Return the directory for cache slot *key*."""
        return self.cache_dir / key

    def data_path(self, key: str) -> Path:
        """Return the path to the cached CSV for *key*."""
        return self._slot_dir(key) / self._DATA_FILENAME

    def meta_path(self, key: str) -> Path:
        """Return the path to the metadata JSON for *key*."""
        return self._slot_dir(key) / self._META_FILENAME

    # ------------------------------------------------------------------
    # Inspection
    # ------------------------------------------------------------------

    def is_cached(self, key: str) -> bool:
        """Return True if both the data file and metadata file exist for *key*."""
        return self.data_path(key).exists() and self.meta_path(key).exists()

    def list_cached(self) -> list[str]:
        """Return a sorted list of all cache keys that have complete entries."""
        if not self.cache_dir.exists():
            return []
        return sorted(
            d.name
            for d in self.cache_dir.iterdir()
            if d.is_dir()
            and (d / self._DATA_FILENAME).exists()
            and (d / self._META_FILENAME).exists()
        )

    # ------------------------------------------------------------------
    # Hash utilities
    # ------------------------------------------------------------------

    @staticmethod
    def compute_hash(path: Path) -> str:
        """Return the hex-encoded SHA-256 hash of the file at *path*."""
        h = hashlib.sha256()
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()

    def verify_hash(self, key: str) -> bool:
        """
        Verify the cached data file against the hash stored in metadata.

        Returns
        -------
        bool
            True if the file hash matches; False if the metadata has no hash
            stored (considered unverified but not corrupt).

        Raises
        ------
        CacheCorruptionError
            If the file hash does not match the stored hash.
        FileNotFoundError
            If the cache slot does not exist.
        """
        data = self.data_path(key)
        meta_file = self.meta_path(key)
        if not data.exists() or not meta_file.exists():
            raise FileNotFoundError(f"Cache slot {key!r} is missing.")
        meta = DatasetMetadata.from_json(meta_file.read_text(encoding="utf-8"))
        if not meta.sha256_hash:
            return False  # hash not recorded; cannot verify
        actual = self.compute_hash(data)
        if actual != meta.sha256_hash:
            raise CacheCorruptionError(
                f"Cache corruption detected for key {key!r}: "
                f"expected SHA-256 {meta.sha256_hash[:12]}..., "
                f"got {actual[:12]}..."
            )
        return True

    # ------------------------------------------------------------------
    # Read / Write
    # ------------------------------------------------------------------

    def store(
        self,
        key: str,
        source_path: Path,
        metadata: DatasetMetadata,
    ) -> Path:
        """
        Copy *source_path* into the cache slot for *key*.

        The SHA-256 hash of the copied file is computed and stored in
        *metadata* (overwriting any previously set hash).

        Parameters
        ----------
        key:
            Cache key (from ``connector.cache_key()``).
        source_path:
            Local path to the file to cache.
        metadata:
            Metadata record; ``sha256_hash``, ``row_count``, and ``col_count``
            are populated automatically if not already set.

        Returns
        -------
        Path
            The path of the cached data file.
        """
        slot = self._slot_dir(key)
        slot.mkdir(parents=True, exist_ok=True)
        dest = slot / self._DATA_FILENAME
        shutil.copy2(source_path, dest)

        # Compute and store hash
        sha256 = self.compute_hash(dest)

        # Populate row/col counts if not already set
        row_count = metadata.row_count
        col_count = metadata.col_count
        columns = metadata.columns
        if row_count == 0 or col_count == 0:
            try:
                import csv as _csv
                with dest.open(encoding="utf-8", newline="") as fh:
                    reader = _csv.reader(fh)
                    columns = next(reader, [])
                    rows = sum(1 for _ in reader)
                row_count = rows
                col_count = len(columns)
            except Exception:
                pass

        # Rebuild metadata with populated fields (dataclass is mutable via from_dict)
        updated = DatasetMetadata.from_dict({
            **metadata.to_dict(),
            "sha256_hash": sha256,
            "row_count": row_count,
            "col_count": col_count,
            "columns": columns,
        })
        (slot / self._META_FILENAME).write_text(
            updated.to_json(), encoding="utf-8"
        )
        return dest

    def retrieve(self, key: str) -> tuple[Path, DatasetMetadata]:
        """
        Return the cached data path and metadata for *key*.

        Verifies the file hash before returning.

        Returns
        -------
        tuple[Path, DatasetMetadata]
            ``(path_to_csv, metadata)``.

        Raises
        ------
        KeyError
            If the cache slot does not exist.
        CacheCorruptionError
            If the stored hash does not match the file content.
        """
        if not self.is_cached(key):
            raise KeyError(f"Cache slot {key!r} not found.")
        try:
            self.verify_hash(key)
        except CacheCorruptionError:
            raise
        meta = DatasetMetadata.from_json(
            self.meta_path(key).read_text(encoding="utf-8")
        )
        return self.data_path(key), meta

    # ------------------------------------------------------------------
    # Invalidation
    # ------------------------------------------------------------------

    def invalidate(self, key: str) -> bool:
        """
        Delete the cache slot for *key*.

        Parameters
        ----------
        key:
            Cache key to remove.

        Returns
        -------
        bool
            True if the slot existed and was deleted; False if it did not exist.
        """
        slot = self._slot_dir(key)
        if slot.exists():
            shutil.rmtree(slot)
            return True
        return False

    def clear(self) -> int:
        """
        Delete all cached datasets.

        Returns
        -------
        int
            Number of cache slots removed.
        """
        if not self.cache_dir.exists():
            return 0
        count = 0
        for slot in list(self.cache_dir.iterdir()):
            if slot.is_dir():
                shutil.rmtree(slot)
                count += 1
        return count
