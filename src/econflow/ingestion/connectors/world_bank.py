"""
econflow.ingestion.connectors.world_bank -- World Bank Open Data connector.

Downloads indicator time series from the World Bank API v2
(https://api.worldbank.org/v2/).  No API key required.

Supported indicators (examples)
---------------------------------
* IT.NET.USER.ZS  -- Individuals using the Internet (% of population)
* GB.XPD.RSDV.GD.ZS -- R&D expenditure (% of GDP)
* NE.GDI.TOTL.ZS  -- Gross capital formation (% of GDP)

Usage
-----
::

    from econflow.ingestion.connectors import WorldBankConnector
    from econflow.ingestion.cache import CacheManager

    cache = CacheManager(".cache/econflow")
    conn = WorldBankConnector(
        params={
            "indicators": ["IT.NET.USER.ZS", "GB.XPD.RSDV.GD.ZS"],
            "year_start": 2000,
            "year_end": 2022,
        },
        cache_manager=cache,
    )
    path, meta = conn.fetch()
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from econflow.ingestion.base import AbstractConnector, ConnectorError
from econflow.ingestion.metadata import DatasetMetadata
from econflow.ingestion.registry import register
from econflow.ingestion.validation import DataValidationConfig, DataValidationReport, DataValidator

_API_BASE = "https://api.worldbank.org/v2"
_DEFAULT_PER_PAGE = 1000
_CITATION = (
    "World Bank (2024). World Development Indicators. "
    "The World Bank Group. https://data.worldbank.org"
)


@register(
    "world_bank",
    label="World Bank Open Data",
    status="implemented",
    notes="WB API v2; no API key required; indicators, countries, year range configurable",
)
class WorldBankConnector(AbstractConnector):
    """
    Connector for the World Bank Open Data API (v2).

    Parameters (``params`` dict keys)
    -----------------------------------
    indicators : list[str]
        World Bank indicator codes.  Required.
    countries : list[str] | None
        ISO-2 or ISO-3 country codes.  ``None`` means all countries.
    year_start : int | None
        Inclusive start year.  Defaults to no lower bound.
    year_end : int | None
        Inclusive end year.  Defaults to no upper bound.
    entity_col : str
        Column name for the entity dimension in output.  Default ``"country"``.
    time_col : str
        Column name for the time dimension in output.  Default ``"year"``.
    """

    _CITATION = _CITATION
    _VERSION = "unknown"

    def __init__(
        self,
        params: dict[str, Any] | None = None,
        cache_manager: Any | None = None,
    ) -> None:
        super().__init__(params, cache_manager)
        if not self.params.get("indicators"):
            raise ConnectorError(
                "WorldBankConnector requires at least one indicator in params['indicators'].",
                connector_id="world_bank",
            )
        self._cached_meta: DatasetMetadata | None = None
        self._cached_path: Path | None = None

    # ------------------------------------------------------------------
    # AbstractConnector interface
    # ------------------------------------------------------------------

    def connect(self) -> None:
        """Verify the World Bank API is reachable with a lightweight ping."""
        try:
            import requests  # noqa: PLC0415
        except ImportError as exc:
            raise ConnectorError(
                "WorldBankConnector requires 'requests'. "
                "Install with: pip install requests",
                connector_id="world_bank",
                cause=exc,
            ) from exc
        try:
            resp = requests.get(f"{_API_BASE}?format=json", timeout=10)
            resp.raise_for_status()
        except Exception as exc:
            raise ConnectorError(
                f"Cannot reach World Bank API at {_API_BASE}.",
                connector_id="world_bank",
                cause=exc,
            ) from exc

    def download(self, *, force: bool = False) -> Path:
        """Download all configured indicators and write a tidy long-format CSV."""
        key = self.cache_key()

        if self.cache_manager is not None and not force:
            if self.cache_manager.is_cached(key):
                path, meta = self.cache_manager.retrieve(key)
                self._cached_path = path
                self._cached_meta = meta
                return path

        try:
            import requests  # noqa: PLC0415
        except ImportError as exc:
            raise ConnectorError(
                "WorldBankConnector requires 'requests'.",
                connector_id="world_bank",
                cause=exc,
            ) from exc

        indicators = self.params.get("indicators", [])
        countries = self.params.get("countries") or "all"
        year_start = self.params.get("year_start")
        year_end = self.params.get("year_end")
        entity_col = str(self.params.get("entity_col", "country"))
        time_col = str(self.params.get("time_col", "year"))

        rows: list[dict[str, str]] = []
        for indicator in indicators:
            rows.extend(
                self._fetch_indicator(
                    requests, indicator, countries, year_start, year_end,
                    entity_col=entity_col, time_col=time_col,
                )
            )

        # Write to a temp file then cache
        import tempfile
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, encoding="utf-8", newline=""
        ) as tmp:
            fieldnames = [entity_col, time_col, "indicator", "value"]
            writer = csv.DictWriter(tmp, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
            tmp_path = Path(tmp.name)

        meta = DatasetMetadata.now(
            connector_id="world_bank",
            source="World Bank Open Data",
            url=_API_BASE,
            version=self._api_version(requests),
            citation=_CITATION,
            params=self.params,
        )

        if self.cache_manager is not None:
            stored = self.cache_manager.store(key, tmp_path, meta)
            tmp_path.unlink(missing_ok=True)
            _, self._cached_meta = self.cache_manager.retrieve(key)
            self._cached_path = stored
            return stored

        self._cached_path = tmp_path
        self._cached_meta = meta
        return tmp_path

    def validate(self, path: Path) -> DataValidationReport:
        """Validate the downloaded long-format CSV."""
        entity_col = str(self.params.get("entity_col", "country"))
        time_col = str(self.params.get("time_col", "year"))
        config = DataValidationConfig(
            required_columns=[entity_col, time_col, "indicator", "value"],
            entity_col=entity_col,
            time_col=time_col,
            check_duplicates=False,  # long format has duplicate (country, year) pairs
            check_missing_identifiers=True,
        )
        return DataValidator(config).validate_path(path)

    def metadata(self) -> DatasetMetadata:
        if self._cached_meta is None:
            raise ConnectorError(
                "No metadata available. Call download() first.",
                connector_id="world_bank",
            )
        return self._cached_meta

    def cache_key(self) -> str:
        return self._make_cache_key()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_url(
        self,
        indicator: str,
        countries: str | list[str],
        page: int = 1,
    ) -> str:
        if isinstance(countries, list):
            countries_str = ";".join(countries)
        else:
            countries_str = countries
        return (
            f"{_API_BASE}/country/{countries_str}/indicator/{indicator}"
            f"?format=json&per_page={_DEFAULT_PER_PAGE}&page={page}"
        )

    def _fetch_indicator(
        self,
        requests: Any,
        indicator: str,
        countries: Any,
        year_start: int | None,
        year_end: int | None,
        entity_col: str,
        time_col: str,
    ) -> list[dict[str, str]]:
        """Paginate through the WB API and return all rows for one indicator."""
        rows: list[dict[str, str]] = []
        page = 1
        while True:
            url = self._build_url(indicator, countries, page=page)
            try:
                resp = requests.get(url, timeout=30)
                resp.raise_for_status()
                payload = resp.json()
            except Exception as exc:
                raise ConnectorError(
                    f"Failed to fetch indicator {indicator!r} from World Bank API.",
                    connector_id="world_bank",
                    cause=exc,
                ) from exc

            if not isinstance(payload, list) or len(payload) < 2:
                break
            meta_block = payload[0]
            data_block = payload[1] or []

            for entry in data_block:
                if not isinstance(entry, dict):
                    continue
                raw_year = str(entry.get("date", ""))
                raw_val = entry.get("value")
                country_code = (entry.get("countryiso3code") or
                               entry.get("country", {}).get("id", ""))
                try:
                    yr = int(raw_year)
                except (ValueError, TypeError):
                    continue
                if year_start and yr < year_start:
                    continue
                if year_end and yr > year_end:
                    continue
                rows.append({
                    entity_col: str(country_code),
                    time_col: raw_year,
                    "indicator": indicator,
                    "value": "" if raw_val is None else str(raw_val),
                })

            total_pages = int(meta_block.get("pages", 1))
            if page >= total_pages:
                break
            page += 1

        return rows

    def _api_version(self, requests: Any) -> str:
        """Try to get the WB API version string."""
        try:
            resp = requests.get(
                f"{_API_BASE}?format=json", timeout=5
            )
            payload = resp.json()
            return str(payload[0].get("lastupdated", "unknown"))
        except Exception:
            return "unknown"
