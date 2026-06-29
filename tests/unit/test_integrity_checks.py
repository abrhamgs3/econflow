"""
Unit tests for econflow.integrity.checks — registry and all 3 built-in plugins.
"""

from __future__ import annotations

import pandas as pd
import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _er(
    estimator_id="ols",
    var_names=None,
    param_values=None,
    pvalues=None,
    nobs=100,
):
    """
    Create a minimal EstimationResult for testing.

    Parameters
    ----------
    var_names: list[str]
        Variable names (index).  Default: ["x1", "x2", "x3"].
    param_values: list[float]
        Coefficient values.  Default: [0.5] * len(var_names).
    pvalues: list[float]
        P-values.  Must have the same length as var_names.
        Default: [0.01, 0.05, 0.20, ...].
    """
    from econflow.estimation.result import EstimationResult

    var_names = var_names or ["x1", "x2", "x3"]
    idx = pd.Index(var_names)
    n = len(idx)

    pv = param_values or [0.5] * n
    if len(pv) != n:
        raise ValueError(f"param_values length {len(pv)} != var_names length {n}")

    _default_pvals = [0.01, 0.05, 0.20]
    pv_list = pvalues if pvalues is not None else (_default_pvals[:n] + [0.10] * max(0, n - 3))
    if len(pv_list) != n:
        raise ValueError(f"pvalues length {len(pv_list)} != var_names length {n}")

    return EstimationResult(
        estimator_id=estimator_id,
        estimator_name=estimator_id.upper(),
        params=pd.Series(pv, index=idx),
        std_err=pd.Series([0.1] * n, index=idx),
        conf_int=pd.DataFrame(
            {"lower": [v - 0.2 for v in pv], "upper": [v + 0.2 for v in pv]},
            index=idx,
        ),
        pvalues=pd.Series(pv_list, index=idx),
        nobs=nobs,
        ngroups=20,
        df_resid=nobs - n - 1,
        rsquared=0.60,
        rsquared_adj=0.58,
    )


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


class TestIntegrityCheckRegistry:
    def test_list_checks_returns_implemented(self):
        from econflow.integrity.checks import list_checks
        checks = list_checks()
        ids = [c["id"] for c in checks]
        assert "coefficient_stability" in ids
        assert "sample_size" in ids
        assert "pvalue_distribution" in ids

    def test_get_check_returns_class(self):
        from econflow.integrity.checks import get_check
        cls = get_check("coefficient_stability")
        from econflow.integrity.checks.base import BaseIntegrityCheck
        assert issubclass(cls, BaseIntegrityCheck)

    def test_get_check_unknown_raises(self):
        from econflow.core.exceptions import RegistryError
        from econflow.integrity.checks import get_check
        with pytest.raises(RegistryError):
            get_check("nonexistent_check")

    def test_duplicate_registration_raises(self):
        from econflow.core.exceptions import RegistryError
        from econflow.integrity.checks.registry import register_integrity_check
        with pytest.raises(RegistryError):
            @register_integrity_check("coefficient_stability")
            class DupCheck:
                pass

    def test_unregister_and_reregister(self):
        from econflow.integrity.checks.base import BaseIntegrityCheck, IntegrityCheckResult
        from econflow.integrity.checks.registry import (
            get_check,
            register_integrity_check,
            unregister_check,
        )

        @register_integrity_check("_tmp_test_check")
        class _TmpCheck(BaseIntegrityCheck):
            def run(self, result, **kwargs):
                return IntegrityCheckResult(
                    check_id=self.check_id, name=self.name, status="pass"
                )

        assert get_check("_tmp_test_check") is _TmpCheck
        unregister_check("_tmp_test_check")
        from econflow.core.exceptions import RegistryError
        with pytest.raises(RegistryError):
            get_check("_tmp_test_check")


# ---------------------------------------------------------------------------
# CoefficientStabilityCheck
# ---------------------------------------------------------------------------


