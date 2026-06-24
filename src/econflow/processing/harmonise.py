"""
econflow.processing.harmonise — Country-ID harmonisation.

Normalises country identifiers from heterogeneous source conventions to a
canonical ISO 3166-1 alpha-3 (ISO-3) code.  Handles:

* World Bank ``countrycode`` strings → ISO-3
* OECD ``LOCATION`` codes → ISO-3
* PWT ``countrycode`` → ISO-3 (already aligned but validated here)
* Free-text country names → ISO-3 via a static crosswalk table

The crosswalk is stored in ``econflow/data/iso3_crosswalk.csv`` (bundled with the
package).  Custom additions can be passed as *extra_mapping* at runtime.

Usage (once implemented)
-------------------------
    from econflow.processing.harmonise import CountryHarmoniser
    h = CountryHarmoniser()
    df["iso3"] = h.normalise(df["country_raw"], source="world_bank")
"""

from __future__ import annotations

import pandas as pd


class CountryHarmoniser:
    """
    Normalises raw country identifiers to ISO-3 codes.

    Parameters
    ----------
    extra_mapping:
        Additional ``{raw_id: iso3}`` pairs that extend (or override) the
        built-in crosswalk.
    """

    def __init__(self, extra_mapping: dict[str, str] | None = None) -> None:
        self._crosswalk: dict[str, str] = {}
        self._extra = extra_mapping or {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def normalise(self, series: pd.Series, source: str = "generic") -> pd.Series:
        """
        Map *series* of raw country identifiers to ISO-3 codes.

        Parameters
        ----------
        series:
            String series of country codes or names.
        source:
            Hint about the originating data source (``"world_bank"``,
            ``"oecd"``, ``"pwt"``, ``"generic"``).  Used to select the
            appropriate sub-crosswalk.

        Returns
        -------
        pd.Series
            ISO-3 coded series aligned with *series*.

        Raises
        ------
        econflow.core.exceptions.HarmonisationError
            If any value cannot be mapped and ``strict=True`` (default).
        """
        raise NotImplementedError

    def unmapped(self, series: pd.Series, source: str = "generic") -> pd.Series:
        """Return the subset of *series* that has no crosswalk entry."""
        raise NotImplementedError

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load_crosswalk(self) -> dict[str, str]:
        """Load the bundled ISO-3 crosswalk CSV into a lookup dict."""
        raise NotImplementedError
