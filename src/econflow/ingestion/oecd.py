"""
econflow.ingestion.oecd — OECD.Stat / SDMX connector.

Retrieves data from the OECD SDMX-JSON API
(``https://stats.oecd.org/SDMX-JSON/data/``).  Key datasets:

* ``MSTI_PUB``    — Main Science and Technology Indicators
* ``ICT_ISIC4``   — ICT sector employment and value-added
* ``NAAG``        — National Accounts at a Glance

Usage (once implemented)
-------------------------
    from econflow.ingestion.oecd import OECDConnector
    conn = OECDConnector(config)
    df = conn.fetch(indicators=["MSTI_PUB.GERD"], year_start=2000, year_end=2022)
"""

from __future__ import annotations

import pandas as pd

from econflow.core.config import DataSourceConfig
from econflow.ingestion.base import BaseConnector

_DEFAULT_BASE_URL = "https://stats.oecd.org/SDMX-JSON/data"


class OECDConnector(BaseConnector):
    """
    Connector for the OECD SDMX-JSON API.

    Parameters
    ----------
    config:
        Source config block; ``indicators`` should be OECD dataset+measure
        strings (e.g. ``"MSTI_PUB.GERD"``).
    cache:
        Optional download cache.
    """

    source_name = "oecd"

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
        Retrieve OECD series and return a tidy long-format DataFrame.

        Returns columns ``["iso3", "year", "indicator", "value"]``.
        """
        raise NotImplementedError

    def validate(self, df: pd.DataFrame) -> None:
        """
        Assert schema and coverage expectations on *df*.

        Raises
        ------
        econflow.core.exceptions.IngestionError
            On violations.
        """
        raise NotImplementedError

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_query(self, dataset: str, measure: str, countries: list[str]) -> str:
        """Compose an SDMX-JSON query URL."""
        raise NotImplementedError

    def _parse_sdmx_json(self, payload: dict) -> pd.DataFrame:
        """Convert an SDMX-JSON response dict to a tidy DataFrame."""
        raise NotImplementedError
