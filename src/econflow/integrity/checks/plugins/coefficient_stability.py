"""
econflow.integrity.checks.plugins.coefficient_stability

Checks that regression coefficients are within plausible bounds.

Pass:  max |coef| ≤ warn_threshold
Warn:  warn_threshold < max |coef| ≤ fail_threshold, or any NaN/Inf coef
Fail:  max |coef| > fail_threshold
"""

from __future__ import annotations

import math

from econflow.estimation.result import EstimationResult
from econflow.integrity.checks.base import BaseIntegrityCheck, IntegrityCheckResult
from econflow.integrity.checks.registry import register_integrity_check

_DEFAULT_WARN = 100.0
_DEFAULT_FAIL = 1_000.0


@register_integrity_check(
    "coefficient_stability",
    label="Coefficient Stability",
    notes="Checks for extreme or non-finite coefficient values",
)
class CoefficientStabilityCheck(BaseIntegrityCheck):
    """
    Flags extreme or non-finite coefficient values.

    Thresholds are configurable via keyword arguments to :meth:`run`:

    Parameters
    ----------
    warn_threshold:
        ``max |coef|`` above this triggers a warning (default 100).
    fail_threshold:
        ``max |coef|`` above this triggers a failure (default 1000).
    """

    check_id = "coefficient_stability"
    name = "Coefficient Stability"
    description = (
        "Checks that all estimated coefficients are finite and within "
        "plausible magnitude bounds.  Extreme values may indicate "
        "multicollinearity, scale issues, or data problems."
    )
    supported_estimators = ["*"]

    def run(
        self,
        result: EstimationResult,
        *,
        warn_threshold: float = _DEFAULT_WARN,
        fail_threshold: float = _DEFAULT_FAIL,
        **kwargs: object,
    ) -> IntegrityCheckResult:
        params = result.params
        if params is None or len(params) == 0:
            return self._not_applicable("no parameters in EstimationResult")

        values = params.values
        non_finite = [
            str(name)
            for name, v in zip(params.index, values)
            if not math.isfinite(float(v))
        ]
        if non_finite:
            return self._warn(
                f"Non-finite coefficient(s) detected: {non_finite}",
                non_finite=non_finite,
                warn_threshold=warn_threshold,
                fail_threshold=fail_threshold,
            )

        max_abs = float(max(abs(float(v)) for v in values))

        if max_abs > fail_threshold:
            return self._fail(
                f"max |coefficient| = {max_abs:.2f} exceeds fail threshold "
                f"({fail_threshold}).  Check for scale or multicollinearity issues.",
                max_abs_coefficient=max_abs,
                warn_threshold=warn_threshold,
                fail_threshold=fail_threshold,
            )
        if max_abs > warn_threshold:
            return self._warn(
                f"max |coefficient| = {max_abs:.2f} exceeds warn threshold "
                f"({warn_threshold}).  Verify variable scales.",
                max_abs_coefficient=max_abs,
                warn_threshold=warn_threshold,
                fail_threshold=fail_threshold,
            )

        return self._pass(
            f"All coefficients finite; max |coef| = {max_abs:.2f}.",
            max_abs_coefficient=max_abs,
            warn_threshold=warn_threshold,
            fail_threshold=fail_threshold,
        )
