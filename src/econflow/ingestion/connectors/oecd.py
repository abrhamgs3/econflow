"""
econflow.ingestion.connectors.oecd -- OECD SDMX-JSON connector.

Downloads indicator data from the OECD SDMX-JSON API (v1.0).
No API key is required for public datasets.

Reference
---------
* OECD Data API docs: https://data.oecd.org/api/sdmx-json-documentation/
* Base URL: https://sdmx.oecd.org/public/rest/

Usage
-----
::

    from econflow.ingestion.connectors import OECDConnector
    from econflow.ingestion.cache import CacheManager

    cache = CacheManager(".cache/econflow")
    conn = OECDConnector(
        params={
            "dataflow": "HEALTH_STAT",
            "filter": "AUS+CAN+FRA+DEU+GBR+USA..",
            "start_period": "2010",
            "end_period": "2022",
        },
        cache_manager=cache,
    )
    path, meta = conn.fetch()

SDMX-JSON structure
--------------------
The API returns a JSON envelope with:

* ``data.dataSets[0].series``  — dict keyed by dimension-key string e.g. "0:0:1:3"
* ``data.structures[0].dimensions.series`` — ordered list of dimension descriptors
* Each series has ``observations`` keyed by time-period index

We parse the dimension metadata to decode keys, then flatten to long CSV.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from econflow.ingestion.base import AbstractConnector, ConnectorError
from econflow.ingestion.metadata import DatasetMetadata
from econflow.ingestion.registry import register
from econflow.ingestion.validation import DataValidationConfig, DataValidationReport, DataValidator

_API_BASE = "https://sdmx.oecd.org/public/rest"
_CITATION = (
    "OECD (2024). OECD Data. "
    "Organisation for Economic Co-operation and Development. "
    "https://data.oecd.org"
)
_VERSION = "SDMX-JSON v1.0"


@register(
    "oecd",
    label="OECD SDMX-JSON API",
    status="implemented",
    notes="OECD public SDMX-JSON API; no API key required for public dataflows",
)
class OECDConnector(AbstractConnector):
    """
    Connector for the OECD SDMX-JSON API.

    Parameters (``params`` dict keys)
    -----------------------------------
    dataflow : str
        OECD dataflow identifier (e.g. ``"HEALTH_STAT"``).  Required.
    filter : str
        SDMX filter expression (e.g. ``"AUS+CAN+FRA.."``).
        Defaults to ``"all"`` (all members).
    start_period : str | None
        Start period (e.g. ``"2010"``).
    end_period : str | None
        End period (e.g. ``"2022"``).
    entity_col : str
        Column name for the country dimension in output.  Default ``"country"``.
    time_col : str
        Column name for the time dimension in output.  Default ``"year"``.
    timeout : int
        HTTP timeout in seconds.  Default 60.
    """

    _CITATION = _CITATION
    _VERSION = _VERSION

    def __init__(
        self,
        params: dict[str, Any] | None = None,
        cache_manager: Any | None = None,
    ) -> None:
        super().__init__(params, cache_manager)
        if not self.params.get("dataflow"):
            raise ConnectorError(
                "OECDConnector requires params['dataflow'] (SDMX dataflow identifier).",
                connector_id="oecd",
            )
        self._cached_meta: DatasetMetadata | None = None
        self._cached_path: Path | None = None

    # ------------------------------------------------------------------
    # AbstractConnector interface
    # ------------------------------------------------------------------

    def connect(self) -> None:
        """Verify the OECD API is reachable with a lightweight ping."""
        _requests = self._import_requests()
        dataflow = self.params["dataflow"]
        url = f"{_API_BASE}/dataflow/OECD.SDD.NAD/{dataflow}?format=sdmx-json"
        try:
            resp = _requests.get(url, timeout=int(self.params.get("timeout", 30)))
            # 200 or 404 both indicate the API is reachable
            if resp.status_code not in (200, 404):
                resp.raise_for_status()
        except Exception as exc:
            raise ConnectorError(
                f"Cannot reach OECD API at {_API_BASE}.",
                connector_id="oecd",
                cause=exc,
            ) from exc

    def download(self, *, force: bool = False) -> Path:
        """Download the configured dataflow and write a tidy long-format CSV."""
        key = self.cache_key()

        if self.cache_manager is not None and not force:
            if self.cache_manager.is_cached(key):
                path, meta = self.cache_manager.retrieve(key)
                self._cached_path = path
                self._cached_meta = meta
                return path

        _requests = self._import_requests()
        dataflow = self.params["dataflow"]
        filter_expr = str(self.params.get("filter", "all"))
        start = self.params.get("start_period")
        end = self.params.get("end_period")
        entity_col = str(self.params.get("entity_col", "country"))
        time_col = str(self.params.get("time_col", "year"))
        timeout = int(self.params.get("timeout", 60))

        # Build URL with OECD agency and dataflow
        url = (
            f"{_API_BASE}/data/OECD.SDD.NAD,{dataflow}/{filter_expr}"
            f"?format=sdmx-json&dimensionAtObservation=TIME_PERIOD"
        )
        if start:
            url += f"&startPeriod={start}"
        if end:
            url += f"&endPeriod={end}"

        try:
            resp = _requests.get(url, timeout=timeout)
            resp.raise_for_status()
            payload = resp.json()
        except Exception as exc:
            raise ConnectorError(
                f"Failed to download OECD dataflow {dataflow!r}.",
                connector_id="oecd",
                cause=exc,
            ) from exc

        rows = self._parse_sdmx_json(payload, entity_col=entity_col, time_col=time_col)

        import tempfile
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, encoding="utf-8", newline=""
        ) as tmp:
            fieldnames = [entity_col, time_col, "indicator", "value", "measure"]
            writer = csv.DictWriter(tmp, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)
            tmp_path = Path(tmp.name)

        meta = DatasetMetadata.now(
            connector_id="oecd",
            source="OECD SDMX-JSON API",
            url=url,
            version=_VERSION,
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
            check_duplicates=False,
            check_missing_identifiers=True,
        )
        return DataValidator(config).validate_path(path)

    def metadata(self) -> DatasetMetadata:
        if self._cached_meta is None:
            raise ConnectorError(
                "No metadata available. Call download() first.",
                connector_id="oecd",
            )
        return self._cached_meta

    def cache_key(self) -> str:
        return self._make_cache_key()

    def citation(self) -> str:
        return _CITATION

    def version(self) -> str:
        return _VERSION

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _import_requests(self) -> Any:
        try:
            import requests  # noqa: PLC0415
            return requests
        except ImportError as exc:
            raise ConnectorError(
                "OECDConnector requires 'requests'. Install with: pip install requests",
                connector_id="oecd",
                cause=exc,
            ) from exc

    def _parse_sdmx_json(
        self,
        payload: dict[str, Any],
        *,
        entity_col: str,
        time_col: str,
    ) -> list[dict[str, str]]:
        """
        Flatten an SDMX-JSON response into a list of row dicts.

        Handles the OECD v1.0 SDMX-JSON envelope structure where observations
        are nested under datasets -> series -> observations.
        """
        rows: list[dict[str, str]] = []

        try:
            data_section = payload.get("data", payload)

            # Extract structure dimensions
            structures = data_section.get("structures", [{}])
            if not structures:
                return rows
            structure = structures[0] if isinstance(structures, list) else structures
            dims = structure.get("dimensions", {}).get("series", [])
            obs_dims = structure.get("dimensions", {}).get("observation", [])

            # Build lookup tables for each dimension
            dim_values: list[list[str]] = []
            for d in dims:
                vals = [v.get("id", str(i)) for i, v in enumerate(d.get("values", []))]
                dim_values.append(vals)

            # Time period values from observation dimensions
            time_values: list[str] = []
            for od in obs_dims:
                if "TIME" in od.get("id", "").upper() or od.get("id") == "TIME_PERIOD":
                    time_values = [v.get("id", str(i)) for i, v in enumerate(od.get("values", []))]

            # Attribute id lookup (for MEASURE dimension)
            measure_idx: int | None = None
            for i, d in enumerate(dims):
                if d.get("id", "").upper() in ("MEASURE", "INDICATOR"):
                    measure_idx = i

            # country dimension index
            country_idx: int | None = None
            for i, d in enumerate(dims):
                cid = d.get("id", "").upper()
                if cid in ("LOCATION", "COUNTRY", "REF_AREA", "COUNTERPART_AREA"):
                    country_idx = i

            datasets = data_section.get("dataSets", [data_section])
            for dataset in datasets:
                series_map = dataset.get("series", {})
                dataflow_id = str(self.params.get("dataflow", ""))
                for key_str, series_data in series_map.items():
                    key_parts = [int(k) for k in key_str.split(":")]

                    # Decode country
                    country = ""
                    if country_idx is not None and country_idx < len(key_parts):
                        ci = key_parts[country_idx]
                        if ci < len(dim_values[country_idx]):
                            country = dim_values[country_idx][ci]

                    # Decode measure/indicator
                    measure = ""
                    if measure_idx is not None and measure_idx < len(key_parts):
                        mi = key_parts[measure_idx]
                        if mi < len(dim_values[measure_idx]):
                            measure = dim_values[measure_idx][mi]

                    observations = series_data.get("observations", {})
                    for obs_idx_str, obs_values in observations.items():
                        obs_idx = int(obs_idx_str)
                        time_val = (
                            time_values[obs_idx]
                            if obs_idx < len(time_values)
                            else str(obs_idx)
                        )
                        value = obs_values[0] if obs_values else None
                        rows.append({
                            entity_col: country,
                            time_col: time_val,
                            "indicator": dataflow_id,
                            "value": "" if value is None else str(value),
                            "measure": measure,
                        })
        except Exception as exc:
            raise ConnectorError(
                f"Failed to parse OECD SDMX-JSON response: {exc}",
                connector_id="oecd",
                cause=exc,
            ) from exc

        return rows
