"""
econflow.integrity.checks.base — Abstract integrity check interface.

Integrity checks are post-estimation tests that assess research quality
signals such as coefficient plausibility, sample sufficiency, and p-value
distribution health.

Adding a new check
------------------
1. Create ``econflow/integrity/checks/plugins/my_check.py``.
2. Inherit from :class:`BaseIntegrityCheck`.
3. Set class attributes: ``check_id``, ``name``, ``description``,
   ``supported_estimators``.
4. Implement :meth:`run`.
5. Decorate with ``@register_integrity_check("my_check", ...)``.
6. Add the import to ``econflow/integrity/checks/plugins/__init__.py``.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import Any

from econflow.estimation.result import EstimationResult

# ---------------------------------------------------------------------------
# IntegrityCheckResult
# ---------------------------------------------------------------------------


@dataclass
class IntegrityCheckResult:
    """
    Result produced by a single :class:`BaseIntegrityCheck` run.

    Parameters
    ----------
    check_id:
        Registry key of the check that produced this result.
    name:
        Human-readable check name.
    status:
        ``"pass"``, ``"warn"``, ``"fail"``, or ``"skip"``.
    message:
        Short human-readable explanation.
    extra:
        Arbitrary supplementary data (thresholds, observed values, etc.).
    """

    check_id: str
    name: str
    status: str = "pass"      # "pass" | "warn" | "fail" | "skip"
    message: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "check_id": self.check_id,
            "name": self.name,
            "status": self.status,
            "message": self.message,
            "extra": self.extra,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> IntegrityCheckResult:
        return cls(
            check_id=str(data.get("check_id", "")),
            name=str(data.get("name", "")),
            status=str(data.get("status", "pass")),
            message=str(data.get("message", "")),
            extra=dict(data.get("extra") or {}),
        )


# ---------------------------------------------------------------------------
# BaseIntegrityCheck
# ---------------------------------------------------------------------------


class BaseIntegrityCheck(abc.ABC):
    """
    Abstract base for all EconFlow integrity check plugins.

    Class attributes
    ----------------
    check_id:
        Short registry key set by ``@register_integrity_check()``
        (e.g. ``"coefficient_stability"``).
    name:
        Human-readable check name.
    description:
        One-paragraph description of what the check assesses.
    supported_estimators:
        List of estimator IDs this check can run on.
        Use ``["*"]`` to support all estimators.
    """

    check_id: str = "base"
    name: str = "BaseIntegrityCheck"
    description: str = ""
    supported_estimators: list[str] = ["*"]

    # ------------------------------------------------------------------
    # Abstract interface
    # ------------------------------------------------------------------

    @abc.abstractmethod
    def run(
        self,
        result: EstimationResult,
        **kwargs: Any,
    ) -> IntegrityCheckResult:
        """
        Run the integrity check on *result*.

        Parameters
        ----------
        result:
            A fitted :class:`~econflow.estimation.result.EstimationResult`.
        **kwargs:
            Check-specific keyword arguments (e.g. custom thresholds).

        Returns
        -------
        IntegrityCheckResult
        """

    # ------------------------------------------------------------------
    # Concrete helpers
    # ------------------------------------------------------------------

    def supports(self, estimator_id: str) -> bool:
        """Return ``True`` if this check supports *estimator_id*."""
        if self.supported_estimators == ["*"]:
            return True
        return estimator_id in self.supported_estimators

    def _not_applicable(self, reason: str = "") -> IntegrityCheckResult:
        """Return a skipped / not-applicable result."""
        return IntegrityCheckResult(
            check_id=self.check_id,
            name=self.name,
            status="skip",
            message=f"Not applicable: {reason}" if reason else "Not applicable.",
        )

    def _pass(self, message: str = "", **extra: Any) -> IntegrityCheckResult:
        """Return a passing result."""
        return IntegrityCheckResult(
            check_id=self.check_id,
            name=self.name,
            status="pass",
            message=message,
            extra=dict(extra),
        )

    def _warn(self, message: str, **extra: Any) -> IntegrityCheckResult:
        """Return a warning result."""
        return IntegrityCheckResult(
            check_id=self.check_id,
            name=self.name,
            status="warn",
            message=message,
            extra=dict(extra),
        )

    def _fail(self, message: str, **extra: Any) -> IntegrityCheckResult:
        """Return a failing result."""
        return IntegrityCheckResult(
            check_id=self.check_id,
            name=self.name,
            status="fail",
            message=message,
            extra=dict(extra),
        )

    def __repr__(self) -> str:
        return (
            f"<{self.__class__.__name__} "
            f"id={self.check_id!r} "
            f"supports={self.supported_estimators}>"
        )
