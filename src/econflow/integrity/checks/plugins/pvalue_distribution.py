"""
econflow.integrity.checks.plugins.pvalue_distribution

Checks for suspicious p-value distributions that may signal p-hacking.

Pass:  p-value distribution looks healthy (mix of significant/non-significant)
Warn:  unusually high fraction of p-values < 0.05 (possible selective reporting)
Fail:  all p-values are identical, all < 0.001, or all > 0.99
"""

from __future__ import annotations

from econflow.estimation.result import EstimationResult
from econflow.integrity.checks.base import BaseIntegrityCheck, IntegrityCheckResult
from econflow.integrity.checks.registry import register_integrity_check

_DEFAULT_SUSPICIOUS_FRACTION = 0.9   # fraction < 0.05 that triggers a warning
_DEFAULT_MIN_PVALUES = 3             # minimum p-values needed to run this check


@register_integrity_check(
    "pvalue_distribution",
    label="P-value Distribution Health",
    notes="Flags suspicious p-value distributions that may indicate p-hacking",
)
class PvalueDistributionCheck(BaseIntegrityCheck):
    """
    Checks for suspicious patterns in the estimated p-value distribution.

    Parameters
    ----------
    suspicious_fraction:
        If more than this fraction of p-values are < 0.05, emit a warning
        (default 0.9).
    min_pvalues:
        Minimum number of p-values required to run the check (default 3).
    """

    check_id = "pvalue_distribution"
    name = "P-value Distribution Health"
    description = (
        "Checks for suspicious patterns in the distribution of coefficient "
        "p-values: all near-zero, all non-significant, or an unusually high "
        "fraction below 0.05.  These patterns may indicate selective reporting "
        "or p-hacking."
    )
    supported_estimators = ["*"]

    def run(
        self,
        result: EstimationResult,
        *,
        suspicious_fraction: float = _DEFAULT_SUSPICIOUS_FRACTION,
        min_pvalues: int = _DEFAULT_MIN_PVALUES,
        **kwargs: object,
    ) -> IntegrityCheckResult:
        pvalues = result.pvalues
        if pvalues is None or len(pvalues) == 0:
            return self._not_applicable("pvalues not available in EstimationResult")

        pv_list = [float(p) for p in pvalues.values]
        n = len(pv_list)

        if n < min_pvalues:
            return self._not_applicable(
                f"only {n} p-value(s) available; minimum is {min_pvalues}"
            )

        # Check: all p-values identical (pathological)
        if len(set(f"{p:.6f}" for p in pv_list)) == 1:
            return self._fail(
                f"All {n} p-values are identical ({pv_list[0]:.4f}).  "
                "This is highly unusual and may indicate a computation error.",
                n_pvalues=n,
                unique_count=1,
            )

        # Check: all p-values < 0.001 (extreme)
        if all(p < 0.001 for p in pv_list):
            return self._fail(
                f"All {n} p-values are < 0.001.  "
                "This pattern is unusual; verify data scaling and model specification.",
                n_pvalues=n,
                n_below_0001=n,
            )

        # Check: all p-values > 0.99 (suspicious non-significance)
        if all(p > 0.99 for p in pv_list):
            return self._warn(
                f"All {n} p-values are > 0.99.  "
                "This may indicate a model that explains nothing or miscoded data.",
                n_pvalues=n,
                n_above_099=n,
            )

        # Check: suspiciously high fraction below 0.05
        n_sig = sum(1 for p in pv_list if p < 0.05)
        frac_sig = n_sig / n

        if frac_sig > suspicious_fraction:
            return self._warn(
                f"{n_sig}/{n} ({frac_sig:.0%}) of p-values are < 0.05.  "
                "This high fraction may indicate selective reporting; "
                "report all specifications.",
                n_pvalues=n,
                n_significant=n_sig,
                fraction_significant=round(frac_sig, 4),
                suspicious_fraction_threshold=suspicious_fraction,
            )

        return self._pass(
            f"P-value distribution looks healthy: {n_sig}/{n} significant at 5%.",
            n_pvalues=n,
            n_significant=n_sig,
            fraction_significant=round(frac_sig, 4),
        )
