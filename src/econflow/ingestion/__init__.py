"""
econflow.ingestion — Data acquisition, caching, validation, and provenance.

Public API
----------
Connectors
~~~~~~~~~~
.. autoclass:: econflow.ingestion.base.AbstractConnector
.. autoclass:: econflow.ingestion.base.ConnectorError
.. autofunction:: econflow.ingestion.registry.register
.. autofunction:: econflow.ingestion.registry.get_connector
.. autofunction:: econflow.ingestion.registry.list_connectors

Built-in connectors
~~~~~~~~~~~~~~~~~~~
.. autoclass:: econflow.ingestion.connectors.csv_connector.LocalCSVConnector
.. autoclass:: econflow.ingestion.connectors.world_bank.WorldBankConnector
.. autoclass:: econflow.ingestion.connectors.oecd.OECDConnector
.. autoclass:: econflow.ingestion.connectors.pwt.PennWorldTablesConnector
.. autoclass:: econflow.ingestion.connectors.fred.FREDConnector

Cache
~~~~~
.. autoclass:: econflow.ingestion.cache.CacheManager
.. autoclass:: econflow.ingestion.cache.CacheCorruptionError

Metadata
~~~~~~~~
.. autoclass:: econflow.ingestion.metadata.DatasetMetadata

Manifest
~~~~~~~~
.. autoclass:: econflow.ingestion.manifest.DatasetManifest
.. autoclass:: econflow.ingestion.manifest.ManifestEntry

Validation
~~~~~~~~~~
.. autoclass:: econflow.ingestion.validation.DataValidator
.. autoclass:: econflow.ingestion.validation.DataValidationConfig
.. autoclass:: econflow.ingestion.validation.DataValidationReport
.. autoclass:: econflow.ingestion.validation.DataValidationIssue
"""

from __future__ import annotations

# Import all built-in connectors so they self-register via @register().
import econflow.ingestion.connectors  # noqa: E402, F401

# Core abstractions
from econflow.ingestion.base import AbstractConnector, ConnectorError

# Cache layer
from econflow.ingestion.cache import CacheCorruptionError, CacheManager

# Manifest
from econflow.ingestion.manifest import DatasetManifest, ManifestEntry

# Dataset metadata
from econflow.ingestion.metadata import DatasetMetadata

# Registry
from econflow.ingestion.registry import (
    get_connector,
    list_connectors,
    register,
    register_connector,
    unregister,
    unregister_connector,
)

# Validation
from econflow.ingestion.validation import (
    DataValidationConfig,
    DataValidationIssue,
    DataValidationReport,
    DataValidator,
    ValidationIssue,  # deprecated alias — kept for backward compat
)

__all__ = [
    # Abstractions
    "AbstractConnector",
    "ConnectorError",
    # Cache
    "CacheManager",
    "CacheCorruptionError",
    # Metadata
    "DatasetMetadata",
    # Manifest
    "DatasetManifest",
    "ManifestEntry",
    # Registry — stable names (register_connector, unregister_connector)
    "register_connector",
    "get_connector",
    "list_connectors",
    "unregister_connector",
    # Deprecated aliases kept for backward compat
    "register",
    "unregister",
    # Validation
    "DataValidator",
    "DataValidationConfig",
    "DataValidationReport",
    "DataValidationIssue",
    # Deprecated alias — will be removed in v2.0; use DataValidationIssue
    "ValidationIssue",
]
