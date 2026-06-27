"""
econflow.ingestion.connectors.oecd -- OECD SDMX-JSON connector (stub).

Downloads indicator data from the OECD SDMX-JSON API.
Full implementation requires registering for an OECD API key and
familiarising yourself with the SDMX 2.1 dataflow structure.

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
            "dataflow": "EDU_GRADUATION_RATE",
            "filter": "AUS+CAN+FRA..",
            "start_period": "2010",
            "end_period": "2022",
        },
        cache_manager=cache,
    )
    path, meta = conn.fetch()

Status: ``stub`` — interface is complete; download logic is not yet
implemented.  Calling :meth:`connect` or :meth:`download` raises
``NotImplementedError``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from econflow.ingestion.base import AbstractConnector, ConnectorError
from econflow.ingestion.metadata import DatasetMetadata
from econflow.ingestion.registry import register
from econflow.ingestion.validation import DataValidationConfig, DataValidationReport, DataValidator

_API_BASE = "https://sdmx.oecd.org/public/rest"
_CITATION = (
    "OECD (2024). OECD.Stat Web Browser. "
    "Organisation for Economic Co-operation and Development. "
    "https://stats.oecd.org"
)


@register(
    "oecd",
    label="OECD SDMX-JSON API",
    status="stub",
    notes="SDMX 2.1 dataflow; requires OECD API key; stub implementation",
)
class OECDConnector(AbstractConnector):
    """
    Connector for the OECD SDMX-JSON API.

    Parameters (``params`` dict keys)
    -----------------------------------
    dataflow : str
        OECD dataflow identifier (e.g. ``"EDU_GRADUATION_RATE"``).  Required.
    filter : str
        SDMX filter expression (e.g. ``"AUS+CAN+FRA.."``).
        Defaults to ``"all"`` (all members).
    start_period : str | None
        Start period in ISO-8601 or OECD period notation (e.g. ``"2010"``).
    end_period : str | None
        End period in ISO-8601 or OECD period notation (e.g. ``"2022"``).
    entity_col : str
        Column name for the country dimension in output.  Default ``"country"``.
    time_col : str
        Column name for the time dimension in output.  Default ``"year"``.

    .. note::
        The OECD API may require an ``api_key`` parameter for some endpoints.
        Pass it as ``params={"api_key": "<your-key>", ...}``.

    Implementation notes
    ---------------------
    The OECD SDMX-JSON API returns data in a structure of ``series`` keyed by
    a dimension key string.  Dimension metadata is provided separately under
    ``structure.dimensions``.  Parsing requires joining the two sections.

    Stub implementation plan:

    1. ``connect()`` — GET ``{_API_BASE}/dataflow/OECD/{dataflow}?format=sdmx-json``
       and verify a 200 response.
    2. ``download()`` — GET
       ``{_API_BASE}/data/OECD/{dataflow}/{filter}?format=sdmx-json&startPeriod=...``
       parse the SDMX-JSON response structure, flatten into tidy long CSV with
       columns [``entity_col``, ``time_col``, ``indicator``, ``value``].
    3. Cache via ``CacheManager`` if provided.
    """

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

    # ------------------------------------------------------------------
    # AbstractConnector interface
    # ------------------------------------------------------------------

    def connect(self) -> None:
        """
        Verify the OECD API is reachable and the dataflow exists.

        **Not yet implemented.**
        """
        raise NotImplementedError(
            "OECDConnector.connect() is not yet implemented.  "
            "This connector is a documented stub.  "
            "See the module docstring for the implementation plan."
        )

    def download(self, *, force: bool = False) -> Path:
        """
        Download the configured dataflow and write a tidy long-format CSV.

        **Not yet implemented.**
        """
        raise NotImplementedError(
            "OECDConnector.download() is not yet implemented.  "
            "This connector is a documented stub.  "
            "See the module docstring for the implementation plan."
        )

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
        """
        Return dataset metadata.

        Raises ``ConnectorError`` if ``download()`` has not been called.
        """
        raise ConnectorError(
            "OECDConnector.download() has not been called (stub).",
            connector_id="oecd",
        )

    def cache_key(self) -> str:
        return self._make_cache_key()
