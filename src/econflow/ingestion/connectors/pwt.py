"""
econflow.ingestion.connectors.pwt -- Penn World Tables connector (stub).

Downloads the Penn World Tables (PWT) panel dataset from the official
Groningen Growth and Development Centre (GGDC) release page.

Reference
---------
* PWT homepage: https://www.rug.nl/ggdc/productivity/pwt/
* PWT 10.01 Excel: https://dataverse.harvard.edu/dataset.xhtml?persistentId=doi:10.7910/DVN/61LOLE

Usage
-----
::

    from econflow.ingestion.connectors import PennWorldTablesConnector
    from econflow.ingestion.cache import CacheManager

    cache = CacheManager(".cache/econflow")
    conn = PennWorldTablesConnector(
        params={
            "version": "10.01",
            "variables": ["rgdpna", "emp", "avh", "rkna"],
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

# PWT release URLs keyed by version string.
# Update this dict when new PWT versions are released.
_PWT_URLS: dict[str, str] = {
    "10.01": (
        "https://dataverse.harvard.edu/api/access/datafile/"
        ":persistentId?persistentId=doi:10.7910/DVN/61LOLE/RWKJTZ"
    ),
    "10.0": (
        "https://dataverse.harvard.edu/api/access/datafile/"
        ":persistentId?persistentId=doi:10.7910/DVN/61LOLE/RWKJTZ"
    ),
}
_DEFAULT_VERSION = "10.01"

_CITATION = (
    "Feenstra, R.C., Inklaar, R., and Timmer, M.P. (2015). "
    "'The Next Generation of the Penn World Table.' "
    "American Economic Review, 105(10), pp.3150-82. "
    "Available for download at www.ggdc.net/pwt"
)


@register(
    "pwt",
    label="Penn World Tables",
    status="stub",
    notes="PWT 10.01; Excel download from Harvard Dataverse; stub implementation",
)
class PennWorldTablesConnector(AbstractConnector):
    """
    Connector for the Penn World Tables (PWT).

    Parameters (``params`` dict keys)
    -----------------------------------
    version : str
        PWT version to download (e.g. ``"10.01"``).
        Supported versions: ``"10.0"``, ``"10.01"``.
        Defaults to ``"10.01"``.
    variables : list[str] | None
        List of PWT variable codes to include in the output CSV.
        ``None`` returns all variables.  Useful variable codes:

        * ``"rgdpna"``  — Real GDP at constant 2017 national prices (in mil. 2017 USD)
        * ``"emp"``     — Number of persons engaged (in millions)
        * ``"avh"``     — Average annual hours worked by persons engaged
        * ``"rkna"``    — Capital stock at constant 2017 national prices (in mil. 2017 USD)
        * ``"rtfpna"``  — TFP at constant national prices (2017=1)
        * ``"labsh"``   — Share of labour compensation in GDP at current national prices
    entity_col : str
        Column name for the country dimension in output.  Default ``"country"``.
    time_col : str
        Column name for the time dimension in output.  Default ``"year"``.

    Implementation notes
    ---------------------
    PWT is distributed as an Excel (.xlsx) file from Harvard Dataverse.
    The ``data`` sheet contains all variables; the ``legend`` sheet documents
    variable codes and units.

    Stub implementation plan:

    1. ``connect()`` — HTTP HEAD request on the download URL to confirm
       accessibility (no auth required for Dataverse public datasets).
    2. ``download()`` — Stream the .xlsx file to a temp path, parse with
       ``openpyxl`` or ``pandas``, select the ``data`` sheet, optionally
       filter to ``params["variables"]``, reshape to long format, write to CSV.
       Cache via ``CacheManager`` if provided.
    3. Column mapping: PWT uses ``countrycode`` (ISO-3) and ``year`` already.
       Rename to ``entity_col`` / ``time_col`` if configured.

    Dependencies needed for full implementation:
    * ``requests`` — HTTP download
    * ``openpyxl`` or ``pandas[excel]`` — Excel parsing
    """

    def __init__(
        self,
        params: dict[str, Any] | None = None,
        cache_manager: Any | None = None,
    ) -> None:
        super().__init__(params, cache_manager)
        self._version = str(self.params.get("version", _DEFAULT_VERSION))
        if self._version not in _PWT_URLS:
            supported = ", ".join(sorted(_PWT_URLS))
            raise ConnectorError(
                f"PWT version {self._version!r} is not supported.  "
                f"Supported versions: {supported}",
                connector_id="pwt",
            )
        self._download_url = _PWT_URLS[self._version]

    # ------------------------------------------------------------------
    # AbstractConnector interface
    # ------------------------------------------------------------------

    def connect(self) -> None:
        """
        Verify the PWT download URL is reachable.

        **Not yet implemented.**
        """
        raise NotImplementedError(
            "PennWorldTablesConnector.connect() is not yet implemented.  "
            "This connector is a documented stub.  "
            "See the module docstring for the implementation plan."
        )

    def download(self, *, force: bool = False) -> Path:
        """
        Download the PWT Excel file and write a tidy long-format CSV.

        **Not yet implemented.**
        """
        raise NotImplementedError(
            "PennWorldTablesConnector.download() is not yet implemented.  "
            "This connector is a documented stub.  "
            "See the module docstring for the implementation plan."
        )

    def validate(self, path: Path) -> DataValidationReport:
        """Validate the downloaded long-format CSV."""
        entity_col = str(self.params.get("entity_col", "country"))
        time_col = str(self.params.get("time_col", "year"))
        variables = self.params.get("variables") or []
        required = [entity_col, time_col] + list(variables)
        config = DataValidationConfig(
            required_columns=required,
            entity_col=entity_col,
            time_col=time_col,
            check_duplicates=True,
            check_missing_identifiers=True,
        )
        return DataValidator(config).validate_path(path)

    def metadata(self) -> DatasetMetadata:
        """
        Return dataset metadata.

        Raises ``ConnectorError`` if ``download()`` has not been called.
        """
        raise ConnectorError(
            "PennWorldTablesConnector.download() has not been called (stub).",
            connector_id="pwt",
        )

    def cache_key(self) -> str:
        return self._make_cache_key({"version": self._version})

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    @staticmethod
    def list_versions() -> list[str]:
        """Return the PWT version strings that this connector supports."""
        return sorted(_PWT_URLS)

    @property
    def download_url(self) -> str:
        """Resolved download URL for the configured PWT version."""
        return self._download_url
