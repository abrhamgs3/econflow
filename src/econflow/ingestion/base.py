"""
econflow.ingestion.base — Abstract connector interface.

All data-source connectors must subclass :class:`AbstractConnector` and
implement its five abstract methods.  This contract ensures:

* A uniform call signature so the pipeline can swap connectors without
  touching downstream code.
* Deterministic caching via :meth:`cache_key`.
* Self-describing metadata via :meth:`metadata`.
* Configurable validation via :meth:`validate`.

Connector lifecycle
-------------------
::

    connector = MyConnector(params={...}, cache_manager=cache)
    connector.connect()                    # 1. verify connectivity / file access
    path = connector.download()            # 2. fetch & cache -> local CSV path
    report = connector.validate(path)      # 3. structural + quality checks
    meta = connector.metadata()            # 4. provenance metadata

Or use the convenience wrapper::

    path, meta = connector.fetch()         # steps 1-4 combined

Raising errors
--------------
All connector methods should raise :class:`ConnectorError` on failure.
Do not raise raw ``OSError``, ``requests.RequestException``, or other
library-specific exceptions -- wrap them.
"""

from __future__ import annotations

import abc
from pathlib import Path
from typing import Any

from econflow.ingestion.metadata import DatasetMetadata

# ---------------------------------------------------------------------------
# Domain exception
# ---------------------------------------------------------------------------

class ConnectorError(Exception):
    """
    Raised when a connector cannot complete an operation.

    Wraps network errors, file-not-found errors, authentication failures,
    and unexpected API responses so callers only need to catch one type.

    Attributes
    ----------
    connector_id:
        The ID of the connector that raised the error.
    cause:
        The original exception, if any.
    """

    def __init__(
        self,
        message: str,
        *,
        connector_id: str = "",
        cause: BaseException | None = None,
    ) -> None:
        super().__init__(message)
        self.connector_id = connector_id
        self.cause = cause

    def __str__(self) -> str:
        base = super().__str__()
        if self.connector_id:
            base = f"[{self.connector_id}] {base}"
        if self.cause:
            base = f"{base}  (caused by: {type(self.cause).__name__}: {self.cause})"
        return base


# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------

class AbstractConnector(abc.ABC):
    """
    Abstract base class for all EconFlow data-source connectors.

    Subclass this and implement all five abstract methods.  Register the
    subclass with :func:`~econflow.ingestion.registry.register` to make it
    available via ``econflow info`` and
    :func:`~econflow.ingestion.registry.get_connector`.

    Parameters
    ----------
    params:
        Connector-specific parameters (indicators, countries, year range,
        file path, API key, etc.).  Stored as ``self.params``.
    cache_manager:
        Optional :class:`~econflow.ingestion.cache.CacheManager`.  When
        provided, :meth:`download` should check the cache before hitting
        the network and store results after downloading.
    """

    #: Short identifier; set automatically by @register().
    connector_id: str = ""
    #: Human-readable label.
    label: str = ""

    def __init__(
        self,
        params: dict[str, Any] | None = None,
        cache_manager: Any | None = None,
    ) -> None:
        self.params: dict[str, Any] = params or {}
        self.cache_manager = cache_manager

    # ------------------------------------------------------------------
    # Abstract interface (all subclasses must implement)
    # ------------------------------------------------------------------

    @abc.abstractmethod
    def connect(self) -> None:
        """
        Verify that the data source is accessible.

        For network connectors: perform a lightweight ping or auth check.
        For file connectors: verify the file exists and is readable.

        Raises
        ------
        ConnectorError
            If the source is not reachable.
        """

    @abc.abstractmethod
    def download(self, *, force: bool = False) -> Path:
        """
        Fetch data from the source and return the path to a local CSV.

        The returned CSV must have a header row and be UTF-8 encoded.
        If a :attr:`cache_manager` is set, the result must be stored in
        the cache.  Subsequent calls with ``force=False`` should return
        the cached copy without re-downloading.

        Parameters
        ----------
        force:
            If ``True``, bypass the cache and re-download.

        Returns
        -------
        Path
            Absolute path to the cached CSV file.

        Raises
        ------
        ConnectorError
            On download failure.
        """

    @abc.abstractmethod
    def validate(self, path: Path) -> Any:
        """
        Run structural and quality checks on the downloaded CSV at *path*.

        Parameters
        ----------
        path:
            Path to the CSV to validate.

        Returns
        -------
        DataValidationReport
            Report describing any issues found.
        """

    @abc.abstractmethod
    def metadata(self) -> DatasetMetadata:
        """
        Return provenance metadata for the most recently downloaded dataset.

        Must be called after :meth:`download`.

        Returns
        -------
        DatasetMetadata
            Populated metadata record.
        """

    @abc.abstractmethod
    def cache_key(self) -> str:
        """
        Return a deterministic cache key for this connector + params combination.

        The key must be deterministic, collision-resistant, and filesystem-safe.
        A good default is to SHA-256 hash a canonical JSON of the connector id
        and sorted params (see :meth:`_make_cache_key`).

        Returns
        -------
        str
            A filesystem-safe string (e.g. a hex digest).
        """

    # ------------------------------------------------------------------
    # Concrete convenience method
    # ------------------------------------------------------------------

    def fetch(self, *, force: bool = False) -> tuple[Path, DatasetMetadata]:
        """
        Run the full download -> validate -> metadata lifecycle.

        Parameters
        ----------
        force:
            Passed through to :meth:`download`.

        Returns
        -------
        tuple[Path, DatasetMetadata]
            ``(path_to_csv, metadata)``.
        """
        self.connect()
        path = self.download(force=force)
        self.validate(path)
        meta = self.metadata()
        return path, meta

    # ------------------------------------------------------------------
    # Helpers available to all subclasses
    # ------------------------------------------------------------------

    def _make_cache_key(self, extra: dict[str, Any] | None = None) -> str:
        """
        Default cache key: SHA-256 of connector_id + sorted params.

        Subclasses may use this helper or provide their own implementation.
        """
        import hashlib
        import json

        payload = {
            "connector_id": self.connector_id,
            "params": {k: self.params[k] for k in sorted(self.params)},
        }
        if extra:
            payload.update(extra)
        encoded = json.dumps(payload, sort_keys=True, ensure_ascii=True)
        return hashlib.sha256(encoded.encode()).hexdigest()

    def __repr__(self) -> str:
        return (
            f"<{self.__class__.__name__} "
            f"connector_id={self.connector_id!r} "
            f"params={self.params!r}>"
        )
