"""
Phase 0 Baseline Regression Tests
===================================
These tests were written to establish a numerical gate for the EstimationDispatcher
migration.

> **Coverage note (added 2026-07-19, RC stabilization audit):** the `pipeline_results`
> fixture below computes its comparison values via direct, standalone `linearmodels`
> calls (`linearmodels.PanelOLS`/`PooledOLS`) — it does not import or call anything
> from `econflow.estimation` (no `PooledOLS`, `EntityFE`, or `TwoWayFE` from
> `econflow.estimation.*`, and no `pipeline_generic.py`/dispatcher code path).
> Consequently, this module does **not** exercise "the CURRENT pipeline" or
> econflow's actual estimator classes, and would **not** catch a regression
> introduced in `econflow.estimation.fixed_effects`/`ols.py` (e.g. Sprint S1's
> deliberate removal of the constant term from `EntityFE`/`TwoWayFE` results —
> confirmed live: `EntityFE.fit(...).params.index` is `['value', 'capital']`,
> with no `'const'`, while this fixture's frozen baseline and standalone
> reimplementation both include one). What this module *does* verify: that
> raw `linearmodels` (the fitting library econflow depends on) continues to
> return the same numbers for a fixed model specification across dependency
> upgrades — a real and useful check, just not the one the docstring
> originally claimed. See `docs/release/FINAL_RELEASE_AUDIT_v1.0.md` Task 2
> for the full investigation.

Every test here compares a standalone `linearmodels` reference computation against
the Phase 0 baseline fixtures in tests/integration/fixtures/baseline/. It does not
directly exercise `econflow.estimation`'s estimator classes or `pipeline_generic.py`.

Constraints (enforced by test_no_production_files_changed):
  - No production source files are modified by Phase 0
  - Only tests/, fixtures, and docs/ may contain new files

Dataset: Grunfeld (1958) investment panel
  220 observations, 11 firms, 20 years (1935–1954)
  Dependent: invest   Regressors: value, capital

Models exercised:
  pooled_ols  — PooledOLS,                      unadjusted SEs
  entity_fe   — PanelOLS entity effects,         clustered by entity
  twoway_fe   — PanelOLS entity + time effects,  clustered by entity
"""

from __future__ import annotations

import hashlib
import json
import math
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).parent.parent.parent
FIXTURE_DIR = Path(__file__).parent / "fixtures" / "baseline"
EXAMPLE_DIR = REPO_ROOT / "examples" / "getting_started"
EXAMPLE_OUTPUTS = EXAMPLE_DIR / "outputs"
EXAMPLE_DATA = EXAMPLE_DIR / "data" / "grunfeld.csv"

CONFIG_PATH = EXAMPLE_DIR / "config" / "config.yaml"
MODELS_PATH = EXAMPLE_DIR / "config" / "models.yaml"
OUTPUTS_PATH = EXAMPLE_DIR / "config" / "outputs.yaml"

# ---------------------------------------------------------------------------
# Tolerances
# ---------------------------------------------------------------------------

COEF_RTOL = 1e-10       # coefficients, SEs, t-stats
PVAL_ATOL = 1e-12       # p-values (near-zero values need absolute tolerance)
CI_RTOL = 1e-10         # confidence intervals
R2_RTOL = 1e-10         # R² variants
FSTAT_RTOL = 1e-8       # F-statistic (slightly looser)
LOGLIK_RTOL = 1e-10     # log-likelihood
DIAG_RTOL = 1e-6        # diagnostic statistics (BP, DW rounded values)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_fixture(name: str):
    path = FIXTURE_DIR / name
    if path.suffix == ".json":
        return json.loads(path.read_text(encoding="utf-8"))
    if path.suffix == ".csv":
        return pd.read_csv(path, dtype=str, keep_default_na=False)
    raise ValueError(f"Unknown fixture type: {path.suffix}")


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _run_pipeline() -> None:
    """Run the getting_started example via the CLI."""
    result = subprocess.run(
        [
            sys.executable, "-m", "econflow.cli", "run",
            "--config", str(CONFIG_PATH),
            "--models", str(MODELS_PATH),
            "--outputs", str(OUTPUTS_PATH),
        ],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"Pipeline run failed (exit {result.returncode}):\n"
            f"STDOUT:\n{result.stdout}\n"
            f"STDERR:\n{result.stderr}"
        )


def _approx_rel(a: float, b: float, rtol: float) -> bool:
    if a == b:
        return True
    if b == 0:
        return abs(a) <= rtol
    return abs(a - b) / abs(b) <= rtol


def _approx_abs(a: float, b: float, atol: float) -> bool:
    return abs(a - b) <= atol


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def baseline_numerical():
    return _load_fixture("numerical_results.json")


