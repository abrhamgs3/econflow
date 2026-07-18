# Expected Outputs

This directory contains reference outputs for the getting started tutorial.
Use them to verify that your installation is working correctly.

## Verification

After running the tutorial pipeline, compare your output against these files:

```bash
# Check regression table matches the reference
diff outputs/tables/table_fe_investment.csv expected_outputs/table_fe_investment.csv

# Check diagnostics match the reference
diff outputs/tables/diagnostics.csv expected_outputs/diagnostics.csv
```

If the files match exactly, your environment is producing reproducible results.

## Files

| File | Description |
|------|-------------|
| `table_fe_investment.csv` | Regression table — three specifications side by side |
| `table_fe_investment.tex` | LaTeX version, ready to paste into a paper |
| `diagnostics.csv` | Post-estimation diagnostics (VIF, Breusch-Pagan, Durbin-Watson) for all three models |

## Interpretation Guide

**Regression table — key coefficients to check:**

| Coefficient | Expected value | Tolerance |
|-------------|---------------|-----------|
| `value` (Entity FE) | 0.1101 | ± 0.0010 |
| `capital` (Entity FE) | 0.3100 | ± 0.0010 |
| R² within (Entity FE) | 0.7667 | ± 0.0005 |

**Diagnostics — key statistics to check:**

| Model | Diagnostic | Expected statistic | Tolerance |
|-------|------------|-------------------|-----------|
| `pooled_ols` | Breusch-Pagan | 82.2029 | ± 0.0010 |
| `pooled_ols` | Durbin-Watson | 0.3815 | ± 0.0010 |
| `entity_fe` | Breusch-Pagan | 77.8714 | ± 0.0010 |
| `twoway_fe` | Breusch-Pagan | 68.7760 | ± 0.0010 |

Small floating-point differences across platforms are normal.
Values outside the tolerance range indicate a software version conflict —
run `econflow doctor` to check your dependency versions.
