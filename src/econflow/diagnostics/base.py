"""
econflow.diagnostics.base — Abstract diagnostic plugin interface.

Diagnostic plugins are post-estimation tests that operate on an
:class:`~econflow.estimation.result.EstimationResult`.  Each plugin
advertises which estimators it supports and what assumptions it requires,
so the pipeline can automatically skip inapplicable diagnostics.

Adding a new diagnostic
------------------------
1. Create ``econflow/diagnostics/plugins/my_test.py``.
2. Inherit from :class:`BaseDiagnostic`.
3. Set class attributes: ``diagnostic_id``, ``name``,
   ``supported_estimators``, ``required_assumptions``.
4. Implement :meth:`run`.
5. Decorate with ``@register_diagnostic("my_test", ...)``.
6. Add the import to ``econflow/diagnostics/plugins/__init__.py``.
"""

from __future__ import annotations

import abc
from typing import Any

from econflow.estimation.result import DiagnosticResult, EstimationResult


class DiagnosticError(Exception):
    """Raised when a diagnostic cannot complete its computation."""

    def __init__(
        self,
        message: str,
        *,
        diagnostic_id: str = "",
        cause: Exception | None = None,
    ) -> None:
        super().__init__(message)
        self.diagnostic_id = diagnostic_id
        self.cause = cause

    def __str__(self) -> str:
        base = super().__str__()
        if self.diagnostic_id:
            base = f"[{self.diagnostic_id}] {base}"
        if self.cause:
            base = f"{base}\nCaused by: {self.cause!r}"
        return base


class BaseDiagnostic(abc.ABC):
    """
    Abstract base for all EconFlow diagnostic plugins.

    Class attributes
    ----------------
    diagnostic_id:
        Short registry key set by ``@register_diagnostic()`` (e.g. ``"hausman"``).
    name:
        Human-readable name.
    description:
        One-paragraph description of what the test does.
    supported_estimators:
        List of estimator IDs this diagnostic can run on.
        Use ``["*"]`` to support all estimators.
    required_assumptions:
        List of assumptions the test requires (informational only).
    output_schema:
        Dict describing the keys present in ``DiagnosticResult.extra``
        for this diagnostic.
    """

    diagnostic_id: str = "base"
    name: str = "BaseDiagnostic"
    description: str = ""
    supported_estimators: list[str] = ["*"]
    required_assumptions: list[str] = []
    output_schema: dict[str, str] = {}

    # ------------------------------------------------------------------
    # Abstract interface
    # ------------------------------------------------------------------

    @abc.abstractmethod
    def run(
        self,
        result: EstimationResult,
        **kwargs: Any,
    ) -> DiagnosticResult:
        """
        Run the diagnostic on *result* and return a :class:`DiagnosticResult`.

        Parameters
        ----------
        result:
            A fitted :class:`EstimationResult`.
        **kwargs:
            Diagnostic-specific keyword arguments (e.g. alternative
            estimator results for Hausman test).
        """

    # ------------------------------------------------------------------
    # Concrete helpers
    # ------------------------------------------------------------------

    def run_with_context(
        self,
        result: EstimationResult,
        **kwargs: Any,
    ) -> DiagnosticResult:
        """
        Run the diagnostic and stamp ``estimator_id`` from *result*.

        This is the preferred entry-point for pipeline code.  It calls
        :meth:`run` and then sets ``diagnostic_result.estimator_id =
        result.estimator_id`` so that
        :func:`~econflow.outputs.diagnostics_report.build_diagnostics_report`
        can group rows by estimator.

        Parameters
        ----------
        result:
            A fitted :class:`~econflow.estimation.result.EstimationResult`.
        **kwargs:
            Forwarded verbatim to :meth:`run`.

        Returns
        -------
        DiagnosticResult
            The result returned by :meth:`run`, with ``estimator_id`` set.
        """
        diag_result = self.run(result, **kwargs)
        diag_result.estimator_id = result.estimator_id
        return diag_result

    def supports(self, estimator_id: str) -> bool:
        """
        Return ``True`` if this diagnostic supports *estimator_id*.

        Parameters
        ----------
        estimator_id:
            The :attr:`~econflow.estimation.base.BaseEstimator.estimator_id`
            of the estimator whose result will be passed to :meth:`run`.
        """
        if self.supported_estimators == ["*"]:
            return True
        return estimator_id in self.supported_estimators

    def _not_applicable(self, reason: str = "") -> DiagnosticResult:
        """Return a skipped / not-applicable result."""
        return DiagnosticResult(
            diagnostic_id=self.diagnostic_id,
            diagnostic_name=self.name,
            conclusion=f"Not applicable: {reason}" if reason else "Not applicable.",
            level="skip",
        )

    def __repr__(self) -> str:
        return (
            f"<{self.__class__.__name__} "
            f"id={self.diagnostic_id!r} "
            f"supports={self.supported_estimators}>"
        )