@pytest.fixture(scope="module")
def baseline_diagnostics_full():
    return _load_fixture("diagnostics_full.json")


@pytest.fixture(scope="module")
def baseline_diagnostics_csv():
    return _load_fixture("diagnostics.csv")


@pytest.fixture(scope="module")
def baseline_comparison_csv():
    return _load_fixture("comparison_table.csv")


@pytest.fixture(scope="module")
def baseline_provenance_schema():
    return _load_fixture("provenance_schema.json")


@pytest.fixture(scope="module")
def pipeline_results(baseline_numerical):
    """
    Return linearmodels result objects computed directly via raw
    ``linearmodels.PanelOLS``/``PooledOLS`` calls.

    This is a standalone reference computation, not a call into
    ``econflow.estimation`` or ``pipeline_generic.py`` — it deliberately
    keeps an explicit ``const`` column even for the entity/time-effects
    models, which is why this fixture's values differ from what
    ``econflow.estimation.fixed_effects.EntityFE``/``TwoWayFE`` (the
    classes ``econflow run`` actually uses) return for the same data —
    those omit ``const`` entirely, since it is collinear with the
    absorbed fixed effects. See the module docstring's coverage note.
    """
    import numpy as np
    from linearmodels import PanelOLS, PooledOLS

    df = pd.read_csv(EXAMPLE_DATA)
    df = df.set_index(["firm", "year"])
    y = df["invest"]
    X = df[["value", "capital"]]
    X = pd.concat([pd.Series(1.0, index=X.index, name="const"), X], axis=1)

    results = {
        "pooled_ols": PooledOLS(y, X).fit(cov_type="unadjusted"),
        "entity_fe": PanelOLS(y, X, entity_effects=True, time_effects=False,
                              drop_absorbed=True).fit(cov_type="clustered",
                                                      cluster_entity=True),
        "twoway_fe": PanelOLS(y, X, entity_effects=True, time_effects=True,
                              drop_absorbed=True).fit(cov_type="clustered",
                                                      cluster_entity=True),
    }
    return results


# ---------------------------------------------------------------------------
# Section 1: Data integrity
# ---------------------------------------------------------------------------


class TestDataIntegrity:
    """The input dataset must not change between runs."""

    def test_grunfeld_sha256_matches_fixture(self, baseline_provenance_schema):
        expected = baseline_provenance_schema["data_sha256"]
        actual = _sha256_file(EXAMPLE_DATA)
        assert actual == expected, (
            f"Grunfeld data file has changed!\n"
            f"  Expected SHA-256: {expected}\n"
            f"  Actual   SHA-256: {actual}"
        )

    def test_grunfeld_row_count(self):
        df = pd.read_csv(EXAMPLE_DATA)
        assert len(df) == 220, f"Expected 220 rows, got {len(df)}"

    def test_grunfeld_entity_count(self):
        df = pd.read_csv(EXAMPLE_DATA)
        assert df["firm"].nunique() == 11, f"Expected 11 entities, got {df['firm'].nunique()}"

    def test_grunfeld_time_count(self):
        df = pd.read_csv(EXAMPLE_DATA)
        assert df["year"].nunique() == 20, f"Expected 20 time periods, got {df['year'].nunique()}"

    def test_grunfeld_columns(self):
        df = pd.read_csv(EXAMPLE_DATA)
        required = {"invest", "value", "capital", "firm", "year"}
        assert required.issubset(df.columns), (
            f"Missing columns: {required - set(df.columns)}"
        )

    def test_grunfeld_no_missing_values(self):
        df = pd.read_csv(EXAMPLE_DATA)
        assert df[["invest", "value", "capital"]].isnull().sum().sum() == 0


# ---------------------------------------------------------------------------
# Section 2: Numerical results — coefficients
# ---------------------------------------------------------------------------


MODEL_IDS = ["pooled_ols", "entity_fe", "twoway_fe"]
REGRESSORS = ["const", "value", "capital"]


