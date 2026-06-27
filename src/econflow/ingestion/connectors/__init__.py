"""
econflow.ingestion.connectors -- Built-in data source connectors.

Importing this package registers all built-in connectors automatically
via the @register() decorator applied to each class.
"""

from econflow.ingestion.connectors.csv_connector import LocalCSVConnector
from econflow.ingestion.connectors.oecd import OECDConnector
from econflow.ingestion.connectors.pwt import PennWorldTablesConnector
from econflow.ingestion.connectors.world_bank import WorldBankConnector

__all__ = [
    "LocalCSVConnector",
    "WorldBankConnector",
    "OECDConnector",
    "PennWorldTablesConnector",
]
