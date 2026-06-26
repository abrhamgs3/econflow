# Expected Outputs

This directory contains reference outputs for the getting started tutorial.
Use them to verify that your installation is working correctly.

## Verification

After running the tutorial pipeline, compare your output against these files:

```bash
# Check your table matches the reference
diff outputs/tables/table_fe_investment.csv expected_outputs/table_fe_investment.csv
```

If the files match exactly, your environment is producing reproducible results.

## Files

| File | Description |
|------|-------------|
| `table_fe_investment.csv` | Regression table — three specifications side by side |
| `table_fe_investment.tex` | LaTeX version, ready to paste into a paper |

## Interpretation Guide

The key numbers to check:

| Coefficient | Expected value | Tolerance |
|-------------|---------------|-----------|
| `value` (Entity FE) | 0.1101 | ± 0.0010 |
| `capital` (Entity FE) | 0.3100 | ± 0.0010 |
| R² within (Entity FE) | 0.7667 | ± 0.0005 |

Small floating-point differences across platforms are normal.
Values outside the tolerance range indicate a software version conflict —
run `econflow doctor` to check your dependency versions.
