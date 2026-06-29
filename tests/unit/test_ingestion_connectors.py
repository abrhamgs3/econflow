"""
tests/unit/test_ingestion_connectors.py — Unit tests for built-in connectors.

Tests LocalCSVConnector fully (no network), and WorldBank/OECD/PWT/FRED
with mocked HTTP responses.  All network calls are intercepted so no
real API access is needed.
"""

from __future__ import annotations

import csv
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from econflow.ingestion.base import AbstractConnector, ConnectorError
from econflow.ingestion.cache import CacheManager
from econflow.ingestion.connectors.csv_connector import LocalCSVConnector
from econflow.ingestion.connectors.fred import FREDConnector
from econflow.ingestion.connectors.oecd import OECDConnector
from econflow.ingestion.connectors.pwt import PennWorldTablesConnector
from econflow.ingestion.connectors.world_bank import WorldBankConnector
from econflow.ingestion.manifest import DatasetManifest
from econflow.ingestion.metadata import DatasetMetadata
from econflow.ingestion.registry import get_connector, list_connectors

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_csv(path: Path, rows: list[list[str]]) -> None:
    """Write a CSV file to path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerows(rows)


# ---------------------------------------------------------------------------
# AbstractConnector interface
# ---------------------------------------------------------------------------

class TestAbstractConnectorInterface:
    """Verify that AbstractConnector exposes citation() and version() methods."""

    def test_csv_has_citation_method(self, tmp_path):
        src = tmp_path / "data.csv"
        _make_csv(src, [["entity", "time", "gdp"], ["USA", "2020", "21.3"]])
        conn = LocalCSVConnector(params={"path": str(src)})
        cit = conn.citation()
        assert isinstance(cit, str)

    def test_csv_has_version_method(self, tmp_path):
        src = tmp_path / "data.csv"
        _make_csv(src, [["entity", "time"], ["USA", "2020"]])
        conn = LocalCSVConnector(params={"path": str(src)})
        ver = conn.version()
        assert isinstance(ver, str)

    def test_world_bank_citation_is_nonempty(self):
        conn = WorldBankConnector(params={"indicators": ["IT.NET.USER.ZS"]})
        cit = conn.citation()
        assert "World Bank" in cit

    def test_world_bank_version_is_string(self):
        conn = WorldBankConnector(params={"indicators": ["IT.NET.USER.ZS"]})
        ver = conn.version()
        assert isinstance(ver, str)

    def test_fred_citation_nonempty(self):
        conn = FREDConnector(params={"series_ids": ["GDPPC"]})
        cit = conn.citation()
        assert "FRED" in cit or "Federal Reserve" in cit

    def test_fred_version_is_string(self):
        conn = FREDConnector(params={"series_ids": ["GDPPC"]})
        ver = conn.version()
        assert isinstance(ver, str)

    def test_oecd_citation_nonempty(self):
        conn = OECDConnector(params={"dataflow": "HEALTH_STAT"})
        cit = conn.citation()
        assert "OECD" in cit

    def test_pwt_citation_nonempty(self):
        conn = PennWorldTablesConnector(params={})
        cit = conn.citation()
        assert "Penn World" in cit or "Feenstra" in cit

    def test_pwt_version_matches_param(self):
        conn = PennWorldTablesConnector(params={"version": "10.01"})
        assert conn.version() == "10.01"


# ---------------------------------------------------------------------------
# LocalCSVConnector
# ---------------------------------------------------------------------------

class TestLocalCSVConnector:
    """Full functional tests without network."""

    def test_connect_passes_existing_file(self, tmp_path):
        src = tmp_path / "panel.csv"
        _make_csv(src, [["entity", "time"], ["USA", "2020"]])
        conn = LocalCSVConnector(params={"path": str(src)})
        conn.connect()  # should not raise

    def test_connect_raises_on_missing_file(self):
        conn = LocalCSVConnector(params={"path": "/does/not/exist/panel.csv"})
        with pytest.raises(ConnectorError, match="not found"):
            conn.connect()

    def test_requires_path_param(self):
        with pytest.raises(ConnectorError, match="path"):
            LocalCSVConnector(params={})

    def test_download_no_cache(self, tmp_path):
        src = tmp_path / "data.csv"
        _make_csv(src, [["entity", "time", "gdp"], ["USA", "2020", "21.3"]])
        conn = LocalCSVConnector(params={"path": str(src)})
        path = conn.download()
        assert path.exists()
        # Without cache manager, returns source path
        assert path == src

    def test_download_with_cache(self, tmp_path):
        src = tmp_path / "data.csv"
        _make_csv(src, [["entity", "time", "gdp"], ["USA", "2020", "21.3"]])
        cache = CacheManager(tmp_path / "cache")
        conn = LocalCSVConnector(params={"path": str(src)}, cache_manager=cache)
        path = conn.download()
        assert path.exists()
        assert "cache" in str(path)  # stored under cache dir

    def test_download_cache_hit(self, tmp_path):
        src = tmp_path / "data.csv"
        _make_csv(src, [["entity", "time"], ["USA", "2020"]])
        cache = CacheManager(tmp_path / "cache")
        conn = LocalCSVConnector(params={"path": str(src)}, cache_manager=cache)
        path1 = conn.download()
        path2 = conn.download()
        assert path1 == path2

    def test_metadata_after_download(self, tmp_path):
        src = tmp_path / "data.csv"
        _make_csv(src, [["entity", "time"], ["USA", "2020"], ["GBR", "2020"]])
        conn = LocalCSVConnector(params={"path": str(src)})
        conn.download()
        meta = conn.metadata()
        assert isinstance(meta, DatasetMetadata)
        assert meta.connector_id == "csv"

    def test_metadata_raises_before_download(self, tmp_path):
        src = tmp_path / "data.csv"
        _make_csv(src, [["entity", "time"]])
        conn = LocalCSVConnector(params={"path": str(src)})
        with pytest.raises(ConnectorError, match="download"):
            conn.metadata()

    def test_validate_detects_missing_required_cols(self, tmp_path):
        src = tmp_path / "data.csv"
        _make_csv(src, [["entity", "time"], ["USA", "2020"]])
        conn = LocalCSVConnector(
            params={"path": str(src), "required_columns": ["gdp"]}
        )
        report = conn.validate(src)
        assert report.has_errors

    def test_validate_passes_on_valid_csv(self, tmp_path):
        src = tmp_path / "data.csv"
        _make_csv(src, [["entity", "time", "gdp"], ["USA", "2020", "21.3"]])
        conn = LocalCSVConnector(params={"path": str(src)})
        report = conn.validate(src)
        assert not report.has_errors

    def test_cache_key_deterministic(self, tmp_path):
        src = tmp_path / "data.csv"
        _make_csv(src, [["a", "b"]])
        conn1 = LocalCSVConnector(params={"path": str(src)})
        conn2 = LocalCSVConnector(params={"path": str(src)})
        assert conn1.cache_key() == conn2.cache_key()

    def test_fetch_returns_path_and_metadata(self, tmp_path):
        src = tmp_path / "data.csv"
        _make_csv(src, [["entity", "time"], ["USA", "2020"]])
        conn = LocalCSVConnector(params={"path": str(src)})
        path, meta = conn.fetch()
        assert path.exists()
        assert isinstance(meta, DatasetMetadata)


# ---------------------------------------------------------------------------
# WorldBankConnector (mocked)
# ---------------------------------------------------------------------------

class TestWorldBankConnector:
    """WorldBankConnector tests with mocked HTTP."""

    def _mock_wb_response(self, indicator: str = "IT.NET.USER.ZS") -> list:
        """Build a minimal WB API response."""
        return [
            {"page": 1, "pages": 1, "per_page": 1000, "total": 2, "lastupdated": "2024-01-01"},
            [
                {"countryiso3code": "USA", "date": "2020", "value": 90.5,
                 "country": {"id": "US", "value": "United States"}},
                {"countryiso3code": "GBR", "date": "2020", "value": 96.0,
                 "country": {"id": "GB", "value": "United Kingdom"}},
            ]
        ]

    def test_requires_indicators_param(self):
        with pytest.raises(ConnectorError, match="indicator"):
            WorldBankConnector(params={})

    def test_cache_key_includes_indicators(self):
        c1 = WorldBankConnector(params={"indicators": ["IT.NET.USER.ZS"]})
        c2 = WorldBankConnector(params={"indicators": ["NY.GDP.MKTP.CD"]})
        assert c1.cache_key() != c2.cache_key()

    def test_connect_success(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = [{"lastupdated": "2024-01-01"}]

        with patch("requests.get", return_value=mock_resp):
            conn = WorldBankConnector(params={"indicators": ["IT.NET.USER.ZS"]})
            conn.connect()  # should not raise

    def test_download_writes_long_format_csv(self, tmp_path):
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = self._mock_wb_response()

        mock_version_resp = MagicMock()
        mock_version_resp.json.return_value = [{"lastupdated": "2024-01-01"}]

        def fake_get(url, **kwargs):
            # The version ping URL ends with ?format=json at the API root
            # The indicator URL contains /country/ or /indicator/
            if "/country/" in url or "/indicator/" in url:
                return mock_resp
            return mock_version_resp

        cache = CacheManager(tmp_path / "cache")
        with patch("requests.get", side_effect=fake_get):
            conn = WorldBankConnector(
                params={"indicators": ["IT.NET.USER.ZS"]},
                cache_manager=cache,
            )
            path = conn.download()
        assert path.exists()
        with path.open(encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            rows = list(reader)
        # At least one row
        assert len(rows) >= 1
        first = rows[0]
        assert "country" in first or "year" in first or "indicator" in first

    def test_metadata_raises_before_download(self):
        conn = WorldBankConnector(params={"indicators": ["IT.NET.USER.ZS"]})
        with pytest.raises(ConnectorError, match="download"):
            conn.metadata()

    def test_citation_is_nonempty(self):
        conn = WorldBankConnector(params={"indicators": ["IT.NET.USER.ZS"]})
        assert conn.citation()


# ---------------------------------------------------------------------------
# OECDConnector (mocked)
# ---------------------------------------------------------------------------

class TestOECDConnector:
    """OECDConnector tests with mocked HTTP."""

    def test_requires_dataflow_param(self):
        with pytest.raises(ConnectorError, match="dataflow"):
            OECDConnector(params={})

    def test_citation_contains_oecd(self):
        conn = OECDConnector(params={"dataflow": "HEALTH_STAT"})
        assert "OECD" in conn.citation()

    def test_cache_key_includes_dataflow(self):
        c1 = OECDConnector(params={"dataflow": "HEALTH_STAT"})
        c2 = OECDConnector(params={"dataflow": "EDU_GRAD"})
        assert c1.cache_key() != c2.cache_key()

    def _sdmx_payload(self) -> dict:
        """Minimal SDMX-JSON payload for testing."""
        return {
            "data": {
                "structures": [{
                    "dimensions": {
                        "series": [
                            {
                                "id": "LOCATION",
                                "values": [
                                    {"id": "USA", "name": "United States"},
                                    {"id": "GBR", "name": "United Kingdom"},
                                ]
                            },
                            {
                                "id": "MEASURE",
                                "values": [
                                    {"id": "PC_GDP", "name": "% of GDP"},
                                ]
                            }
                        ],
                        "observation": [
                            {
                                "id": "TIME_PERIOD",
                                "values": [
                                    {"id": "2020", "name": "2020"},
                                    {"id": "2021", "name": "2021"},
                                ]
                            }
                        ]
                    },
                    "attributes": {"series": []}
                }],
                "dataSets": [{
                    "series": {
                        "0:0": {
                            "observations": {
                                "0": [85.5, None],
                                "1": [87.2, None],
                            }
                        },
                        "1:0": {
                            "observations": {
                                "0": [92.1, None],
                                "1": [93.0, None],
                            }
                        }
                    }
                }]
            }
        }

    def test_parse_sdmx_json(self):
        conn = OECDConnector(params={"dataflow": "TEST"})
        rows = conn._parse_sdmx_json(
            self._sdmx_payload(),
            entity_col="country",
            time_col="year",
        )
        assert len(rows) >= 2
        assert all("country" in r and "year" in r for r in rows)

    def test_download_with_mock(self, tmp_path):
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = self._sdmx_payload()

        cache = CacheManager(tmp_path / "cache")
        with patch("requests.get", return_value=mock_resp):
            conn = OECDConnector(
                params={"dataflow": "HEALTH_STAT"},
                cache_manager=cache,
            )
            path = conn.download()
        assert path.exists()

    def test_validate_on_oecd_output(self, tmp_path):
        src = tmp_path / "oecd.csv"
        _make_csv(src, [
            ["country", "year", "indicator", "value", "measure"],
            ["USA", "2020", "HEALTH_STAT", "85.5", "PC_GDP"],
        ])
        conn = OECDConnector(params={"dataflow": "HEALTH_STAT"})
        report = conn.validate(src)
        assert not report.has_errors


# ---------------------------------------------------------------------------
# PennWorldTablesConnector
# ---------------------------------------------------------------------------

class TestPennWorldTablesConnector:
    """PWT connector tests."""

    def test_default_version(self):
        conn = PennWorldTablesConnector(params={})
        assert conn.version() == "10.01"

    def test_invalid_version_raises(self):
        with pytest.raises(ConnectorError, match="not supported"):
            PennWorldTablesConnector(params={"version": "99.99"})

    def test_list_versions(self):
        versions = PennWorldTablesConnector.list_versions()
        assert "10.01" in versions

    def test_download_url_set(self):
        conn = PennWorldTablesConnector(params={"version": "10.01"})
        assert conn.download_url.startswith("https://")

    def test_citation_has_feenstra(self):
        conn = PennWorldTablesConnector(params={})
        assert "Feenstra" in conn.citation()

    def test_validate_requires_entity_time(self, tmp_path):
        src = tmp_path / "pwt.csv"
        _make_csv(src, [
            ["country", "year", "rgdpna"],
            ["USA", "2020", "21000"],
        ])
        conn = PennWorldTablesConnector(
            params={"variables": ["rgdpna"]}
        )
        report = conn.validate(src)
        # entity_col defaults to 'country', time_col to 'year' — should pass
        assert not report.has_errors

    def test_excel_to_csv_mapping(self, tmp_path):
        """Test the Excel->CSV conversion helper with an openpyxl mock."""
        import openpyxl
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "data"
        ws.append(["countrycode", "year", "rgdpna", "emp"])
        ws.append(["USA", 2020, 21000.5, 150.3])
        ws.append(["GBR", 2020, 2700.1, 32.1])
        xl_path = tmp_path / "pwt.xlsx"
        wb.save(str(xl_path))

        conn = PennWorldTablesConnector(params={"variables": ["rgdpna"]})
        csv_path = conn._excel_to_csv(
            xl_path,
            variables=["rgdpna"],
            entity_col="country",
            time_col="year",
        )
        assert csv_path.exists()
        with csv_path.open(encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            rows = list(reader)
        assert len(rows) == 2
        assert "country" in rows[0]
        assert "rgdpna" in rows[0]
        assert "emp" not in rows[0]  # filtered out
        csv_path.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# FREDConnector (mocked)
# ---------------------------------------------------------------------------

class TestFREDConnector:
    """FRED connector tests with mocked HTTP."""

    def test_requires_series_ids(self):
        with pytest.raises(ConnectorError, match="series_ids"):
            FREDConnector(params={})

    def test_api_key_from_env(self, monkeypatch):
        monkeypatch.setenv("FRED_API_KEY", "testkey123")
        conn = FREDConnector(params={"series_ids": ["GDPPC"]})
        assert conn._api_key == "testkey123"

    def test_api_key_from_params(self):
        conn = FREDConnector(params={"series_ids": ["GDPPC"], "api_key": "mykey"})
        assert conn._api_key == "mykey"

    def test_connect_raises_without_key(self):
        conn = FREDConnector(params={"series_ids": ["GDPPC"]})
        # No key set
        conn._api_key = ""
        with pytest.raises(ConnectorError, match="API key"):
            conn.connect()

    def test_cache_key_excludes_api_key(self):
        c1 = FREDConnector(params={"series_ids": ["GDPPC"], "api_key": "key1"})
        c2 = FREDConnector(params={"series_ids": ["GDPPC"], "api_key": "key2"})
        assert c1.cache_key() == c2.cache_key()

    def _mock_series_meta(self, series_id: str) -> dict:
        return {
            "seriess": [
                {"id": series_id, "title": f"Test {series_id}", "units": "Index"}
            ]
        }

    def _mock_observations(self) -> dict:
        return {
            "observations": [
                {"date": "2020-01-01", "value": "100.5"},
                {"date": "2021-01-01", "value": "103.2"},
                {"date": "2022-01-01", "value": "."},  # missing value
            ]
        }

    def test_download_long_format_csv(self, tmp_path, monkeypatch):
        monkeypatch.setenv("FRED_API_KEY", "testkey")

        def fake_get(url, **kwargs):
            resp = MagicMock()
            resp.raise_for_status = MagicMock()
            if "/series/observations" in url:
                resp.json.return_value = self._mock_observations()
            else:
                resp.json.return_value = self._mock_series_meta("GDPPC")
            return resp

        cache = CacheManager(tmp_path / "cache")
        with patch("requests.get", side_effect=fake_get):
            conn = FREDConnector(
                params={"series_ids": ["GDPPC"]},
                cache_manager=cache,
            )
            path = conn.download()

        assert path.exists()
        with path.open(encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            rows = list(reader)
        assert len(rows) == 3
        assert rows[2]["value"] == ""  # "." converted to empty

    def test_validate_long_format(self, tmp_path):
        src = tmp_path / "fred.csv"
        _make_csv(src, [
            ["series_id", "date", "value", "series_name", "units"],
            ["GDPPC", "2020-01-01", "100.5", "GDP per Capita", "USD"],
        ])
        conn = FREDConnector(params={"series_ids": ["GDPPC"]})
        report = conn.validate(src)
        assert not report.has_errors

    def test_citation_contains_fred(self):
        conn = FREDConnector(params={"series_ids": ["GDPPC"]})
        assert "FRED" in conn.citation() or "Federal Reserve" in conn.citation()


# ---------------------------------------------------------------------------
# Registry integration
# ---------------------------------------------------------------------------

class TestConnectorRegistryIntegration:
    """Verify all built-in connectors are registered."""

    def test_all_four_connectors_registered(self):
        import econflow.ingestion  # noqa: F401 — triggers registration
        ids = {c["id"] for c in list_connectors()}
        assert "csv" in ids
        assert "world_bank" in ids
        assert "oecd" in ids
        assert "pwt" in ids
        assert "fred" in ids

    def test_get_connector_returns_class(self):
        import econflow.ingestion  # noqa: F401
        cls = get_connector("csv")
        assert issubclass(cls, AbstractConnector)

    def test_get_connector_raises_on_unknown(self):
        from econflow.ingestion.registry import get_connector as _gc
        with pytest.raises(KeyError):
            _gc("nonexistent_connector_xyz")


# ---------------------------------------------------------------------------
# DatasetManifest
# ---------------------------------------------------------------------------

class TestDatasetManifest:
    """Unit tests for DatasetManifest."""

    def _meta(self) -> DatasetMetadata:
        return DatasetMetadata.now(
            connector_id="csv",
            source="Test",
            url="/test.csv",
            row_count=10,
            col_count=3,
            columns=["entity", "time", "gdp"],
        )

    def test_empty_manifest(self):
        m = DatasetManifest(project="test")
        assert len(m) == 0
        assert m.all_passed
        assert m.total_errors == 0

    def test_add_entry(self):
        m = DatasetManifest(project="test")
        m.add_entry(
            connector_id="csv",
            cache_key="abc123",
            params={"path": "/data.csv"},
            metadata=self._meta(),
            validation_passed=True,
            citation="Test citation",
            dataset_version="1.0",
        )
        assert len(m) == 1
        assert m.all_passed

    def test_add_failed_entry(self):
        m = DatasetManifest(project="test")
        m.add_entry(
            connector_id="csv",
            cache_key="abc123",
            params={},
            metadata=self._meta(),
            validation_passed=False,
            validation_errors=2,
        )
        assert not m.all_passed
        assert m.total_errors == 2

    def test_serialization_roundtrip(self):
        m = DatasetManifest(project="my_project")
        m.add_entry(
            connector_id="world_bank",
            cache_key="deadbeef",
            params={"indicators": ["IT.NET.USER.ZS"]},
            metadata=self._meta(),
            citation="WB citation",
        )
        restored = DatasetManifest.from_json(m.to_json())
        assert restored.project == "my_project"
        assert len(restored.entries) == 1
        assert restored.entries[0].connector_id == "world_bank"
        assert restored.entries[0].citation == "WB citation"

    def test_save_and_load(self, tmp_path):
        m = DatasetManifest(project="save_test")
        m.add_entry(
            connector_id="fred",
            cache_key="f00d",
            params={"series_ids": ["GDPPC"]},
            metadata=self._meta(),
        )
        path = tmp_path / "manifest.json"
        m.save(path)
        assert path.exists()
        loaded = DatasetManifest.load(path)
        assert loaded.project == "save_test"
        assert len(loaded.entries) == 1

    def test_citations_list(self):
        m = DatasetManifest()
        m.add_entry(
            connector_id="csv",
            cache_key="k1",
            params={},
            metadata=self._meta(),
            citation="First citation",
        )
        m.add_entry(
            connector_id="csv",
            cache_key="k2",
            params={},
            metadata=self._meta(),
            citation="",  # empty — excluded
        )
        cits = m.citations()
        assert len(cits) == 1
        assert "First citation" in cits

    def test_schema_version_in_json(self):
        m = DatasetManifest()
        d = m.to_dict()
        assert "schema_version" in d
        assert d["schema_version"] == "1.0.0"
