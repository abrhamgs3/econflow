"""
econflow.diagnostics.plugins.pesaran_cd — Pesaran cross-sectional dependence test.

Tests H0: no cross-sectional dependence in panel residuals.
CD statistic ~ N(0,1) under H0 for large N.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

from econflow.diagnostics.base import BaseDiagnostic
from econflow.diagnostics.registry import register_diagnostic
from econflow.estimation.result import DiagnosticResult, EstimationResult


@register_diagnostic(
    "pesaran_cd",
    label="Pesaran Cross-Sectional Dependence Test",
    notes="H0: no cross-sectional dependence; CD ~ N(0,1)",
)
class PesaranCD(BaseDiagnostic):
    """
    Pesaran (2004) CD test for cross-sectional dependence.

    Requires the original data to compute residuals.  Pass it via
    ``run(result, data=df)``.
    """

    diagnostic_id = "pesaran_cd"
    name = "Pesaran CD Test"
    description = (
        "Tests for cross-sectional dependence in panel residuals.  "
        "H0: residuals are cross-sectionally independent.  "
        "Rejection suggests common factor structure."
    )
    supported_estimators = ["ols", "fe", "twfe", "re", "fd"]
    required_assumptions = ["Residuals computed from a fitted model"]
    output_schema = {
        "statistic": "float — CD statistic (standard normal under H0)",
        "N": "int — number of cross-sectional units",
        "T": "int — average time series length",
        "mean_corr": "float — average pair-wise correlation",
    }

    def run(
        self,
        result: EstimationResult,
        *,
        data: pd.DataFrame | None = None,
        residuals: pd.Series | None = None,
        **kwargs: object,
    ) -> DiagnosticResult:
        import pandas as pd  # noqa: PLC0415

        if residuals is None and data is None:
            return self._not_applicable(
                "Pass data= or residuals= to compute the CD statistic"
            )

        if residuals is None:
            dep = result.provenance.get("params", {}).get("dependent", "")
            if not dep or dep not in data.columns:
                return self._not_applicable(f"Cannot find dependent variable '{dep}' in data")
            # Approximate residuals: y - Xb
            regs = result.provenance.get("params", {}).get("regressors", [])
            ec = result.entity_col
            tc = result.time_col
            needed = [dep, ec, tc] + list(regs)
            if not all(c in data.columns for c in needed):
                return self._not_applicable("Required columns missing in data")
            subset = data.dropna(subset=[dep] + list(regs)).copy()
            fitted = subset[list(regs)].values @ result.params[list(regs)].values
            residuals = pd.Series(
                subset[dep].values - fitted,
                index=pd.MultiIndex.from_arrays(
                    [subset[ec].values, subset[tc].values],
                    names=[ec, tc],
                ),
            )

        # Pivot to wide (entity × time)
        try:
            wide = residuals.unstack(level=1)
        except Exception:
            return self._not_applicable("Could not pivot residuals to wide format")

        N, T = wide.shape
        if N < 2:
            return self._not_applicable("Need at least 2 entities")

        # Pair-wise correlations
        corr_sum = 0.0
        count = 0
        for i in range(N):
            for j in range(i + 1, N):
                mask = ~(np.isnan(wide.iloc[i].values) | np.isnan(wide.iloc[j].values))
                t_ij = mask.sum()
                if t_ij < 2:
                    continue
                r = float(np.corrcoef(wide.iloc[i].values[mask],
                                       wide.iloc[j].values[mask])[0, 1])
                corr_sum += np.sqrt(t_ij) * r
                count += 1

        if count == 0:
            return self._not_applicable("No valid entity pairs found")

        cd = np.sqrt(2 / (N * (N - 1))) * corr_sum
        pvalue = float(2 * (1 - stats.norm.cdf(abs(cd))))
        mean_corr = corr_sum / count if count else 0.0

        conclusion = (
            f"{'Reject' if pvalue < 0.05 else 'Fail to reject'} H0 "
            f"(CD={cd:.3f}, p={pvalue:.4f}): "
            f"{'cross-sectional dependence detected' if pvalue < 0.05 else 'no significant CD'}."
        )

        return DiagnosticResult(
            diagnostic_id=self.diagnostic_id,
            diagnostic_name=self.name,
            statistic=float(cd),
            pvalue=pvalue,
            conclusion=conclusion,
            level="warning" if pvalue < 0.05 else "info",
            extra={"N": N, "T": T, "mean_corr": mean_corr / np.sqrt(T) if T > 0 else 0.0},
        )
