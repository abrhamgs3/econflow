# Phase 0 Baseline Fixtures

These fixtures capture the **exact outputs** of `pipeline_generic.py` run against the
Grunfeld (1958) investment dataset with the `getting_started` example configuration.
They are the numerical gate for the `EstimationDispatcher` migration (see
`docs/architecture/MIGRATION_ROADMAP.md`).

## Dataset

| Property | Value |
|---|---|
| Name | Grunfeld (1958) |
| Observations | 220 |
| Entities | 11 firms |
| Periods | 20 years (1935–1954) |
| Dependent | `invest` |
| Regressors | `value`, `capital` |
| SHA-256 | `d73bb76112ccf74ef6c85d4780e7dc0fb7ded7c671f1f51cd94831b3472f2ff9` |

## Models

| ID | Estimator | Entity FE | Time FE | Covariance |
|---|---|---|---|---|
| `pooled_ols` | PooledOLS | No | No | Unadjusted |
| `entity_fe` | PanelOLS | Yes | No | Clustered by entity |
| `twoway_fe` | PanelOLS | Yes | Yes | Clustered by entity |

## Files

### `numerical_results.json`
Full float64-precision estimation results for all three models. Fields captured:
- `params` — coefficients (3 regressors incl. const)
- `std_errors` — standard errors
- `tstats` — t-statistics
- `pvalues` — p-values
- `conf_int` — 95% confidence intervals (lower + upper)
- `nobs` — observation count
- `rsquared`, `rsquared_within`, `rsquared_between`, `rsquared_overall`
- `f_statistic`, `f_pvalue`
- `loglik` — log-likelihood

Regression tests assert that future pipeline runs reproduce these values to within
the tolerances specified in `test_pipeline_baseline.py`.

### `diagnostics_full.json`
Full float64-precision diagnostic values for 9 diagnostic rows (3 models × 3 diagnostics).
Rounded values in `diagnostics.csv` are derived from these.

### `diagnostics.csv`
Rounded diagnostic table exactly matching `outputs/tables/diagnostics.csv` produced by
the pipeline. Tests assert string-level equality against the pipeline's actual output file.

### `comparison_table.csv`
Comparison table produced by `_build_comparison_table()` with `decimal_places=4`.
Contains: coefficient rows (with significance stars), SE rows, FE indicator rows,
N row, R² within row.

**Note:** The pre-existing `examples/getting_started/outputs/tables/table_fe_investment.csv`
was produced by an older pipeline version (`decimal_places=3`). This fixture captures
what the **current** pipeline produces (`decimal_places=4`, i.e. `(0.0055)` not `(0.006)`).

### `comparison_table.tex`
LaTeX booktabs table with threeparttable and significance footnote, produced by
`_write_latex()` with `decimal_places=4`.

### `comparison_table.md`
GitHub-Flavored Markdown table produced by `_write_markdown()`.

### `comparison_table.html`
HTML table produced by `_write_html()`.

### `provenance_schema.json`
Required keys and expected data SHA-256 for `run_metadata.json`. Tests assert
structural integrity and data hash — not run_id or timestamp (those change per run).

## Tolerances

Defined in `test_pipeline_baseline.py`:

| Quantity | Tolerance |
|---|---|
| Coefficients | `rtol=1e-10` (relative) |
| Standard errors | `rtol=1e-10` (relative) |
| t-statistics | `rtol=1e-10` (relative) |
| p-values | `atol=1e-12` (absolute, handles values near 0) |
| Confidence intervals | `rtol=1e-10` (relative) |
| R² variants | `rtol=1e-10` (relative) |
| F-statistic | `rtol=1e-8` (relative, slightly looser) |
| Log-likelihood | `rtol=1e-10` (relative) |
| Diagnostic statistics | `rtol=1e-6` (relative, BP/DW rounding) |

## Invariants Verified by Tests

1. Data SHA-256 matches across all runs
2. All coefficient signs are preserved exactly
3. Significance stars are unchanged (***/**/* thresholds at 0.01/0.05/0.10)
4. FE indicator rows show correct Yes/No values
5. Formatted CSV/LaTeX/MD/HTML outputs are string-identical
6. Provenance JSON contains all required keys with correct data hash
7. N=220 for all three models