class TestCoefficientStabilityCheck:
    def _check(self):
        from econflow.integrity.checks import get_check
        return get_check("coefficient_stability")()

    def test_normal_coefs_pass(self):
        result = self._check().run(_er())
        assert result.status == "pass"
        assert result.check_id == "coefficient_stability"

    def test_large_coef_warn(self):
        er = _er(var_names=["x1"], param_values=[150.0], pvalues=[0.01])
        result = self._check().run(er, warn_threshold=100.0, fail_threshold=1000.0)
        assert result.status == "warn"
        assert result.extra["max_abs_coefficient"] > 100

    def test_huge_coef_fail(self):
        er = _er(var_names=["x1"], param_values=[2000.0], pvalues=[0.01])
        result = self._check().run(er, warn_threshold=100.0, fail_threshold=1000.0)
        assert result.status == "fail"

    def test_custom_thresholds(self):
        # coef=5 > warn=3 but < fail=10 → warn
        er = _er(var_names=["x1"], param_values=[5.0], pvalues=[0.01])
        result = self._check().run(er, warn_threshold=3.0, fail_threshold=10.0)
        assert result.status == "warn"

    def test_no_params_returns_skip(self):
        import pandas as pd

        from econflow.estimation.result import EstimationResult
        er = EstimationResult(
            estimator_id="x", estimator_name="X",
            params=pd.Series([], dtype=float),
            std_err=pd.Series([], dtype=float),
            conf_int=pd.DataFrame({"lower": [], "upper": []}),
            pvalues=pd.Series([], dtype=float),
            nobs=0, ngroups=0, df_resid=0,
            rsquared=0.0, rsquared_adj=0.0,
        )
        result = self._check().run(er)
        assert result.status == "skip"

    def test_inf_coef_warn(self):
        er = _er(var_names=["x1"], param_values=[0.5], pvalues=[0.01])
        er.params["x1"] = float("inf")
        result = self._check().run(er)
        assert result.status == "warn"
        assert result.extra.get("non_finite")


# ---------------------------------------------------------------------------
# SampleSizeCheck
# ---------------------------------------------------------------------------


class TestSampleSizeCheck:
    def _check(self):
        from econflow.integrity.checks import get_check
        return get_check("sample_size")()

    def test_adequate_sample_pass(self):
        result = self._check().run(_er(nobs=200))
        assert result.status == "pass"

    def test_small_sample_warn(self):
        result = self._check().run(_er(nobs=20), warn_threshold=30, fail_threshold=10)
        assert result.status == "warn"

    def test_tiny_sample_fail(self):
        result = self._check().run(_er(nobs=5), warn_threshold=30, fail_threshold=10)
        assert result.status == "fail"

    def test_exactly_at_warn_threshold_passes(self):
        result = self._check().run(_er(nobs=30), warn_threshold=30, fail_threshold=10)
        assert result.status == "pass"

    def test_nobs_none_returns_skip(self):
        er = _er(nobs=100)
        er.nobs = None
        result = self._check().run(er)
        assert result.status == "skip"

    def test_extra_contains_nobs(self):
        result = self._check().run(_er(nobs=50))
        assert result.extra["nobs"] == 50


# ---------------------------------------------------------------------------
# PvalueDistributionCheck
# ---------------------------------------------------------------------------


class TestPvalueDistributionCheck:
    def _check(self):
        from econflow.integrity.checks import get_check
        return get_check("pvalue_distribution")()

    def test_healthy_distribution_pass(self):
        # 5 variables, mixed pvalues — healthy
        er = _er(
            var_names=["x1", "x2", "x3", "x4", "x5"],
            param_values=[0.5] * 5,
            pvalues=[0.001, 0.03, 0.15, 0.40, 0.70],
        )
        result = self._check().run(er)
        assert result.status == "pass"

    def test_all_identical_fail(self):
        er = _er(
            var_names=["x1", "x2", "x3", "x4"],
            param_values=[0.5] * 4,
            pvalues=[0.05, 0.05, 0.05, 0.05],
        )
        result = self._check().run(er)
        assert result.status == "fail"

    def test_all_below_0001_fail(self):
        er = _er(
            var_names=["x1", "x2", "x3", "x4"],
            param_values=[0.5] * 4,
            pvalues=[0.0001, 0.0002, 0.00005, 0.00001],
        )
        result = self._check().run(er)
        assert result.status == "fail"

    def test_all_above_099_warn(self):
        er = _er(
            var_names=["x1", "x2", "x3", "x4"],
            param_values=[0.5] * 4,
            pvalues=[0.995, 0.998, 0.991, 0.999],
        )
        result = self._check().run(er)
        assert result.status == "warn"

    def test_high_fraction_significant_warn(self):
        # 9/10 < 0.05 → suspicious at 0.8 threshold
        n = 10
        pvals = [0.01] * 9 + [0.30]
        er = _er(
            var_names=[f"x{i}" for i in range(n)],
            param_values=[0.5] * n,
            pvalues=pvals,
        )
        result = self._check().run(er, suspicious_fraction=0.8)
        assert result.status == "warn"

    def test_too_few_pvalues_skip(self):
        # Only 2 variables (< min_pvalues=3) → skip
        er = _er(
            var_names=["x1", "x2"],
            param_values=[0.5, 0.3],
            pvalues=[0.01, 0.05],
        )
        result = self._check().run(er, min_pvalues=3)
        assert result.status == "skip"

    def test_extra_contains_fractions(self):
        er = _er(
            var_names=["x1", "x2", "x3", "x4", "x5"],
            param_values=[0.5] * 5,
            pvalues=[0.01, 0.50, 0.80, 0.90, 0.95],
        )
        result = self._check().run(er)
        assert "n_pvalues" in result.extra
        assert "fraction_significant" in result.extra