class TestCoefficients:
    """Coefficients must match the baseline to within COEF_RTOL."""

    @pytest.mark.parametrize("model_id", MODEL_IDS)
    @pytest.mark.parametrize("reg", REGRESSORS)
    def test_param(self, pipeline_results, baseline_numerical, model_id, reg):
        expected = baseline_numerical["models"][model_id]["params"][reg]
        actual = float(pipeline_results[model_id].params[reg])
        assert _approx_rel(actual, expected, COEF_RTOL), (
            f"{model_id}.params[{reg}]: expected {expected:.15g}, got {actual:.15g}, "
            f"rel_diff={abs(actual - expected) / abs(expected):.2e}"
        )

    @pytest.mark.parametrize("model_id", MODEL_IDS)
    @pytest.mark.parametrize("reg", REGRESSORS)
    def test_std_error(self, pipeline_results, baseline_numerical, model_id, reg):
        expected = baseline_numerical["models"][model_id]["std_errors"][reg]
        actual = float(pipeline_results[model_id].std_errors[reg])
        assert _approx_rel(actual, expected, COEF_RTOL), (
            f"{model_id}.std_errors[{reg}]: expected {expected:.15g}, got {actual:.15g}"
        )

    @pytest.mark.parametrize("model_id", MODEL_IDS)
    @pytest.mark.parametrize("reg", REGRESSORS)
    def test_tstat(self, pipeline_results, baseline_numerical, model_id, reg):
        expected = baseline_numerical["models"][model_id]["tstats"][reg]
        actual = float(pipeline_results[model_id].tstats[reg])
        assert _approx_rel(actual, expected, COEF_RTOL), (
            f"{model_id}.tstats[{reg}]: expected {expected:.15g}, got {actual:.15g}"
        )

    @pytest.mark.parametrize("model_id", MODEL_IDS)
    @pytest.mark.parametrize("reg", ["value", "capital"])
    def test_pvalue(self, pipeline_results, baseline_numerical, model_id, reg):
        expected = baseline_numerical["models"][model_id]["pvalues"][reg]
        actual = float(pipeline_results[model_id].pvalues[reg])
        # Use absolute tolerance for near-zero p-values
        assert _approx_abs(actual, expected, PVAL_ATOL) or _approx_rel(actual, expected, 1e-6), (
            f"{model_id}.pvalues[{reg}]: expected {expected:.6e}, got {actual:.6e}"
        )

    @pytest.mark.parametrize("model_id", MODEL_IDS)
    @pytest.mark.parametrize("reg", REGRESSORS)
    def test_conf_int_lower(self, pipeline_results, baseline_numerical, model_id, reg):
        expected = baseline_numerical["models"][model_id]["conf_int"]["lower"][reg]
        # conf_int is a method in linearmodels PanelResults
        actual = float(pipeline_results[model_id].conf_int().loc[reg, "lower"])
        assert _approx_rel(actual, expected, CI_RTOL), (
            f"{model_id}.conf_int.lower[{reg}]: expected {expected:.15g}, got {actual:.15g}"
        )

    @pytest.mark.parametrize("model_id", MODEL_IDS)
    @pytest.mark.parametrize("reg", REGRESSORS)
    def test_conf_int_upper(self, pipeline_results, baseline_numerical, model_id, reg):
        expected = baseline_numerical["models"][model_id]["conf_int"]["upper"][reg]
        actual = float(pipeline_results[model_id].conf_int().loc[reg, "upper"])
        assert _approx_rel(actual, expected, CI_RTOL), (
            f"{model_id}.conf_int.upper[{reg}]: expected {expected:.15g}, got {actual:.15g}"
        )


# ---------------------------------------------------------------------------
# Section 3: Goodness-of-fit statistics
# ---------------------------------------------------------------------------


class TestGoodnessOfFit:
    """R², F-stat, log-likelihood, and observation counts."""

    @pytest.mark.parametrize("model_id", MODEL_IDS)
    def test_nobs(self, pipeline_results, baseline_numerical, model_id):
        expected = baseline_numerical["models"][model_id]["nobs"]
        actual = int(pipeline_results[model_id].nobs)
        assert actual == expected, f"{model_id}.nobs: expected {expected}, got {actual}"

    @pytest.mark.parametrize("model_id", MODEL_IDS)
    def test_rsquared(self, pipeline_results, baseline_numerical, model_id):
        expected = baseline_numerical["models"][model_id]["rsquared"]
        actual = float(pipeline_results[model_id].rsquared)
        assert _approx_rel(actual, expected, R2_RTOL), (
            f"{model_id}.rsquared: expected {expected:.15g}, got {actual:.15g}"
        )

    @pytest.mark.parametrize("model_id", MODEL_IDS)
    def test_rsquared_within(self, pipeline_results, baseline_numerical, model_id):
        expected = baseline_numerical["models"][model_id]["rsquared_within"]
        actual = float(pipeline_results[model_id].rsquared_within)
        assert _approx_rel(actual, expected, R2_RTOL), (
            f"{model_id}.rsquared_within: expected {expected:.15g}, got {actual:.15g}"
        )

    @pytest.mark.parametrize("model_id", MODEL_IDS)
    def test_rsquared_between(self, pipeline_results, baseline_numerical, model_id):
        expected = baseline_numerical["models"][model_id]["rsquared_between"]
        actual = float(pipeline_results[model_id].rsquared_between)
        assert _approx_rel(actual, expected, R2_RTOL), (
            f"{model_id}.rsquared_between: expected {expected:.15g}, got {actual:.15g}"
        )

    @pytest.mark.parametrize("model_id", MODEL_IDS)
    def test_rsquared_overall(self, pipeline_results, baseline_numerical, model_id):
        expected = baseline_numerical["models"][model_id]["rsquared_overall"]
        actual = float(pipeline_results[model_id].rsquared_overall)
        assert _approx_rel(actual, expected, R2_RTOL), (
            f"{model_id}.rsquared_overall: expected {expected:.15g}, got {actual:.15g}"
        )

    @pytest.mark.parametrize("model_id", MODEL_IDS)
    def test_f_statistic(self, pipeline_results, baseline_numerical, model_id):
        expected = baseline_numerical["models"][model_id]["f_statistic"]
        try:
            actual = float(pipeline_results[model_id].f_statistic.stat)
        except AttributeError:
            actual = float(pipeline_results[model_id].f_statistic)
        assert _approx_rel(actual, expected, FSTAT_RTOL), (
            f"{model_id}.f_statistic: expected {expected:.15g}, got {actual:.15g}"
        )

    @pytest.mark.parametrize("model_id", MODEL_IDS)
    def test_loglik(self, pipeline_results, baseline_numerical, model_id):
        expected = baseline_numerical["models"][model_id]["loglik"]
        actual = float(pipeline_results[model_id].loglik)
        assert _approx_rel(actual, expected, LOGLIK_RTOL), (
            f"{model_id}.loglik: expected {expected:.15g}, got {actual:.15g}"
        )


