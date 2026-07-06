"""
econflow.diagnostics.plugins.hausman — Hausman specification test.

Tests H0: individual effects are uncorrelated with regressors (RE is consistent).
Rejection favours FE.

Statistic:  H = (b_FE - b_RE)' [V_FE - V_RE]^{-1} (b_FE - b_RE) ~ chi2(k)
"""

from __future__ import annotations

import numpy as np
from scipy import stats

from econflow.diagnostics.base import BaseDiagnostic, DiagnosticError
from econflow.diagnostics.registry import register_diagnostic
from econflow.estimation.result import DiagnosticResult, EstimationResult


@register_diagnostic(
    "hausman",
    label="Hausman Specification Test",
    notes="H0: RE is consistent; rejection favours FE",
)
class HausmanTest(BaseDiagnostic):
    """
    Hausman test for random vs. fixed effects.

    Usage
    -----
    ::

        diag = HausmanTest()
        result = diag.run(fe_result, re_result=re_result)

    The ``re_result`` keyword argument is required.
    """

    diagnostic_id = "hausman"
    name = "Hausman Specification Test"
    description = (
        "Tests whether the random-effects estimator is consistent.  "
        "H0: individual effects uncorrelated with regressors (RE consistent).  "
        "Rejection favours the fixed-effects model."
    )
    supported_estimators = ["fe", "twfe"]
    required_assumptions = [
        "FE and RE estimated on identical samples",
        "FE estimator is always consistent",
        "RE estimator is efficient under H0",
    ]
    output_schema = {
        "statistic": "float — chi-squared test statistic",
        "df": "int — degrees of freedom",
        "common_vars": "list[str] — variables included in the test",
    }

    def run(
        self,
        result: EstimationResult,
        *,
        re_result: EstimationResult | None = None,
        **kwargs: object,
    ) -> DiagnosticResult:
        if re_result is None:
            return self._not_applicable("re_result keyword argument is required")

        # Align common variables
        common = result.params.index.intersection(re_result.params.index).tolist()
        if len(common) == 0:
            return self._not_applicable("No common variables between FE and RE results")

        b_fe = result.params[common].values
        b_re = re_result.params[common].values

        # Variance matrices (diagonal only — assume independent)
        try:
            v_fe = np.diag(result.std_err[common].values ** 2)
            v_re = np.diag(re_result.std_err[common].values ** 2)
            v_diff = v_fe - v_re

            # Ensure positive semi-definite (regularise if needed)
            eigvals = np.linalg.eigvalsh(v_diff)
            if np.any(eigvals < -1e-10):
                # Small negative eigenvalues → clamp to 0
                v_diff = v_diff + abs(eigvals.min()) * np.eye(len(common)) * 1.01

            diff = b_fe - b_re
            stat = float(diff @ np.linalg.pinv(v_diff) @ diff)
            df = len(common)
            pvalue = float(1 - stats.chi2.cdf(stat, df))
        except Exception as exc:
            raise DiagnosticError(
                f"Hausman test computation failed: {exc}",
                diagnostic_id=self.diagnostic_id,
                cause=exc,
            ) from exc

        if pvalue < 0.05:
            conclusion = (
                f"Reject H0 (p={pvalue:.4f}): use Fixed Effects "
                f"(chi2({df})={stat:.3f})."
            )
        else:
            conclusion = (
                f"Fail to reject H0 (p={pvalue:.4f}): Random Effects may be "
                f"consistent (chi2({df})={stat:.3f})."
            )

        return DiagnosticResult(
            diagnostic_id=self.diagnostic_id,
            diagnostic_name=self.name,
            statistic=stat,
            pvalue=pvalue,
            conclusion=conclusion,
            level="warning" if pvalue < 0.05 else "info",
            extra={"df": df, "common_vars": common},
        )
