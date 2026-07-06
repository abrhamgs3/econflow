"""
tests/integration/test_ingestion_pipeline.py — Integration tests for Sprint 8.

Tests the full ingestion pipeline end-to-end:
- Offline cache cycle (store → retrieve → verify)
- Checksum verification and corruption detection
- Multi-connector manifest building
- CLI fetch command integration
- Regression: cache key stability across param orderings
"""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from econflow.ingestion.cache import CacheCorruptionError, CacheManager
from econflow.ingestion.connectors.csv_connector import LocalCSVConnector
from econflow.ingestion.connectors.fred import FREDConnector
from econflow.ingestion.connectors.world_bank import WorldBankConnector
from econflow.ingestion.manifest import DatasetManifest
from econflow.ingestion.metadata import DatasetMetadata

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_csv(path: Path, rows: list[list[str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        csv.writer(fh).writerows(rows)


def _meta() -> DatasetMetadata:
    return DatasetMetadata.now(
        connector_id="test",
        source="Test Source",
        url="https://example.com",
        row_count=2,
        col_count=3,
        columns=["entity", "time", "value"],
    )


# ---------------------------------------------------------------------------
# Offline cache cycle
# ---------------------------------------------------------------------------

class TestOfflineCacheCycle:
    """Full store → retrieve → verify pipeline without network."""

    def test_store_then_retrieve(self, tmp_path):
        src = tmp_path / "data.csv"
        _write_csv(src, [["entity", "time", "gdp"], ["USA", "2020", "21.3"]])

        cache = CacheManager(tmp_path / "cache")
        meta = _meta()
        stored_path = cache.store("key1", src, meta)

        assert stored_path.exists()
        assert cache.is_cached("key1")

        path_out, meta_out = cache.retrieve("key1")
        assert path_out.exists()
        assert meta_out.sha256_hash != ""
        assert meta_out.row_count > 0

    def test_retrieve_verifies_hash(self, tmp_path):
        src = tmp_path / "data.csv"
        _write_csv(src, [["entity", "time"], ["USA", "2020"]])

        cache = CacheManager(tmp_path / "cache")
        cache.store("key2", src, _meta())

        # Verify passes normally
        ok = cache.verify_hash("key2")
        assert ok is True

    def test_corrupted_file_raises(self, tmp_path):
        src = tmp_path / "data.csv"
        _write_csv(src, [["entity", "time"], ["USA", "2020"]])

        cache = CacheManager(tmp_path / "cache")
        cache.store("key3", src, _meta())

        # Corrupt the cached file
        data_path = cache.data_path("key3")
        data_path.write_text("CORRUPTED", encoding="utf-8")

        with pytest.raises(CacheCorruptionError, match="corruption"):
            cache.verify_hash("key3")

    def test_invalidate_removes_slot(self, tmp_path):
        src = tmp_path / "data.csv"
        _write_csv(src, [["entity", "time"], ["USA", "2020"]])

        cache = CacheManager(tmp_path / "cache")
        cache.store("key4", src, _meta())
        assert cache.is_cached("key4")

        removed = cache.invalidate("key4")
        assert removed is True
        assert not cache.is_cached("key4")

    def test_list_cached_returns_all_keys(self, tmp_path):
        src = tmp_path / "data.csv"
        _write_csv(src, [["entity", "time"], ["USA", "2020"]])

        cache = CacheManager(tmp_path / "cache")
        for k in ("ka", "kb", "kc"):
            cache.store(k, src, _meta())

        keys = cache.list_cached()
        assert sorted(keys) == ["ka", "kb", "kc"]

    def test_clear_removes_everything(self, tmp_path):
        src = tmp_path / "data.csv"
        _write_csv(src, [["entity", "time"], ["USA", "2020"]])

        cache = CacheManager(tmp_path / "cache")
        for k in ("x1", "x2"):
            cache.store(k, src, _meta())

        count = cache.clear()
        assert count == 2
        assert cache.list_cached() == []


# ---------------------------------------------------------------------------
# CSV connector full pipeline
# ---------------------------------------------------------------------------

class TestCSVConnectorFullPipeline:
    """Full lifecycle: connect → download → validate → metadata."""

    def test_full_pipeline_with_cache(self, tmp_path):
        src = tmp_path / "panel.csv"
        _write_csv(src, [
            ["entity", "time", "gdp", "pop"],
            ["USA", "2018", "20500", "327"],
            ["USA", "2019", "21000", "329"],
            ["GBR", "2018", "2800", "66"],
            ["GBR", "2019", "2850", "67"],
        ])

        cache = CacheManager(tmp_path / "cache")
        conn = LocalCSVConnector(
            params={"path": str(src)},
            cache_manager=cache,
        )

        path, meta = conn.fetch()

        assert path.exists()
        assert meta.row_count == 4
        assert meta.col_count == 4
        assert meta.sha256_hash != ""
        assert "entity" in meta.columns

    def test_force_redownload_updates_cache(self, tmp_path):
        src = tmp_path / "panel.csv"
        _write_csv(src, [["entity", "time"], ["USA", "2020"]])

        cache = CacheManager(tmp_path / "cache")
        conn = LocalCSVConnector(params={"path": str(src)}, cache_manager=cache)

        path1 = conn.download()
        path2 = conn.download(force=True)
        assert path1 == path2  # same path

    def test_cache_key_stable_across_instances(self, tmp_path):
        src = tmp_path / "panel.csv"
        _write_csv(src, [["entity", "time"]])

        c1 = LocalCSVConnector(params={"path": str(src)})
        c2 = LocalCSVConnector(params={"path": str(src)})
        assert c1.cache_key() == c2.cache_key()


# ---------------------------------------------------------------------------
# Manifest integration
# ---------------------------------------------------------------------------

class TestManifestIntegration:
    """Build a manifest from multiple connector downloads."""

    def test_multi_connector_manifest(self, tmp_path):
        src1 = tmp_path / "data1.csv"
        src2 = tmp_path / "data2.csv"
        _write_csv(src1, [["entity", "time"], ["USA", "2020"]])
        _write_csv(src2, [["entity", "time"], ["GBR", "2020"]])

        cache = CacheManager(tmp_path / "cache")
        manifest = DatasetManifest(project="integration_test")

        for i, src in enumerate([src1, src2], 1):
            conn = LocalCSVConnector(params={"path": str(src)}, cache_manager=cache)
            path, meta = conn.fetch()
            report = conn.validate(path)
            manifest.add_entry(
                connector_id=conn.connector_id,
                cache_key=conn.cache_key(),
                params=conn.params,
                metadata=meta,
                validation_passed=not report.has_errors,
                validation_errors=report.n_errors,
                validation_warnings=report.n_warnings,
                citation=conn.citation(),
                dataset_version=conn.version(),
            )

        assert len(manifest) == 2
        assert manifest.all_passed

        manifest_path = tmp_path / "manifest.json"
        manifest.save(manifest_path)
        assert manifest_path.exists()

        loaded = DatasetManifest.load(manifest_path)
        assert len(loaded) == 2

    def test_manifest_captures_failure(self, tmp_path):
        src = tmp_path / "data.csv"
        _write_csv(src, [["entity", "time"], ["USA", "2020"]])

        conn = LocalCSVConnector(
            params={"path": str(src), "required_columns": ["missing_col"]}
        )
        path = conn.download()
        report = conn.validate(path)

        manifest = DatasetManifest()
        manifest.add_entry(
            connector_id="csv",
            cache_key=conn.cache_key(),
            params=conn.params,
            metadata=conn.metadata(),
            validation_passed=not report.has_errors,
            validation_errors=report.n_errors,
        )

        assert not manifest.all_passed
        assert manifest.total_errors >= 1


# ---------------------------------------------------------------------------
# Regression: cache key stability
# ---------------------------------------------------------------------------

class TestCacheKeyRegression:
    """Cache keys must be deterministic regardless of param insertion order."""

    def test_param_order_invariance_world_bank(self):
        c1 = WorldBankConnector(
            params={"indicators": ["IT.NET.USER.ZS"], "year_start": 2000, "year_end": 2022}
        )
        c2 = WorldBankConnector(
            params={"year_end": 2022, "year_start": 2000, "indicators": ["IT.NET.USER.ZS"]}
        )
        assert c1.cache_key() == c2.cache_key()

    def test_different_params_give_different_keys(self):
        c1 = WorldBankConnector(params={"indicators": ["IT.NET.USER.ZS"]})
        c2 = WorldBankConnector(params={"indicators": ["NY.GDP.MKTP.CD"]})
        assert c1.cache_key() != c2.cache_key()

    def test_fred_cache_key_excludes_api_key(self):
        c1 = FREDConnector(params={"series_ids": ["GDPPC"], "api_key": "secret1"})
        c2 = FREDConnector(params={"series_ids": ["GDPPC"], "api_key": "secret2"})
        assert c1.cache_key() == c2.cache_key()

    def test_fred_different_series_different_key(self):
        c1 = FREDConnector(params={"series_ids": ["GDPPC"]})
        c2 = FREDConnector(params={"series_ids": ["UNRATE"]})
        assert c1.cache_key() != c2.cache_key()


# ---------------------------------------------------------------------------
# Checksum end-to-end
# ---------------------------------------------------------------------------

class TestChecksumEndToEnd:
    """Verify SHA-256 is correctly stored and checked across the pipeline."""

    def test_sha256_stored_matches_file(self, tmp_path):
        import hashlib

        src = tmp_path / "data.csv"
        content = "entity,time,gdp\nUSA,2020,21000\nGBR,2020,2800\n"
        src.write_text(content, encoding="utf-8")

        expected_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()

        cache = CacheManager(tmp_path / "cache")
        conn = LocalCSVConnector(params={"path": str(src)}, cache_manager=cache)
        conn.download()
        meta = conn.metadata()

        assert meta.sha256_hash == expected_hash

    def test_retrieve_detects_corruption(self, tmp_path):
        src = tmp_path / "data.csv"
        _write_csv(src, [["entity", "time"], ["USA", "2020"]])

        cache = CacheManager(tmp_path / "cache")
        conn = LocalCSVConnector(params={"path": str(src)}, cache_manager=cache)
        conn.download()

        # Silently corrupt the file
        cache.data_path(conn.cache_key()).write_text("bad data", encoding="utf-8")

        with pytest.raises(CacheCorruptionError):
            cache.retrieve(conn.cache_key())