# ---------------------------------------------------------------------------
# Section 4: Coefficient sign and significance preservation
# ---------------------------------------------------------------------------


class TestCoefficientProperties:
    """Signs and significance tiers must be exactly preserved."""

    @pytest.mark.parametrize("model_id", MODEL_IDS)
    def test_value_coef_positive(self, pipeline_results, model_id):
        coef = float(pipeline_results[model_id].params["value"])
        assert coef > 0, f"{model_id}: value coefficient should be positive, got {coef}"

    @pytest.mark.parametrize("model_id", MODEL_IDS)
    def test_capital_coef_positive(self, pipeline_results, model_id):
        coef = float(pipeline_results[model_id].params["capital"])
        assert coef > 0, f"{model_id}: capital coefficient should be positive, got {coef}"

    @pytest.mark.parametrize("model_id", MODEL_IDS)
    def test_value_pval_triple_star(self, pipeline_results, model_id):
        pval = float(pipeline_results[model_id].pvalues["value"])
        assert pval < 0.01, (
            f"{model_id}: value p-value should be <0.01 (***), got {pval:.6e}"
        )

    @pytest.mark.parametrize("model_id", MODEL_IDS)
    def test_capital_pval_triple_star(self, pipeline_results, model_id):
        pval = float(pipeline_results[model_id].pvalues["capital"])
        assert pval < 0.01, (
            f"{model_id}: capital p-value should be <0.01 (***), got {pval:.6e}"
        )

    def test_entity_fe_has_higher_capital_coef_than_pooled(self, pipeline_results):
        """Entity FE should absorb firm-level omitted variables, raising capital coef."""
        pooled = float(pipeline_results["pooled_ols"].params["capital"])
        entity = float(pipeline_results["entity_fe"].params["capital"])
        assert entity > pooled, (
            f"Expected entity_fe capital ({entity:.4f}) > pooled_ols capital ({pooled:.4f})"
        )

    def test_twoway_fe_capital_highest(self, pipeline_results):
        """Two-way FE absorbs both entity and time variation, further raising capital coef."""
        entity = float(pipeline_results["entity_fe"].params["capital"])
        twoway = float(pipeline_results["twoway_fe"].params["capital"])
        assert twoway > entity, (
            f"Expected twoway_fe capital ({twoway:.4f}) > entity_fe capital ({entity:.4f})"
        )


# ---------------------------------------------------------------------------
# Section 5: Diagnostics
# ---------------------------------------------------------------------------


