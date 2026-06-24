"""
econflow.ingestion.pwt — Penn World Tables (PWT) connector.

Downloads the Penn World Tables Excel release (currently PWT 10.01) from the
Groningen Growth and Development Centre website and exposes selected variables.

Key PWT variables
-----------------
* ``rtfpna``  — TFP at constant national prices (2017=1)
* ``ctfp``    — TFP level at current PPPs (USA=1)
* ``cgdpo``   — Output-side real GDP at current PPPs (mil. 2017 USD)
* ``emp``     — Number of persons engaged (millions)
* ``hc``      — Human capital index

Usage (once implemented)
-------------------------
    from econflow.ingestion.pwt import PennWorldTablesConnector
    conn = PennWorldTablesConnector(config)
    df = conn.fetch(indicators=["rtfpna", "ctfp"], year_start=2000, year_end=2019)
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from econflow.core.config import DataSourceConfig
from econflow.ingestion.base import BaseConnector


_PWT_DOWNLOAD_URL = (
    "https://www.rug.nl/ggdc/docs/pwt1001.xlsx"
)
_PWT_SHEET = "Data"


class PennWorldTablesConnector(BaseConnector):
    """
    Connector for Penn World Tables (bulk Excel download).

    Parameters
    ----------
    config:
        ``base_url`` may point to a local cached copy of the PWT Excel file.
        ``indicators`` lists PWT column names to extract.
    cache:
        Optional download cache; the raw Excel file is large (~5 MB) and
        caching it avoids repeated downloads.
    """

    source_name = "pwt"

    def __init__(self, config: DataSourceConfig, cache: object | None = None) -> None:
        super().__init__(config, cache)
        self._download_url = config.base_url or _PWT_DOWNLOAD_URL

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
        Load PWT data and return a tidy long-format DataFrame.

        Downloads the Excel file if not cached, reads the ``Data`` sheet,
        filters to requested *indicators*, *countries*, and year range, then
        melts to long format with columns ``["iso3", "year", "indicator",
        "value"]``.
        """
        raise NotImplementedError

    def validate(self, df: pd.DataFrame) -> None:
        """
        Verify column presence and value ranges for key PWT indicators.

        Raises
        ------
        econflow.core.exceptions.IngestionError
            If required indicators are absent or TFP values are non-positive.
        """
        raise NotImplementedError

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _download_excel(self, dest: Path) -> Path:
        """Download the PWT Excel file to *dest* and return the path."""
        raise NotImplementedError

    def _read_excel(self, path: Path) -> pd.DataFrame:
        """Read the PWT Excel ``Data`` sheet into a wide-format DataFrame."""
        raise NotImplementedError
