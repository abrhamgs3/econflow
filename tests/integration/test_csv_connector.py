"""
tests/integration/test_csv_connector.py — End-to-end tests for LocalCSVConnector.

These tests exercise the full fetch() pipeline:
  connect() → download() → validate() → metadata()

Also covers CacheManager integration (cache hit, cache miss, force refresh).
"""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from econflow.ingestion.cache import CacheManager
from econflow.ingestion.connectors.csv_connector import LocalCSVConnector

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def sample_csv(tmp_path: Path) -> Path:
    p = tmp_path / "panel.csv"
    rows = [
        {"country": "USA", "year": "2000", "gdp": "10000"},
        {"country": "DEU", "year": "2000", "gdp": "2000"},
        {"country": "USA", "year": "2001", "gdp": "10500"},
    ]
    with p.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=["country", "year", "gdp"])
        writer.writeheader()
        writer.writerows(rows)
    return p


# ---------------------------------------------------------------------------
# connect()
# ---------------------------------------------------------------------------

class TestLocalCSVConnectorConnect:
    def test_connect_succeeds_on_existing_file(self, sample_csv: Path) -> None:
        conn = LocalCSVConnector(params={"path": str(sample_csv)})
        conn.connect()  # should not raise

    def test_connect_raises_on_missing_file(self, tmp_path: Path) -> None:
        from econflow.ingestion.base import ConnectorError
        conn = LocalCSVConnector(params={"path": str(tmp_path / "missing.csv")})
        with pytest.raises(ConnectorError, match="not found"):
            conn.connect()

    def test_connect_raises_on_directory(self, tmp_path: Path) -> None:
        from econflow.ingestion.base import ConnectorError
        conn = LocalCSVConnector(params={"path": str(tmp_path)})
        with pytest.raises(ConnectorError):
            conn.connect()

    def test_constructor_raises_without_path_param(self) -> None:
        from econflow.ingestion.base import ConnectorError
        with pytest.raises(ConnectorError, match="path"):
            LocalCSVConnector(params={})


# ---------------------------------------------------------------------------
# download() without cache
# ---------------------------------------------------------------------------

class TestLocalCSVConnectorDownloadNoCache:
    def test_download_returns_path(self, sample_csv: Path) -> None:
        conn = LocalCSVConnector(params={"path": str(sample_csv)})
        conn.connect()
        path = conn.download()
        assert isinstance(path, Path)
        assert path.exists()

    def test_download_returns_source_path_when_no_cache(self, sample_csv: Path) -> None:
        conn = LocalCSVConnector(params={"path": str(sample_csv)})
        conn.connect()
        path = conn.download()
        assert path.resolve() == sample_csv.resolve()

    def test_metadata_available_after_download(self, sample_csv: Path) -> None:
        conn = LocalCSVConnector(params={"path": str(sample_csv)})
        conn.connect()
        conn.download()
        meta = conn.metadata()
        assert meta.connector_id == "csv"
        assert meta.row_count == 3
        assert meta.col_count == 3


# ---------------------------------------------------------------------------
# download() with cache
# ---------------------------------------------------------------------------

class TestLocalCSVConnectorDownloadWithCache:
    def test_download_populates_cache(self, sample_csv: Path, tmp_path: Path) -> None:
        cm = CacheManager(tmp_path / "cache")
        conn = LocalCSVConnector(params={"path": str(sample_csv)}, cache_manager=cm)
        conn.connect()
        conn.download()
        key = conn.cache_key()
        assert cm.is_cached(key)

    def test_cache_hit_on_second_download(self, sample_csv: Path, tmp_path: Path) -> None:
        cm = CacheManager(tmp_path / "cache")
        params = {"path": str(sample_csv)}
        conn1 = LocalCSVConnector(params=params, cache_manager=cm)
        conn1.connect()
        path1 = conn1.download()

        conn2 = LocalCSVConnector(params=params, cache_manager=cm)
        conn2.connect()
        path2 = conn2.download()

        assert path1.resolve() == path2.resolve()

    def test_force_refresh_overwrites_cache(self, sample_csv: Path, tmp_path: Path) -> None:
        cm = CacheManager(tmp_path / "cache")
        params = {"path": str(sample_csv)}
        conn = LocalCSVConnector(params=params, cache_manager=cm)
        conn.connect()
        conn.download()
        key = conn.cache_key()
        # Force refresh should not raise and should produce a valid cached file
        conn2 = LocalCSVConnector(params=params, cache_manager=cm)
        conn2.connect()
        conn2.download(force=True)
        assert cm.is_cached(key)