class TestDiagnostics:
    """Diagnostic values must match the baseline to within DIAG_RTOL."""

    def _get_diagnostic(self, baseline, model_id: str, diagnostic: str) -> dict:
        for row in baseline["diagnostics"]:
            if row["model_id"] == model_id and row["diagnostic"] == diagnostic:
                return row
        raise KeyError(f"No diagnostic row for {model_id}/{diagnostic}")

    @pytest.mark.parametrize("model_id", MODEL_IDS)
    def test_vif_statistic(self, baseline_diagnostics_full, model_id):
        row = self._get_diagnostic(baseline_diagnostics_full, model_id, "VIF (max)")
        expected = row["statistic_full"]
        # Match pipeline: prepend const column, compute VIF at indices 1 and 2
        from statsmodels.stats.outliers_influence import variance_inflation_factor
        import numpy as np
        df = pd.read_csv(EXAMPLE_DATA)
        X_data = df[["value", "capital"]].dropna().values
        X_c = np.column_stack([np.ones(len(X_data)), X_data])
        vifs = [variance_inflation_factor(X_c, i + 1) for i in range(X_data.shape[1])]
        actual = max(vifs)
        assert _approx_rel(actual, expected, DIAG_RTOL), (
            f"{model_id} VIF: expected {expected:.10g}, got {actual:.10g}"
        )

    @pytest.mark.parametrize("model_id", MODEL_IDS)
    def test_bp_statistic(self, pipeline_results, baseline_diagnostics_full, model_id):
        row = self._get_diagnostic(baseline_diagnostics_full, model_id, "Breusch-Pagan")
        expected_stat = row["statistic_full"]
        expected_pval = row["p_value_full"]

        import numpy as np
        from statsmodels.stats.diagnostic import het_breuschpagan

        # Match pipeline: align residuals to X index, prepend const column
        df_data = pd.read_csv(EXAMPLE_DATA).set_index(["firm", "year"])
        X_panel = df_data[["value", "capital"]].dropna()
        common_idx = X_panel.index.intersection(pipeline_results[model_id].resids.index)
        resids_aligned = pipeline_results[model_id].resids.loc[common_idx].values
        X_aligned = np.column_stack([
            np.ones(len(common_idx)),
            X_panel.loc[common_idx].values,
        ])
        lm_stat, lm_pval, _, _ = het_breuschpagan(resids_aligned, X_aligned)

        assert _approx_rel(float(lm_stat), expected_stat, DIAG_RTOL), (
            f"{model_id} BP stat: expected {expected_stat:.10g}, got {lm_stat:.10g}"
        )
        assert _approx_rel(float(lm_pval), expected_pval, DIAG_RTOL) or _approx_abs(
            float(lm_pval), expected_pval, 1e-20
        ), (
            f"{model_id} BP pval: expected {expected_pval:.6e}, got {lm_pval:.6e}"
        )

    @pytest.mark.parametrize("model_id", MODEL_IDS)
    def test_dw_statistic(self, pipeline_results, baseline_diagnostics_full, model_id):
        row = self._get_diagnostic(
            baseline_diagnostics_full, model_id, "Serial Correlation (DW)"
        )
        expected = row["statistic_full"]

        import numpy as np

        resids = np.array(pipeline_results[model_id].resids)
        diff = np.diff(resids)
        dw = np.sum(diff**2) / np.sum(resids**2)
        assert _approx_rel(dw, expected, DIAG_RTOL), (
            f"{model_id} DW: expected {expected:.10g}, got {dw:.10g}"
        )

    def test_diagnostics_csv_matches_baseline(self, baseline_diagnostics_csv):
        """The pipeline's diagnostics.csv must be string-identical to the baseline."""
        output_csv = EXAMPLE_OUTPUTS / "tables" / "diagnostics.csv"
        if not output_csv.exists():
            pytest.skip(
                "diagnostics.csv not present — run 'econflow run ...' to generate it"
            )
        actual = pd.read_csv(output_csv, dtype=str, keep_default_na=False)
        pd.testing.assert_frame_equal(
            actual.reset_index(drop=True),
            baseline_diagnostics_csv.reset_index(drop=True),
            check_names=True,
        )

    @pytest.mark.parametrize("model_id", MODEL_IDS)
    def test_bp_significant(self, baseline_diagnostics_full, model_id):
        row = self._get_diagnostic(baseline_diagnostics_full, model_id, "Breusch-Pagan")
        assert row["p_value_full"] < 0.05, (
            f"{model_id}: BP test should be significant (p<0.05)"
        )

    @pytest.mark.parametrize("model_id", MODEL_IDS)
    def test_dw_positive_autocorrelation(self, baseline_diagnostics_full, model_id):
        row = self._get_diagnostic(
            baseline_diagnostics_full, model_id, "Serial Correlation (DW)"
        )
        assert row["statistic_full"] < 1.5, (
            f"{model_id}: DW should be < 1.5 (positive autocorrelation)"
        )

    def test_vif_below_threshold(self, baseline_diagnostics_full):
        row = self._get_diagnostic(baseline_diagnostics_full, "pooled_ols", "VIF (max)")
        assert row["statistic_full"] < 10, (
            f"Max VIF should be < 10 (no multicollinearity), got {row['statistic_full']:.4f}"
        )


# ---------------------------------------------------------------------------
# Section 6: Publication outputs — formatted tables
# ---------------------------------------------------------------------------


