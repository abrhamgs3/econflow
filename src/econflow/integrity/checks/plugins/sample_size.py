"""
econflow.integrity.checks.plugins.sample_size

Checks that the estimation sample meets minimum observation thresholds.

Pass:  nobs ≥ warn_threshold
Warn:  fail_threshold ≤ nobs < warn_threshold
Fail:  nobs < fail_threshold
"""

from __future__ import annotations

from econflow.estimation.result import EstimationResult
from econflow.integrity.checks.base import BaseIntegrityCheck, IntegrityCheckResult
from econflow.integrity.checks.registry import register_integrity_check

_DEFAULT_WARN = 30
_DEFAULT_FAIL = 10


@register_integrity_check(
    "sample_size",
    label="Sample Size Adequacy",
    notes="Checks that nobs meets minimum thresholds for reliable inference",
)
class SampleSizeCheck(BaseIntegrityCheck):
    """
    Verifies that the estimation sample is large enough for reliable inference.

    Parameters
    ----------
    warn_threshold:
        Minimum recommended observations (default 30).
    fail_threshold:
        Absolute minimum observations (default 10).
    """

    check_id = "sample_size"
    name = "Sample Size Adequacy"
    description = (
        "Checks that the number of observations meets thresholds for "
        "reliable asymptotic inference.  Very small samples undermine "
        "the validity of standard errors and p-values."
    )
    supported_estimators = ["*"]

    def run(
        self,
        result: EstimationResult,
        *,
        warn_threshold: int = _DEFAULT_WARN,
        fail_threshold: int = _DEFAULT_FAIL,
        **kwargs: object,
    ) -> IntegrityCheckResult:
        nobs = result.nobs
        if nobs is None:
            return self._not_applicable("nobs not available in EstimationResult")

        n = int(nobs)

        if n < fail_threshold:
            return self._fail(
                f"Sample size n={n} is below the minimum threshold "
                f"({fail_threshold}).  Inference results are unreliable.",
                nobs=n,
                warn_threshold=warn_threshold,
                fail_threshold=fail_threshold,
            )
        if n < warn_threshold:
            return self._warn(
                f"Sample size n={n} is below the recommended threshold "
                f"({warn_threshold}).  Results should be interpreted cautiously.",
                nobs=n,
                warn_threshold=warn_threshold,
                fail_threshold=fail_threshold,
            )

        return self._pass(
            f"Sample size n={n} meets adequacy thresholds.",
            nobs=n,
            warn_threshold=warn_threshold,
            fail_threshold=fail_threshold,
        )
