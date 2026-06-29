"""
econflow.integrity.checks — Integrity check plugin system.

Public API::

    from econflow.integrity.checks import (
        BaseIntegrityCheck,
        IntegrityCheckResult,
        get_check,
        list_checks,
        register_integrity_check,
        unregister_check,
    )
"""

import econflow.integrity.checks.plugins  # noqa: F401 — registers all plugins
from econflow.integrity.checks.base import BaseIntegrityCheck, IntegrityCheckResult
from econflow.integrity.checks.registry import (
    get_check,
    list_checks,
    register_integrity_check,
    unregister_check,
)

__all__ = [
    "BaseIntegrityCheck",
    "IntegrityCheckResult",
    "get_check",
    "list_checks",
    "register_integrity_check",
    "unregister_check",
]