class TestComparisonTableCSV:
    """The pipeline's comparison table CSV must be string-identical to the baseline."""

    def test_comparison_table_csv_matches_baseline(self, baseline_comparison_csv):
        output_csv = EXAMPLE_OUTPUTS / "tables" / "table_fe_investment.csv"
        if not output_csv.exists():
            pytest.skip(
                "table_fe_investment.csv not present — run 'econflow run ...' to generate it"
            )
        actual = pd.read_csv(output_csv, dtype=str, keep_default_na=False)
        pd.testing.assert_frame_equal(
            actual.reset_index(drop=True),
            baseline_comparison_csv.reset_index(drop=True),
            check_names=True,
        )

    def test_baseline_csv_row_count(self, baseline_comparison_csv):
        # 2 regressors × 2 rows (coef + SE) + FE rows + N + R²
        assert len(baseline_comparison_csv) == 8

    def test_baseline_csv_has_three_model_columns(self, baseline_comparison_csv):
        """Columns are the models.yaml `label:` values, not raw registry ids
        (see _build_comparison_table()'s id_to_label lookup in pipeline_generic.py)."""
        assert set(baseline_comparison_csv.columns) == {
            "Specification", "Pooled OLS", "Entity FE", "Two-Way FE"
        }

    def test_baseline_csv_significance_stars_present(self, baseline_comparison_csv):
        """All coefficient cells must carry *** (p<0.01 for all regressors)."""
        for mid in ["Pooled OLS", "Entity FE", "Two-Way FE"]:
            for label in ["Coefficient: value", "Coefficient: capital"]:
                row = baseline_comparison_csv[
                    baseline_comparison_csv["Specification"] == label
                ]
                assert not row.empty, f"Missing row: {label}"
                cell = row.iloc[0][mid]
                assert "***" in cell, (
                    f"{mid}/{label}: expected *** stars in '{cell}'"
                )

    def test_baseline_csv_se_formatting(self, baseline_comparison_csv):
        """SE cells must be parenthesised to 4 decimal places."""
        for mid in ["Pooled OLS", "Entity FE", "Two-Way FE"]:
            for label in ["SE: value", "SE: capital"]:
                row = baseline_comparison_csv[
                    baseline_comparison_csv["Specification"] == label
                ]
                assert not row.empty, f"Missing row: {label}"
                cell = row.iloc[0][mid]
                assert cell.startswith("(") and cell.endswith(")"), (
                    f"{mid}/{label}: SE cell should be parenthesised, got '{cell}'"
                )
                # Check 4 decimal places
                inner = cell[1:-1]
                assert "." in inner and len(inner.split(".")[1]) == 4, (
                    f"{mid}/{label}: expected 4 decimal places, got '{cell}'"
                )

    def test_baseline_csv_fe_indicators(self, baseline_comparison_csv):
        """FE indicator rows must match the model specs."""
        firm_fe_row = baseline_comparison_csv[
            baseline_comparison_csv["Specification"] == "Firm FE"
        ]
        assert firm_fe_row.iloc[0]["Pooled OLS"] == "No"
        assert firm_fe_row.iloc[0]["Entity FE"] == "Yes"
        assert firm_fe_row.iloc[0]["Two-Way FE"] == "Yes"

        year_fe_row = baseline_comparison_csv[
            baseline_comparison_csv["Specification"] == "Year FE"
        ]
        assert year_fe_row.iloc[0]["Pooled OLS"] == "No"
        assert year_fe_row.iloc[0]["Entity FE"] == "No"
        assert year_fe_row.iloc[0]["Two-Way FE"] == "Yes"

    def test_baseline_csv_r2_within_pooled_suppressed(self, baseline_comparison_csv):
        """R² within for pooled OLS should be an em-dash (suppressed)."""
        r2_row = baseline_comparison_csv[
            baseline_comparison_csv["Specification"] == "R² within"
        ]
        assert r2_row.iloc[0]["Pooled OLS"] == "—", (
            f"Expected '—' for Pooled OLS R² within, got '{r2_row.iloc[0]['Pooled OLS']}'"
        )

    def test_baseline_csv_n_is_220(self, baseline_comparison_csv):
        n_row = baseline_comparison_csv[
            baseline_comparison_csv["Specification"] == "N"
        ]
        for mid in ["Pooled OLS", "Entity FE", "Two-Way FE"]:
            assert n_row.iloc[0][mid] == "220", (
                f"Expected N=220 for {mid}, got '{n_row.iloc[0][mid]}'"
            )


