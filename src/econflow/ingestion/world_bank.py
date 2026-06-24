"""
econflow.ingestion.world_bank — World Bank Open Data connector.

Fetches indicator time series from the World Bank API v2
(``https://api.worldbank.org/v2/``).  Supports pagination and stores raw
JSON responses in the :class:`~econflow.ingestion.cache.DownloadCache` to avoid
redundant network calls.

Indicators of interest (examples)
-----------------------------------
* ``IT.NET.USER.ZS``  — Individuals using the Internet (% of population)
* ``GB.XPD.RSDV.GD.ZS`` — R&D expenditure (% of GDP)
* ``NE.GDI.TOTL.ZS``  — Gross capital formation (% of GDP)

Usage (once implemented)
-------------------------
    from econflow.ingestion.world_bank import WorldBankConnector
    conn = WorldBankConnector(config)
    df = conn.fetch(indicators=["IT.NET.USER.ZS"], year_start=2000, year_end=2022)
"""

from __future__ import annotations

import pandas as pd

from econflow.core.config import DataSourceConfig
from econflow.ingestion.base import BaseConnector


_DEFAULT_BASE_URL = "https://api.worldbank.org/v2"


class WorldBankConnector(BaseConnector):
    """
    Connector for the World Bank Open Data API (v2).

    Parameters
    ----------
    config:
        Must include ``base_url`` (optional, falls back to the public API)
        and ``indicators`` (list of WB indicator codes).
    cache:
        Optional download cache.
    """

    source_name = "world_bank"

    def __init__(self, config: DataSourceConfig, cache: object | None = None) -> None:
        super().__init__(config, cache)
        self._base_url = config.base_url or _DEFAULT_BASE_URL

    # ------------------------------------------------------------------
    # BaseConnector interface
    # ------------------------------------------------------------------

    def fetch(
        self,
        indicators: list[str] | None = None,
        countries: list[str] | None = None,
        year_start: int | None = None,
        year_end: int | None = None,
    ) -> pd.DataFrame:
        """
        Download World Bank indicator data and return a tidy long-format frame.

        Iterates over *indicators*, issues paginated requests to the WB API,
        and concatenates results into a single DataFrame with columns
        ``["iso3", "year", "indicator", "value"]``.
        """
        raise NotImplementedError

    def validate(self, df: pd.DataFrame) -> None:
        """
        Verify that *df* has the expected columns and no fully-null series.

        Raises
        ------
        econflow.core.exceptions.IngestionError
            On schema or completeness violations.
        """
        raise NotImplementedError

    # ------------------------------------------------------------------
    # Internal helpers (private)
    # ------------------------------------------------------------------

    def _build_url(self, indicator: str, country: str = "all") -> str:
        """Construct the WB API endpoint URL for *indicator* and *country*."""
        raise NotImplementedError

    def _parse_response(self, raw: list) -> pd.DataFrame:
        """Convert a WB API JSON response list to a tidy DataFrame."""
        raise NotImplementedError