# ---------------------------------------------------------------------------
# validate()
# ---------------------------------------------------------------------------

class TestLocalCSVConnectorValidate:
    def test_validate_returns_report(self, sample_csv: Path) -> None:
        from econflow.ingestion.validation import DataValidationReport
        conn = LocalCSVConnector(params={"path": str(sample_csv)})
        conn.connect()
        path = conn.download()
        report = conn.validate(path)
        assert isinstance(report, DataValidationReport)

    def test_validate_no_errors_on_valid_csv(self, sample_csv: Path) -> None:
        conn = LocalCSVConnector(params={"path": str(sample_csv)})
        conn.connect()
        path = conn.download()
        report = conn.validate(path)
        assert not report.has_errors

    def test_validate_checks_required_columns(self, tmp_path: Path) -> None:
        p = tmp_path / "bad.csv"
        with p.open("w") as fh:
            fh.write("col1,col2\n1,2\n")
        conn = LocalCSVConnector(params={
            "path": str(p),
            "required_columns": ["col1", "col2", "missing_col"],
        })
        conn.connect()
        path = conn.download()
        report = conn.validate(path)
        assert report.has_errors


# ---------------------------------------------------------------------------
# fetch() convenience wrapper
# ---------------------------------------------------------------------------

class TestLocalCSVConnectorFetch:
    def test_fetch_returns_path_and_metadata(self, sample_csv: Path) -> None:
        conn = LocalCSVConnector(params={"path": str(sample_csv)})
        path, meta = conn.fetch()
        assert path.exists()
        assert meta.connector_id == "csv"

    def test_fetch_metadata_row_count_correct(self, sample_csv: Path) -> None:
        conn = LocalCSVConnector(params={"path": str(sample_csv)})
        _, meta = conn.fetch()
        assert meta.row_count == 3

    def test_fetch_with_cache(self, sample_csv: Path, tmp_path: Path) -> None:
        cm = CacheManager(tmp_path / "cache")
        conn = LocalCSVConnector(params={"path": str(sample_csv)}, cache_manager=cm)
        path, meta = conn.fetch()
        assert cm.is_cached(conn.cache_key())


# ---------------------------------------------------------------------------
# cache_key()
# ---------------------------------------------------------------------------

class TestLocalCSVConnectorCacheKey:
    def test_cache_key_is_string(self, sample_csv: Path) -> None:
        conn = LocalCSVConnector(params={"path": str(sample_csv)})
        assert isinstance(conn.cache_key(), str)

    def test_cache_key_is_64_chars_sha256(self, sample_csv: Path) -> None:
        conn = LocalCSVConnector(params={"path": str(sample_csv)})
        assert len(conn.cache_key()) == 64

    def test_same_path_same_key(self, sample_csv: Path) -> None:
        conn1 = LocalCSVConnector(params={"path": str(sample_csv)})
        conn2 = LocalCSVConnector(params={"path": str(sample_csv)})
        assert conn1.cache_key() == conn2.cache_key()

    def test_different_path_different_key(self, tmp_path: Path) -> None:
        p1 = tmp_path / "a.csv"
        p2 = tmp_path / "b.csv"
        p1.write_text("a\n1\n")
        p2.write_text("a\n1\n")
        conn1 = LocalCSVConnector(params={"path": str(p1)})
        conn2 = LocalCSVConnector(params={"path": str(p2)})
        assert conn1.cache_key() != conn2.cache_key()