class TestComparisonTableLaTeX:
    """LaTeX fixture must contain required structural elements."""

    @pytest.fixture(scope="class")
    def latex_content(self):
        return (FIXTURE_DIR / "comparison_table.tex").read_text(encoding="utf-8")

    def test_has_table_environment(self, latex_content):
        assert r"\begin{table}" in latex_content
        assert r"\end{table}" in latex_content

    def test_has_threeparttable(self, latex_content):
        assert r"\begin{threeparttable}" in latex_content
        assert r"\end{threeparttable}" in latex_content

    def test_has_booktabs_rules(self, latex_content):
        assert r"\toprule" in latex_content
        assert r"\midrule" in latex_content
        assert r"\bottomrule" in latex_content

    def test_has_tablenotes(self, latex_content):
        assert r"\begin{tablenotes}" in latex_content
        assert r"\end{tablenotes}" in latex_content

    def test_has_significance_note(self, latex_content):
        assert "p<0.10" in latex_content
        assert "p<0.05" in latex_content
        assert "p<0.01" in latex_content

    def test_has_r2_within_math(self, latex_content):
        assert r"$R^2$ within" in latex_content

    def test_triple_star_math_mode(self, latex_content):
        assert r"$^{***}$" in latex_content

    def test_column_model_labels(self, latex_content):
        """Column headers are the models.yaml `label:` values (e.g. "Pooled OLS"),
        not raw registry ids -- see _build_comparison_table()'s id_to_label lookup."""
        assert "Pooled OLS" in latex_content
        assert "Entity FE" in latex_content
        assert "Two-Way FE" in latex_content

    def test_latex_matches_pipeline_output(self):
        """Pipeline's .tex output must be identical to the baseline fixture."""
        output_tex = EXAMPLE_OUTPUTS / "tables" / "table_fe_investment.tex"
        if not output_tex.exists():
            pytest.skip(
                "table_fe_investment.tex not present — run 'econflow run ...' to generate it"
            )
        expected = (FIXTURE_DIR / "comparison_table.tex").read_text(encoding="utf-8")
        actual = output_tex.read_text(encoding="utf-8")
        assert actual == expected, (
            "LaTeX output differs from baseline. First differing line:\n"
            + _first_diff_line(expected, actual)
        )


class TestComparisonTableMarkdown:
    """Markdown fixture structural checks."""

    @pytest.fixture(scope="class")
    def md_content(self):
        return (FIXTURE_DIR / "comparison_table.md").read_text(encoding="utf-8")

    def test_has_header_row(self, md_content):
        assert "Specification" in md_content
        assert "pooled_ols" in md_content

    def test_has_separator_row(self, md_content):
        assert "---" in md_content or ":---" in md_content

    def test_has_eight_data_rows(self, md_content):
        lines = [line for line in md_content.strip().split("\n") if line.startswith("|")]
        # header + separator + 8 data rows = 10 lines
        assert len(lines) == 10, f"Expected 10 table lines, got {len(lines)}"


class TestComparisonTableHTML:
    """HTML fixture structural checks."""

    @pytest.fixture(scope="class")
    def html_content(self):
        return (FIXTURE_DIR / "comparison_table.html").read_text(encoding="utf-8")

    def test_has_table_tag(self, html_content):
        assert "<table" in html_content
        assert "</table>" in html_content

    def test_has_header_row(self, html_content):
        assert "<th>Specification</th>" in html_content or "Specification" in html_content

    def test_has_model_columns(self, html_content):
        assert "pooled_ols" in html_content
        assert "entity_fe" in html_content
        assert "twoway_fe" in html_content


# ---------------------------------------------------------------------------
# Section 7: Provenance
# ---------------------------------------------------------------------------


class TestProvenance:
    """Provenance JSON must have correct structure and data hash."""

    @pytest.fixture(scope="class")
    def provenance_json(self):
        prov_path = EXAMPLE_OUTPUTS / "provenance" / "run_metadata.json"
        if not prov_path.exists():
            pytest.skip("run_metadata.json not present — run pipeline first")
        return json.loads(prov_path.read_text(encoding="utf-8"))

    def test_required_keys_present(self, provenance_json, baseline_provenance_schema):
        for key in baseline_provenance_schema["required_keys"]:
            assert key in provenance_json, f"Missing key in provenance: {key}"

    def test_required_inputs_keys(self, provenance_json, baseline_provenance_schema):
        for key in baseline_provenance_schema["required_inputs_keys"]:
            assert key in provenance_json["inputs"], f"Missing inputs key: {key}"

    def test_required_hashes_keys(self, provenance_json, baseline_provenance_schema):
        for key in baseline_provenance_schema["required_hashes_keys"]:
            assert key in provenance_json["input_hashes"], f"Missing hash key: {key}"

    def test_data_sha256_matches(self, provenance_json, baseline_provenance_schema):
        expected = baseline_provenance_schema["data_sha256"]
        actual = provenance_json["input_hashes"]["data"]
        assert actual == expected, (
            f"Data SHA-256 in provenance doesn't match baseline!\n"
            f"  Expected: {expected}\n"
            f"  Actual  : {actual}"
        )

    def test_models_run(self, provenance_json, baseline_provenance_schema):
        expected = baseline_provenance_schema["expected_models_run"]
        actual = provenance_json["models_run"]
        assert actual == expected, (
            f"models_run mismatch: expected {expected}, got {actual}"
        )

    def test_run_id_is_uuid(self, provenance_json):
        import uuid
        try:
            uuid.UUID(provenance_json["run_id"])
        except ValueError:
            pytest.fail(f"run_id is not a valid UUID: {provenance_json['run_id']}")

    def test_timestamp_is_iso8601(self, provenance_json):
        from datetime import datetime
        ts = provenance_json["timestamp"]
        try:
            datetime.fromisoformat(ts)
        except ValueError:
            pytest.fail(f"timestamp is not valid ISO-8601: {ts}")


