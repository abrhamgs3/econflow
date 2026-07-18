# Blind Replication Example

This directory demonstrates the EconFlow Replication Engine. It contains a
complete, self-contained project that can be reproduced by anyone with
EconFlow installed, starting only from this directory.

The word "blind" means that the replicator begins with no knowledge of the
estimation results. The replication engine re-runs the pipeline from scratch,
then compares its outputs against the `original_outputs/` reference.

---

## Dataset

**File:** `data/investment_panel.csv`

A balanced panel of 6 fictional firms over 15 years (1990–2004).

| Column | Description |
|--------|-------------|
| `firm` | Firm identifier (entity dimension) |
| `year` | Year (time dimension) |
| `invest` | Gross investment (dependent variable) |
| `market_value` | Firm market value (regressor) |
| `capital_stock` | Accumulated capital stock (regressor) |

**True data-generating process** (for evaluation only — not used in estimation):

```
invest = 1.8 × market_value + 0.6 × capital_stock + firm_FE + ε
```

All three estimators (pooled OLS, entity FE, two-way FE) should recover
coefficients close to 1.8 and 0.6. The entity fixed effects estimator
removes unobserved firm heterogeneity and is consistent under this DGP.

---

## Project Structure

```
blind_replication/
├── config/
│   ├── config.yaml           Dataset and variable declarations
│   ├── models.yaml           Three estimator specifications
│   └── outputs.yaml          Output directory and table filenames
├── data/
│   └── investment_panel.csv  The panel dataset (90 observations)
├── original_outputs/
│   └── tables/
│       └── comparison_table.csv  Reference results (produced by original author)
├── outputs/                  Created by econflow run (gitignored)
└── README.md                 This file
```

---

## Reproducing

### Step 1 — Inspect the project

```bash
econflow inspect examples/blind_replication/
```

Expected output: all checks pass (config found, data found, estimators registered).

### Step 2 — Reproduce the pipeline

```bash
econflow reproduce examples/blind_replication/
```

This command:
1. Runs the inspection checks
2. Executes the analysis pipeline in a subprocess
3. Compares outputs against `original_outputs/`
4. Writes a `replication_report.md` and `replication_report.json`

Expected output: all three models run, comparison table matches, overall PASS.

### Step 3 — Compare manually (optional)

```bash
econflow compare \
    examples/blind_replication/original_outputs/ \
    examples/blind_replication/replication_outputs/tables/
```

---

## Reference Results

`original_outputs/tables/comparison_table.csv` contains the reference results
produced by the original pipeline run. The replication engine compares its
reproduced outputs against these.

```
Specification,Pooled OLS,Entity Fixed Effects,Two-way Fixed Effects
Coefficient: market_value,1.7908***,1.7947***,1.7965***
SE: market_value,(0.006),(0.006),(0.007)
Coefficient: capital_stock,0.6098***,0.6013***,0.6019***
SE: capital_stock,(0.022),(0.020),(0.022)
Firm FE,No,Yes,Yes
Year FE,No,No,Yes
N,90,90,90
```

All three estimators recover the true coefficients (1.8 and 0.6) closely.
The entity FE estimator removes firm-specific heterogeneity and is the
consistent specification under this DGP.

---

## What a Successful Replication Looks Like

```
$ econflow reproduce examples/blind_replication/

  EconFlow reproduce
  Project: examples/blind_replication/
  Output:  examples/blind_replication/replication_outputs/

  [1/4] Inspecting project …
       ✔ Python version: 3.11.x
       ✔ Config file: config/config.yaml
       ✔ Models config: config/models.yaml
       ✔ Outputs config: config/outputs.yaml
       ✔ Data file: investment_panel.csv (6 KB)
       ⚠ Data checksum: No provenance record found
       ✔ Estimator registry: 3 estimator(s) registered: OLS, FE, FE
       ✔ Dependencies: econflow 0.1.0  pandas ...

  [2/4] Building execution plan …
         2 step(s) planned

  [3/4] Executing pipeline …
       ✔ Validate project configuration (0.3s)
       ✔ Execute analysis pipeline (1.1s)

  [4/4] Comparing outputs …
       ✔ tables/comparison_table.csv: All 8 rows match (max |Δ| = 0.00e+00)

  Report saved: replication_report.md  replication_report.json

  ✔ PASS — Replication successful
  Elapsed: 1.4 s
  Outputs: 3 file(s) in examples/blind_replication/replication_outputs/
```

---

## Notes for Replicators

- The data checksum warning is expected if no prior `econflow run` has been
  executed in this directory (no provenance record exists to compare against).
  This is a warn, not a failure.

- Coefficient estimates are stable to machine precision across platforms.
  The comparison uses a tolerance of 1e-6 by default.

- If you observe a mismatch, check that your EconFlow version matches the
  version that produced `original_outputs/`. Run `econflow --version`.
