"""
econflow.ingestion.connectors.fred -- FRED (Federal Reserve Economic Data) connector.

Downloads time-series data from the St. Louis Fed FRED API.

API reference: https://fred.stlouisfed.org/docs/api/fred/
Requires a free API key from: https://fred.stlouisfed.org/docs/api/api_key.html

Usage
-----
::

    from econflow.ingestion.connectors import FREDConnector
    from econflow.ingestion.cache import CacheManager

    cache = CacheManager(".cache/econflow")
    conn = FREDConnector(
        params={
            "series_ids": ["GDPPC", "UNRATE", "CPIAUCSL"],
            "api_key": "your_fred_api_key",
            "start_date": "2000-01-01",
            "end_date": "2023-12-31",
            "frequency": "a",       # a=annual, q=quarterly, m=monthly
        },
        cache_manager=cache,
    )
    path, meta = conn.fetch()

Output CSV columns
------------------
``date``, ``series_id``, ``value``, ``series_name``, ``units``

The API key can also be provided via the ``FRED_API_KEY`` environment
variable instead of passing it in ``params``.
"""

from __future__ import annotations

import csv
import os
from pathlib import Path
from typing import Any

from econflow.ingestion.base import AbstractConnector, ConnectorError
from econflow.ingestion.metadata import DatasetMetadata
from econflow.ingestion.registry import register
from econflow.ingestion.validation import DataValidationConfig, DataValidationReport, DataValidator

_API_BASE = "https://api.stlouisfed.org/fred"
_CITATION = (
    "Federal Reserve Bank of St. Louis (2024). "
    "Federal Reserve Economic Data (FRED). "
    "St. Louis Fed. https://fred.stlouisfed.org"
)
_VERSION = "FRED API v2"


