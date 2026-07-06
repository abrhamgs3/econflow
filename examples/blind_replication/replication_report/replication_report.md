# EconFlow Reproducibility Report

**Generated:** 2026-06-29T04:37:09.496595+00:00
**Overall status:** ✔ PASS

## Pre-flight Inspection

**Project:** `/sessions/trusting-amazing-keller/mnt/AI and Productivity/econflow/examples/blind_replication`
**Timestamp:** 2026-06-29T04:37:09.556762+00:00
**Status:** ✔ PASS

| Check | Status | Message |
|-------|--------|---------|
| Python version | ✔ pass | Python 3.10.12 |
| Config file | ✔ pass | config/config.yaml |
| Models config | ✔ pass | config/models.yaml |
| Outputs config | ✔ pass | config/outputs.yaml |
| Data file | ✔ pass | investment_panel.csv (3 KB) |
| Data checksum | ✔ pass | SHA-256 verified: c0afa5b354c61000… |
| Estimator registry | ✔ pass | 3 estimator(s) registered: ols, fe, fe |
| Dependencies | ✔ pass | econflow 0.1.0  pandas 2.3.3  linearmodels 7.0  statsmodels 0.14.6  numpy 2.2.6  pyyaml 6.0.3 |

*8 passed, 0 warned, 0 failed*

## Replication Execution

**Run ID:** `30663610-0b99-44dc-8ccf-5eef0886bea2`
**Timestamp:** 2026-06-29T04:37:11.117912+00:00
**Status:** ✔ SUCCESS
**Elapsed:** 1.5 s
**Output directory:** `examples/blind_replication`

### Steps

| Step | Status | Elapsed | Notes |
|------|--------|---------|-------|
| Validate project configuration | ✔ success | 0.4s |  |
| Execute analysis pipeline | ✔ success | 1.0s |  |

**Outputs produced:** 5 file(s)
  - `examples/blind_replication/outputs/provenance/run_metadata.json`
  - `examples/blind_replication/outputs/replication_report.json`
  - `examples/blind_replication/outputs/replication_report.md`
  - `examples/blind_replication/outputs/tables/comparison_table.csv`
  - `examples/blind_replication/outputs/tables/comparison_table.csv.csv`

## Output Comparison

**Baseline:** `/sessions/trusting-amazing-keller/mnt/AI and Productivity/econflow/examples/blind_replication/original_outputs/tables`
**Replica:** `/sessions/trusting-amazing-keller/mnt/AI and Productivity/econflow/examples/blind_replication/outputs/tables`
**Status:** ✔ PASS
**Numeric tolerance:** 1e-06

| File | Status | Notes |
|------|--------|-------|
| `comparison_table.csv` | ✔ match | All 8 rows match (max |Δ| = 0.00e+00) |

*1 matched, 0 mismatched, 0 missing*
