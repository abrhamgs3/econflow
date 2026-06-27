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

Cache
~~~~~
.. autoclass:: econflow.ingestion.cache.CacheManager
.. autoclass:: econflow.ingestion.cache.CacheCorruptionError

Metadata
~~~~~~~~
.. autoclass:: econflow.ingestion.metadata.DatasetMetadata

Validation
~~~~~~~~~~
.. autoclass:: econflow.ingestion.validation.DataValidator
.. autoclass:: econflow.ingestion.validation.DataValidationConfig
.. autoclass:: econflow.ingestion.validation.DataValidationReport
.. autoclass:: econflow.ingestion.validation.ValidationIssue
"""

from __future__ import annotations

# Import all built-in connectors so they self-register via @register().
# This must come after the registry is imported.
import econflow.ingestion.connectors  # noqa: E402, F401

# Core abstractions
from econflow.ingestion.base import AbstractConnector, ConnectorError

# Cache layer
from econflow.ingestion.cache import CacheCorruptionError, CacheManager

# Dataset metadata
from econflow.ingestion.metadata import DatasetMetadata

# Registry
from econflow.ingestion.registry import get_connector, list_connectors, register

# Validation
from econflow.ingestion.validation import (
    DataValidationConfig,
    DataValidationReport,
    DataValidator,
    ValidationIssue,
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
    # Registry
    "register",
    "get_connector",
    "list_connectors",
    # Validation
    "DataValidator",
    "DataValidationConfig",
    "DataValidationReport",
    "ValidationIssue",
]
