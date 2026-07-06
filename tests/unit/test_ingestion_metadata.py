"""
tests/unit/test_ingestion_metadata.py — Unit tests for DatasetMetadata.

Covers:
- DatasetMetadata.now() factory stamps current UTC time
- to_dict() returns plain dict with all fields
- to_json() / from_json() round-trip
- from_dict() handles missing optional fields with defaults
- __str__ includes connector_id, source, row_count, col_count
"""

from __future__ import annotations

import json

from econflow.ingestion.metadata import DatasetMetadata


class TestDatasetMetadataNow:
    def _make(self, **kwargs) -> DatasetMetadata:
        defaults = dict(
            connector_id="test",
            source="Test Source",
            url="https://example.com/data.csv",
        )
        defaults.update(kwargs)
        return DatasetMetadata.now(**defaults)

    def test_connector_id_set(self) -> None:
        m = self._make(connector_id="csv")
        assert m.connector_id == "csv"

    def test_source_set(self) -> None:
        m = self._make(source="My Source")
        assert m.source == "My Source"

    def test_url_set(self) -> None:
        m = self._make(url="https://data.gov/file.csv")
        assert m.url == "https://data.gov/file.csv"

    def test_download_date_is_iso8601_utc(self) -> None:
        m = self._make()
        # ISO-8601 UTC ends with +00:00 or Z or has a timezone component
        assert "T" in m.download_date

    def test_default_version_is_unknown(self) -> None:
        m = self._make()
        assert m.version == "unknown"

    def test_default_citation_is_empty(self) -> None:
        m = self._make()
        assert m.citation == ""

    def test_default_sha256_is_empty(self) -> None:
        m = self._make()
        assert m.sha256_hash == ""

    def test_default_row_count_zero(self) -> None:
        m = self._make()
        assert m.row_count == 0

    def test_default_col_count_zero(self) -> None:
        m = self._make()
        assert m.col_count == 0

    def test_default_columns_is_empty_list(self) -> None:
        m = self._make()
        assert m.columns == []

    def test_default_params_is_empty_dict(self) -> None:
        m = self._make()
        assert m.params == {}

    def test_custom_version(self) -> None:
        m = self._make(version="2024-Q1")
        assert m.version == "2024-Q1"

    def test_custom_columns(self) -> None:
        m = self._make(columns=["country", "year", "gdp"])
        assert m.columns == ["country", "year", "gdp"]

    def test_custom_params(self) -> None:
        m = self._make(params={"indicators": ["NY.GDP.MKTP.CD"]})
        assert m.params == {"indicators": ["NY.GDP.MKTP.CD"]}


class TestDatasetMetadataSerialization:
    def _sample(self) -> DatasetMetadata:
        return DatasetMetadata(
            connector_id="world_bank",
            source="World Bank",
            download_date="2026-06-27T12:00:00+00:00",
            url="https://api.worldbank.org/v2",
            version="2024-Q1",
            citation="World Bank (2024)",
            sha256_hash="abc123",
            row_count=1000,
            col_count=4,
            columns=["country", "year", "indicator", "value"],
            params={"indicators": ["NY.GDP.MKTP.CD"]},
        )

    def test_to_dict_returns_dict(self) -> None:
        d = self._sample().to_dict()
        assert isinstance(d, dict)

    def test_to_dict_has_all_fields(self) -> None:
        d = self._sample().to_dict()
        for field in (
            "connector_id", "source", "download_date", "url", "version",
            "citation", "sha256_hash", "row_count", "col_count",
            "columns", "params",
        ):
            assert field in d, f"Missing field: {field}"

    def test_to_json_is_valid_json(self) -> None:
        j = self._sample().to_json()
        parsed = json.loads(j)
        assert isinstance(parsed, dict)

    def test_from_json_round_trip(self) -> None:
        original = self._sample()
        reconstructed = DatasetMetadata.from_json(original.to_json())
        assert reconstructed.connector_id == original.connector_id
        assert reconstructed.source == original.source
        assert reconstructed.row_count == original.row_count
        assert reconstructed.columns == original.columns
        assert reconstructed.params == original.params

    def test_from_dict_round_trip(self) -> None:
        original = self._sample()
        reconstructed = DatasetMetadata.from_dict(original.to_dict())
        assert reconstructed.sha256_hash == original.sha256_hash
        assert reconstructed.col_count == original.col_count

    def test_from_dict_missing_optional_fields(self) -> None:
        data = {
            "connector_id": "csv", "source": "Local",
            "download_date": "2026-01-01T00:00:00+00:00",
            "url": "/data.csv",
        }
        m = DatasetMetadata.from_dict(data)
        assert m.version == "unknown"
        assert m.citation == ""
        assert m.sha256_hash == ""
        assert m.row_count == 0
        assert m.col_count == 0
        assert m.columns == []
        assert m.params == {}


class TestDatasetMetadataStr:
    def test_str_contains_connector_id(self) -> None:
        m = DatasetMetadata.now(connector_id="csv", source="Local", url="/f.csv")
        assert "csv" in str(m)

    def test_str_contains_source(self) -> None:
        m = DatasetMetadata.now(connector_id="csv", source="Test Source", url="/f.csv")
        assert "Test Source" in str(m)

    def test_str_contains_row_count(self) -> None:
        m = DatasetMetadata.now(connector_id="csv", source="S", url="/f.csv", row_count=42)
        assert "42" in str(m)