@register(
    "fred",
    label="FRED (Federal Reserve Economic Data)",
    status="implemented",
    notes="St. Louis Fed FRED API v2; requires FRED_API_KEY env var or params['api_key']",
)
class FREDConnector(AbstractConnector):
    """
    Connector for the Federal Reserve Economic Data (FRED) API.

    Downloads one or more FRED series and writes a long-format CSV with
    columns: ``date``, ``series_id``, ``value``, ``series_name``, ``units``.

    Parameters (``params`` dict keys)
    -----------------------------------
    series_ids : list[str]
        FRED series identifiers (e.g. ``["GDPPC", "UNRATE"]``).  Required.
        Common series:

        * ``"GDPPC"``     — GDP per capita (current $US)
        * ``"UNRATE"``    — Civilian Unemployment Rate
        * ``"CPIAUCSL"``  — Consumer Price Index for All Urban Consumers
        * ``"FEDFUNDS"``  — Effective Federal Funds Rate
        * ``"INDPRO"``    — Industrial Production Index
        * ``"T10Y2Y"``    — 10-Year Treasury Constant Maturity Minus 2-Year

    api_key : str | None
        FRED API key.  If omitted, read from ``FRED_API_KEY`` environment variable.
    start_date : str | None
        Observation start date in ``YYYY-MM-DD`` format.
    end_date : str | None
        Observation end date in ``YYYY-MM-DD`` format.
    frequency : str | None
        Aggregation frequency: ``"d"`` (daily), ``"w"`` (weekly), ``"m"`` (monthly),
        ``"q"`` (quarterly), ``"a"`` (annual).  ``None`` = native frequency.
    aggregation_method : str
        How to aggregate: ``"avg"`` (default), ``"sum"``, ``"eop"`` (end of period).
    entity_col : str
        Column name for the series dimension.  Default ``"series_id"``.
    time_col : str
        Column name for the date dimension.  Default ``"date"``.
    timeout : int
        HTTP timeout in seconds.  Default 30.
    """

    _CITATION = _CITATION
    _VERSION = _VERSION

    def __init__(
        self,
        params: dict[str, Any] | None = None,
        cache_manager: Any | None = None,
    ) -> None:
        super().__init__(params, cache_manager)
        if not self.params.get("series_ids"):
            raise ConnectorError(
                "FREDConnector requires params['series_ids'] (list of FRED series IDs).",
                connector_id="fred",
            )
        self._api_key = str(
            self.params.get("api_key") or os.environ.get("FRED_API_KEY", "")
        )
        self._cached_meta: DatasetMetadata | None = None
        self._cached_path: Path | None = None

    # ------------------------------------------------------------------
    # AbstractConnector interface
    # ------------------------------------------------------------------

    def connect(self) -> None:
        """Verify FRED API is reachable and API key is valid."""
        if not self._api_key:
            raise ConnectorError(
                "FREDConnector requires an API key. "
                "Pass params['api_key'] or set the FRED_API_KEY environment variable. "
                "Get a free key at: https://fred.stlouisfed.org/docs/api/api_key.html",
                connector_id="fred",
            )
        _requests = self._import_requests()
        # Lightweight ping: fetch first series metadata
        series_ids = list(self.params["series_ids"])
        url = (
            f"{_API_BASE}/series"
            f"?series_id={series_ids[0]}&api_key={self._api_key}&file_type=json"
        )
        try:
            resp = _requests.get(url, timeout=int(self.params.get("timeout", 30)))
            if resp.status_code == 400:
                raise ConnectorError(
                    f"FRED API returned 400. Check series_id {series_ids[0]!r} "
                    f"and your API key.",
                    connector_id="fred",
                )
            resp.raise_for_status()
        except ConnectorError:
            raise
        except Exception as exc:
            raise ConnectorError(
                f"Cannot reach FRED API at {_API_BASE}.",
                connector_id="fred",
                cause=exc,
            ) from exc

    def download(self, *, force: bool = False) -> Path:
        """Download all configured series and write a tidy long-format CSV."""
        key = self.cache_key()

        if self.cache_manager is not None and not force:
            if self.cache_manager.is_cached(key):
                path, meta = self.cache_manager.retrieve(key)
                self._cached_path = path
                self._cached_meta = meta
                return path

        if not self._api_key:
            raise ConnectorError(
                "FREDConnector requires an API key. "
                "Pass params['api_key'] or set FRED_API_KEY.",
                connector_id="fred",
            )

        _requests = self._import_requests()
        series_ids = list(self.params["series_ids"])
        entity_col = str(self.params.get("entity_col", "series_id"))
        time_col = str(self.params.get("time_col", "date"))

        rows: list[dict[str, str]] = []
        for sid in series_ids:
            series_rows = self._fetch_series(
                _requests, sid, entity_col=entity_col, time_col=time_col
            )
            rows.extend(series_rows)

        import tempfile
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, encoding="utf-8", newline=""
        ) as tmp:
            fieldnames = [entity_col, time_col, "value", "series_name", "units"]
            writer = csv.DictWriter(tmp, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)
            tmp_path = Path(tmp.name)

        meta = DatasetMetadata.now(
            connector_id="fred",
            source="FRED (Federal Reserve Economic Data)",
            url=_API_BASE,
            version=_VERSION,
            citation=_CITATION,
            params={k: v for k, v in self.params.items() if k != "api_key"},
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
        entity_col = str(self.params.get("entity_col", "series_id"))
        time_col = str(self.params.get("time_col", "date"))
        config = DataValidationConfig(
            required_columns=[entity_col, time_col, "value"],
            entity_col=entity_col,
            time_col=time_col,
            check_duplicates=False,
            check_missing_identifiers=True,
        )
        return DataValidator(config).validate_path(path)

    def metadata(self) -> DatasetMetadata:
        if self._cached_meta is None:
            raise ConnectorError(
                "No metadata available. Call download() first.",
                connector_id="fred",
            )
        return self._cached_meta

    def cache_key(self) -> str:
        # Exclude api_key from cache key (security + portability)
        params_no_key = {k: v for k, v in self.params.items() if k != "api_key"}
        import hashlib
        import json
        payload = {
            "connector_id": "fred",
            "params": {k: params_no_key[k] for k in sorted(params_no_key)},
        }
        encoded = json.dumps(payload, sort_keys=True, ensure_ascii=True)
        return hashlib.sha256(encoded.encode()).hexdigest()

    def citation(self) -> str:
        return _CITATION

    def version(self) -> str:
        return _VERSION

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _import_requests() -> Any:
        try:
            import requests  # noqa: PLC0415
            return requests
        except ImportError as exc:
            raise ConnectorError(
                "FREDConnector requires 'requests'. Install with: pip install requests",
                connector_id="fred",
                cause=exc,
            ) from exc

    def _fetch_series(
        self,
        _requests: Any,
        series_id: str,
        *,
        entity_col: str,
        time_col: str,
    ) -> list[dict[str, str]]:
        """Fetch observations for a single FRED series."""
        # First fetch series metadata for name/units
        meta_url = (
            f"{_API_BASE}/series"
            f"?series_id={series_id}&api_key={self._api_key}&file_type=json"
        )
        series_name = series_id
        units = ""
        try:
            meta_resp = _requests.get(
                meta_url, timeout=int(self.params.get("timeout", 30))
            )
            meta_resp.raise_for_status()
            meta_json = meta_resp.json()
            serieses = meta_json.get("seriess", [])
            if serieses:
                series_name = serieses[0].get("title", series_id)
                units = serieses[0].get("units", "")
        except Exception:
            pass  # non-fatal: use series_id as name

        # Now fetch observations
        obs_url = (
            f"{_API_BASE}/series/observations"
            f"?series_id={series_id}&api_key={self._api_key}&file_type=json"
        )
        if self.params.get("start_date"):
            obs_url += f"&observation_start={self.params['start_date']}"
        if self.params.get("end_date"):
            obs_url += f"&observation_end={self.params['end_date']}"
        if self.params.get("frequency"):
            obs_url += f"&frequency={self.params['frequency']}"
        agg = str(self.params.get("aggregation_method", "avg"))
        obs_url += f"&aggregation_method={agg}"

        try:
            resp = _requests.get(
                obs_url, timeout=int(self.params.get("timeout", 30))
            )
            resp.raise_for_status()
            payload = resp.json()
        except Exception as exc:
            raise ConnectorError(
                f"Failed to fetch FRED series {series_id!r}.",
                connector_id="fred",
                cause=exc,
            ) from exc

        rows: list[dict[str, str]] = []
        for obs in payload.get("observations", []):
            value = str(obs.get("value", ""))
            if value == ".":  # FRED uses "." for missing
                value = ""
            rows.append({
                entity_col: series_id,
                time_col: str(obs.get("date", "")),
                "value": value,
                "series_name": series_name,
                "units": units,
            })
        return rows
