"""
econflow.diagnostics — Post-estimation diagnostic plugin framework.

Public API
----------
.. autoclass:: econflow.diagnostics.base.BaseDiagnostic
.. autoclass:: econflow.diagnostics.base.DiagnosticError
.. autofunction:: econflow.diagnostics.registry.register_diagnostic
.. autofunction:: econflow.diagnostics.registry.get_diagnostic
.. autofunction:: econflow.diagnostics.registry.list_diagnostics
"""

from __future__ import annotations

# Trigger self-registration of all built-in plugins
import econflow.diagnostics.plugins  # noqa: F401
from econflow.diagnostics.base import BaseDiagnostic, DiagnosticError
from econflow.diagnostics.registry import (
    get_diagnostic,
    list_diagnostics,
    register_diagnostic,
    unregister_diagnostic,
)

__all__ = [
    "BaseDiagnostic",
    "DiagnosticError",
    "register_diagnostic",
    "get_diagnostic",
    "list_diagnostics",
    "unregister_diagnostic",
]
