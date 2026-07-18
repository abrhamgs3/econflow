"""
econflow.ingestion.connectors — Built-in connector implementations.

Importing this package triggers auto-registration of all built-in connectors
via the ``@register`` decorator in each module.
"""

from __future__ import annotations

from econflow.ingestion.connectors.csv_connector import LocalCSVConnector
from econflow.ingestion.connectors.fred import FREDConnector
from econflow.ingestion.connectors.oecd import OECDConnector
from econflow.ingestion.connectors.pwt import PennWorldTablesConnector
from econflow.ingestion.connectors.world_bank import WorldBankConnector

__all__ = [
    "LocalCSVConnector",
    "FREDConnector",
    "OECDConnector",
    "PennWorldTablesConnector",
    "WorldBankConnector",
]
