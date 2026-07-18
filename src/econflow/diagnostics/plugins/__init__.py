"""
econflow.diagnostics.plugins — Built-in diagnostic plugins.

Importing this package triggers @register_diagnostic() for all built-in
diagnostics.  econflow.diagnostics.__init__ imports this package
automatically.
"""

from econflow.diagnostics.plugins.breusch_pagan import BreuschPagan
from econflow.diagnostics.plugins.hausman import HausmanTest
from econflow.diagnostics.plugins.pesaran_cd import PesaranCD
from econflow.diagnostics.plugins.serial_correlation import SerialCorrelationTest
from econflow.diagnostics.plugins.vif import VIFCheck
from econflow.diagnostics.plugins.wooldridge import WooldridgeTest

__all__ = [
    "HausmanTest",
    "BreuschPagan",
    "PesaranCD",
    "VIFCheck",
    "WooldridgeTest",
    "SerialCorrelationTest",
]