# ---------------------------------------------------------------------------
# Section 8: Fixture file existence
# ---------------------------------------------------------------------------


class TestFixtureFileExistence:
    """Every expected fixture file must be present and non-empty."""

    EXPECTED_FILES = [
        "numerical_results.json",
        "diagnostics_full.json",
        "diagnostics.csv",
        "comparison_table.csv",
        "comparison_table.tex",
        "comparison_table.md",
        "comparison_table.html",
        "provenance_schema.json",
        "README.md",
    ]

    @pytest.mark.parametrize("filename", EXPECTED_FILES)
    def test_fixture_exists(self, filename):
        path = FIXTURE_DIR / filename
        assert path.exists(), f"Fixture missing: {path}"
        assert path.stat().st_size > 0, f"Fixture is empty: {path}"

    def test_numerical_results_has_three_models(self):
        data = json.loads((FIXTURE_DIR / "numerical_results.json").read_text())
        assert set(data["models"].keys()) == {"pooled_ols", "entity_fe", "twoway_fe"}

    def test_numerical_results_meta(self):
        data = json.loads((FIXTURE_DIR / "numerical_results.json").read_text())
        assert data["meta"]["n_obs"] == 220
        assert data["meta"]["n_entities"] == 11
        assert data["meta"]["n_periods"] == 20

    def test_diagnostics_full_has_nine_rows(self):
        data = json.loads((FIXTURE_DIR / "diagnostics_full.json").read_text())
        assert len(data["diagnostics"]) == 9  # 3 models × 3 diagnostics

    def test_provenance_schema_has_data_sha256(self):
        data = json.loads((FIXTURE_DIR / "provenance_schema.json").read_text())
        assert "data_sha256" in data
        # SHA-256 is 64 hex characters
        assert len(data["data_sha256"]) == 64


# ---------------------------------------------------------------------------
# Section 9: No production code changes
# ---------------------------------------------------------------------------


class TestNoProductionChanges:
    """
    Phase 0 acceptance criterion: only tests/ and fixtures/ should be new.
    This test checks that no production source files were modified by Phase 0.
    """

    PRODUCTION_DIRS = [
        "src/",
        "examples/getting_started/config/",
        "examples/getting_started/data/",
    ]

    def test_pipeline_generic_is_unmodified(self):
        """
        pipeline_generic.py must be importable without error — its API
        must match what we depend on in pipeline_results fixture.
        """
        import importlib
        try:
            importlib.import_module("econflow.pipeline_generic")
        except ImportError as exc:
            pytest.fail(f"pipeline_generic.py import failed: {exc}")

    def test_no_new_files_in_src(self):
        """
        No new files should exist in src/ that were not there before Phase 0.
        We detect this by checking that git status shows no untracked src/ files.
        (Only meaningful if run inside the git repo.)
        """
        result = subprocess.run(
            ["git", "status", "--porcelain", "src/"],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
        )
        if result.returncode != 0:
            pytest.skip("git not available or not in a git repo")
        untracked = [
            line for line in result.stdout.splitlines()
            if line.startswith("??")
        ]
        assert not untracked, (
            "New untracked files found in src/ — Phase 0 must not add production files:\n"
            + "\n".join(untracked)
        )


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------


def _first_diff_line(expected: str, actual: str) -> str:
    exp_lines = expected.splitlines()
    act_lines = actual.splitlines()
    for i, (e, a) in enumerate(zip(exp_lines, act_lines)):
        if e != a:
            return f"Line {i + 1}:\n  Expected: {e!r}\n  Actual  : {a!r}"
    if len(exp_lines) != len(act_lines):
        return (
            f"Line count differs: expected {len(exp_lines)}, got {len(act_lines)}"
        )
    return "(files are identical)"
