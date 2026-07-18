"""
tests/unit/test_ingestion_cache.py — Unit tests for CacheManager.

Covers:
- data_path / meta_path resolve correctly
- is_cached() returns False before store, True after
- store() copies file to slot, populates row/col/sha256 in metadata
- retrieve() returns (path, metadata) with correct sha256
- verify_hash() passes on unmodified file, raises CacheCorruptionError on tampered
- invalidate() removes slot; returns True if existed, False if not
- clear() removes all slots and returns count
- list_cached() returns all slot keys
- compute_hash() matches sha256sum of file content
"""

from __future__ import annotations

import csv
import hashlib
from pathlib import Path

import pytest

from econflow.ingestion.cache import CacheCorruptionError, CacheManager
from econflow.ingestion.metadata import DatasetMetadata


def _make_meta(**kwargs) -> DatasetMetadata:
    defaults = dict(connector_id="test", source="Test", url="/test.csv")
    defaults.update(kwargs)
    return DatasetMetadata.now(**defaults)


def _write_csv(path: Path, rows: list[dict]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        if rows:
            writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    return path


class TestCacheManagerPaths:
    def test_data_path_is_under_cache_dir(self, tmp_path: Path) -> None:
        cm = CacheManager(tmp_path)
        assert cm.data_path("mykey").parent.parent == tmp_path

    def test_data_path_ends_with_data_csv(self, tmp_path: Path) -> None:
        cm = CacheManager(tmp_path)
        assert cm.data_path("mykey").name == "data.csv"

    def test_meta_path_ends_with_meta_json(self, tmp_path: Path) -> None:
        cm = CacheManager(tmp_path)
        assert cm.meta_path("mykey").name == "meta.json"

    def test_data_and_meta_in_same_slot_dir(self, tmp_path: Path) -> None:
        cm = CacheManager(tmp_path)
        assert cm.data_path("k").parent == cm.meta_path("k").parent


class TestIsCached:
    def test_false_before_store(self, tmp_path: Path) -> None:
        cm = CacheManager(tmp_path)
        assert not cm.is_cached("missing_key")

    def test_true_after_store(self, tmp_path: Path) -> None:
        cm = CacheManager(tmp_path)
        src = _write_csv(tmp_path / "src.csv", [{"a": 1, "b": 2}])
        cm.store("k1", src, _make_meta())
        assert cm.is_cached("k1")


class TestStore:
    def test_data_file_exists_after_store(self, tmp_path: Path) -> None:
        cm = CacheManager(tmp_path)
        src = _write_csv(tmp_path / "src.csv", [{"x": "1"}])
        cm.store("k", src, _make_meta())
        assert cm.data_path("k").exists()

    def test_meta_file_exists_after_store(self, tmp_path: Path) -> None:
        cm = CacheManager(tmp_path)
        src = _write_csv(tmp_path / "src.csv", [{"x": "1"}])
        cm.store("k", src, _make_meta())
        assert cm.meta_path("k").exists()

    def test_store_returns_data_path(self, tmp_path: Path) -> None:
        cm = CacheManager(tmp_path)
        src = _write_csv(tmp_path / "src.csv", [{"x": "1"}])
        result = cm.store("k", src, _make_meta())
        assert result == cm.data_path("k")

    def test_sha256_populated_in_metadata(self, tmp_path: Path) -> None:
        cm = CacheManager(tmp_path)
        src = _write_csv(tmp_path / "src.csv", [{"x": "1"}])
        cm.store("k", src, _make_meta())
        _, meta = cm.retrieve("k")
        assert len(meta.sha256_hash) == 64  # SHA-256 hex

    def test_row_count_populated(self, tmp_path: Path) -> None:
        cm = CacheManager(tmp_path)
        rows = [{"a": str(i)} for i in range(5)]
        src = _write_csv(tmp_path / "src.csv", rows)
        cm.store("k", src, _make_meta())
        _, meta = cm.retrieve("k")
        assert meta.row_count == 5

    def test_col_count_populated(self, tmp_path: Path) -> None:
        cm = CacheManager(tmp_path)
        src = _write_csv(tmp_path / "src.csv", [{"a": "1", "b": "2", "c": "3"}])
        cm.store("k", src, _make_meta())
        _, meta = cm.retrieve("k")
        assert meta.col_count == 3

    def test_columns_populated(self, tmp_path: Path) -> None:
        cm = CacheManager(tmp_path)
        src = _write_csv(tmp_path / "src.csv", [{"x": "1", "y": "2"}])
        cm.store("k", src, _make_meta())
        _, meta = cm.retrieve("k")
        assert "x" in meta.columns and "y" in meta.columns


class TestRetrieve:
    def test_returns_tuple_of_path_and_metadata(self, tmp_path: Path) -> None:
        cm = CacheManager(tmp_path)
        src = _write_csv(tmp_path / "src.csv", [{"a": "1"}])
        cm.store("k", src, _make_meta())
        result = cm.retrieve("k")
        assert isinstance(result, tuple) and len(result) == 2

    def test_raises_key_error_for_missing_slot(self, tmp_path: Path) -> None:
        cm = CacheManager(tmp_path)
        with pytest.raises(KeyError):
            cm.retrieve("nonexistent")

    def test_metadata_connector_id_preserved(self, tmp_path: Path) -> None:
        cm = CacheManager(tmp_path)
        src = _write_csv(tmp_path / "src.csv", [{"a": "1"}])
        cm.store("k", src, _make_meta(connector_id="world_bank"))
        _, meta = cm.retrieve("k")
        assert meta.connector_id == "world_bank"


class TestVerifyHash:
    def test_verify_passes_on_unmodified_file(self, tmp_path: Path) -> None:
        cm = CacheManager(tmp_path)
        src = _write_csv(tmp_path / "src.csv", [{"a": "1"}])
        cm.store("k", src, _make_meta())
        assert cm.verify_hash("k") is True

    def test_verify_raises_on_tampered_file(self, tmp_path: Path) -> None:
        cm = CacheManager(tmp_path)
        src = _write_csv(tmp_path / "src.csv", [{"a": "1"}])
        cm.store("k", src, _make_meta())
        # Tamper with the cached file
        cm.data_path("k").write_text("tampered content\n", encoding="utf-8")
        with pytest.raises(CacheCorruptionError):
            cm.verify_hash("k")


class TestInvalidate:
    def test_invalidate_existing_returns_true(self, tmp_path: Path) -> None:
        cm = CacheManager(tmp_path)
        src = _write_csv(tmp_path / "src.csv", [{"a": "1"}])
        cm.store("k", src, _make_meta())
        assert cm.invalidate("k") is True

    def test_invalidate_removes_slot(self, tmp_path: Path) -> None:
        cm = CacheManager(tmp_path)
        src = _write_csv(tmp_path / "src.csv", [{"a": "1"}])
        cm.store("k", src, _make_meta())
        cm.invalidate("k")
        assert not cm.is_cached("k")

    def test_invalidate_nonexistent_returns_false(self, tmp_path: Path) -> None:
        cm = CacheManager(tmp_path)
        assert cm.invalidate("nonexistent") is False


class TestClear:
    def test_clear_removes_all_slots(self, tmp_path: Path) -> None:
        cm = CacheManager(tmp_path)
        for i in range(3):
            src = _write_csv(tmp_path / f"src{i}.csv", [{"a": str(i)}])
            cm.store(f"k{i}", src, _make_meta())
        cm.clear()
        for i in range(3):
            assert not cm.is_cached(f"k{i}")

    def test_clear_returns_count(self, tmp_path: Path) -> None:
        cm = CacheManager(tmp_path)
        for i in range(3):
            src = _write_csv(tmp_path / f"src{i}.csv", [{"a": str(i)}])
            cm.store(f"k{i}", src, _make_meta())
        count = cm.clear()
        assert count == 3

    def test_clear_on_empty_returns_zero(self, tmp_path: Path) -> None:
        cm = CacheManager(tmp_path)
        assert cm.clear() == 0


class TestListCached:
    def test_empty_initially(self, tmp_path: Path) -> None:
        cm = CacheManager(tmp_path)
        assert cm.list_cached() == []

    def test_contains_stored_keys(self, tmp_path: Path) -> None:
        cm = CacheManager(tmp_path)
        for key in ("alpha", "beta"):
            src = _write_csv(tmp_path / f"{key}.csv", [{"a": "1"}])
            cm.store(key, src, _make_meta())
        cached = cm.list_cached()
        assert "alpha" in cached
        assert "beta" in cached

    def test_does_not_contain_invalidated_key(self, tmp_path: Path) -> None:
        cm = CacheManager(tmp_path)
        src = _write_csv(tmp_path / "s.csv", [{"a": "1"}])
        cm.store("gone", src, _make_meta())
        cm.invalidate("gone")
        assert "gone" not in cm.list_cached()


class TestComputeHash:
    def test_matches_manual_sha256(self, tmp_path: Path) -> None:
        p = tmp_path / "f.csv"
        p.write_bytes(b"hello,world\n1,2\n")
        expected = hashlib.sha256(b"hello,world\n1,2\n").hexdigest()
        assert CacheManager.compute_hash(p) == expected

    def test_hex_length_is_64(self, tmp_path: Path) -> None:
        p = tmp_path / "f.csv"
        p.write_bytes(b"a,b\n1,2\n")
        assert len(CacheManager.compute_hash(p)) == 64
