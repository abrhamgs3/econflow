"""
econflow.ingestion.base — Abstract connector interface.

All data-source connectors must subclass :class:`BaseConnector` and implement
its abstract methods.  This ensures a uniform call signature across sources
and allows the pipeline to swap connectors without touching downstream code.

Protocol summary
----------------
1. Instantiate with a :class:`~econflow.core.config.DataSourceConfig`.
2. Call :meth:`fetch` to download data into a local :class:`~pandas.DataFrame`.
3. Call :meth:`validate` to assert schema expectations on the raw frame.
"""

from __future__ import annotations

import abc
from typing import Any

import pandas as pd

from econflow.core.config import DataSourceConfig


class BaseConnector(abc.ABC):
    """
    Abstract base class for all APRP data-source connectors.

    Parameters
    ----------
    config:
        Source-specific configuration block parsed from the project YAML.
    cache:
        Optional :class:`~econflow.ingestion.cache.DownloadCache` instance.
        When provided, :meth:`fetch` should check the cache before hitting
        the network.
    """

    #: Human-readable name for this connector (set by subclasses).
    source_name: str = ""

    def __init__(self, config: DataSourceConfig, cache: Any | None = None) -> None:
        self.config = config
        self.cache = cache

    # ------------------------------------------------------------------
    # Abstract interface
    # ------------------------------------------------------------------

    @abc.abstractmethod
    def fetch(
        self,
        indicators: list[str] | None = None,
        countries: list[str] | None = None,
        year_start: int | None = None,
        year_end: int | None = None,
    ) -> pd.DataFrame:
        """
        Download data from the source and return a tidy long-format DataFrame.

        The returned frame must have at minimum the columns:
        ``["iso3", "year", "indicator", "value"]``.

        Parameters
        ----------
        indicators:
            Variable codes to retrieve.  Falls back to ``config.indicators``
            when *None*.
        countries:
            ISO-3 country codes to filter by.  ``None`` means all available.
        year_start / year_end:
            Inclusive year bounds.
        """

    @abc.abstractmethod
    def validate(self, df: pd.DataFrame) -> None:
        """
        Assert structural expectations on *df*.

        Raises
        ------
        econflow.core.exceptions.IngestionError
            If the frame fails any validation check.
        """

    # ------------------------------------------------------------------
    # Concrete helpers (available to all subclasses)
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} source='{self.source_name}'>"
