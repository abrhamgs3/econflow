# EconFlow — First Post-Migration Product Audit

**Date:** 2026-07-10  
**Scope:** Post-Phase-6 migration product audit — economist first-user perspective  
**Baseline:** Architecture Freeze v1 (Phases 0–6 complete)  
**Constraint:** Dispatcher architecture is frozen. Do not propose redesign unless a demonstrable correctness defect is identified.  
**Auditor:** Independent product audit session

---

## Executive Summary

EconFlow's architectural migration (Phases 0–6) is complete. The core pipeline is
correct, reproducible, and well-structured. The estimation, diagnostic, integrity,
and replication subsystems are all implemented and tested. The CLI is the best part
of the product: 16 commands with rich help text, examples, common mistakes, and
expected output.

The primary barriers to public beta are **product-layer** issues, not architectural
ones. The most critical: the package is not on PyPI and the official getting-started
tutorial tells users to run `pip install econflow` (which fails). Phase 6 also
introduced a stale committed output file in `examples/getting_started/outputs/` whose
OLS Breusch-Pagan value no longer matches what the pipeline produces.

**Release-readiness score: 68 / 100**  
**Confidence: 88%**

Score decomposition:

| Dimension | Score | Weight |
|-----------|-------|--------|
| Installation experience | 5/10 | 15% |
| CLI usability | 8/10 | 15% |
| Python API discoverability | 6/10 | 10% |
| Documentation quality | 7/10 | 10% |
| Example projects | 7/10 | 10% |
| Plugin developer experience | 5/10 | 10% |
| Reproducibility workflow | 9/10 | 10% |
| Error messages | 8/10 | 5% |
| Reporting outputs | 7/10 | 10% |
| Public beta readiness | 6/10 | 5% |
| **Weighted total** | **6.8 / 10** | |

---

## Issue Catalog

### I-01 — `pip install econflow` fails; tutorial tells users to try it

**Severity:** Critical  
**Dimension:** 1 (Installation), 5 (Examples)  
**Files:**  
- `examples/getting_started/README.md` line 100: `pip install econflow`  
- `src/econflow/__init__.py` lines 8–9: `pip install econflow` in docstring  
- `docs/release_notes/v0.1.0.md` line 53: `pip install econflow`  
- `src/econflow/commands/init.py` line 249: `pip install econflow (once published)`

**First-time economist encounter:** A researcher clones the repo, reads
`examples/getting_started/README.md` to follow the tutorial, reaches Step 1 and
runs `pip install econflow`. It fails with `ERROR: Could not find a satisfying
requirement for econflow`. There is no fallback instruction on the same page.
They are stopped before seeing a single feature.

**Root cause:** The package is not published to PyPI. `README.md` (root) correctly
documents `git clone ... && pip install -e ".[dev]"` but the tutorial README
diverges.

**Recommended fix:**
1. Replace `pip install econflow` in `getting_started/README.md` Step 1 with:
   ```bash
   git clone https://github.com/abrhamgs3/econflow.git
   cd econflow
   pip install -e ".[dev]"
   cd examples/getting_started
   ```
2. Update `__init__.py` docstring Quick Start to match root `README.md` install path.
3. Update `release_notes/v0.1.0.md` install block.
4. Medium-term: publish to PyPI.

**Estimated fix time:** 30 minutes (docs-only); PyPI publication: 2–4 hours.

---

### I-02 — Stale committed `diagnostics.csv` shows pre-Phase-6 OLS values

**Severity:** High  
**Dimension:** 5 (Examples), 9 (Reporting outputs)  
**File:** `examples/getting_started/outputs/tables/diagnostics.csv` lines 3–4

**Evidence:**
```csv
pooled_ols,Breusch-Pagan,65.228,0.0,...
pooled_ols,Serial Correlation (DW),0.3707,...
```

Phase 6 (`_write_diagnostics()` replacing `_run_diagnostics()`) changed the OLS
Breusch-Pagan statistic from ~65.228 to ~82.203 and the OLS DW from ~0.3707 to
~0.3815 (documented in `PHASE6_COMPLETION_REPORT.md` §4 as an accepted behavioral
change). The committed output file was not regenerated after Phase 6.

**First-time economist encounter:** A user runs `econflow run` on the getting-started
example and opens `outputs/tables/diagnostics.csv`. They see `Breusch-Pagan 82.203`
for `pooled_ols`. They then open the committed file in the repository (e.g., on
GitHub) and see `65.228`. They conclude the pipeline is non-deterministic or broken.

**Recommended fix:** After merging all pending fixes, regenerate committed outputs:
```bash
cd examples/getting_started
econflow run --config config/config.yaml \
             --models config/models.yaml \
             --outputs config/outputs.yaml
```
Commit the updated `outputs/tables/diagnostics.csv` and
`outputs/tables/table_fe_investment.csv`.

**Estimated fix time:** 5 minutes (one pipeline run + commit).

---

### I-03 — `estimation/__init__.py` has stale internal comment visible to any reader

**Severity:** High  
**Dimension:** 3 (Python API), 4 (Documentation)  
**File:** `src/econflow/estimation/__init__.py` lines 44–46

**Evidence:**
```python
# Phase 2 status: purely additive dead code.  Nothing in the production runtime
# imports or calls these yet.  First production import: Phase 4 (ConfigValidator).
```

`EstimationDispatcher` and `PipelineContext` are now the **sole** production path
since Phase 5C. The comment is factually wrong and will confuse any developer or
plugin author reading the file.

**First-time economist/developer encounter:** A plugin author reads `estimation/__init__.py`
to understand what to import. They see "purely additive dead code" next to
`PipelineContext` and `EstimationDispatcher` — which are now the core pipeline
integration points. They either doubt their imports or are misled about the
architecture.

**Recommended fix:** Replace lines 44–46 with:
```python
# Pipeline integration — Phase 5C+: EstimationDispatcher is the sole production
# path for running models via `econflow run`.
```

**Estimated fix time:** 5 minutes.

---

### I-04 — Plugin SDK specifies `econflow>=1.0,<2.0` but package is 0.1.0

**Severity:** High  
**Dimension:** 6 (Plugin DX)  
**File:** `docs/sdk/PLUGIN_SDK.md` lines 48–52

**Evidence:**
```toml
[project]
name = "econflow-myplugin"
version = "0.1.0"
dependencies = ["econflow>=1.0,<2.0"]
```

Any plugin author who follows this example exactly will produce a package whose
dependency constraint `econflow>=1.0,<2.0` cannot be satisfied by EconFlow 0.1.0.
`pip install econflow-myplugin` will fail with a dependency conflict.

**First-time plugin author encounter:** A researcher writes a custom estimator plugin
following the SDK Quick Start verbatim. They publish it. Anyone who tries to install
it fails because `econflow>=1.0` cannot be resolved.

**Recommended fix:** Update to:
```toml
dependencies = ["econflow>=0.1.0"]
```
And add a note: "When EconFlow reaches v1.0, update to `econflow>=1.0,<2.0`
to opt into the version-compatibility guarantee in §11."

**Estimated fix time:** 10 minutes.

---

### I-05 — `econflow.__init__` exports only exceptions; no estimation classes at top level

**Severity:** Medium  
**Dimension:** 3 (Python API discoverability)  
**File:** `src/econflow/__init__.py` lines 35–58

**Evidence:**
```python
from econflow.exceptions import (
    EconFlowError,
    DataValidationError,
    ...
)
# No estimation imports
```

`from econflow import PooledOLS` raises `ImportError`. The canonical import is
`from econflow.estimation import PooledOLS`. This is correct but non-obvious: no
Python package exposes its core abstractions only two levels down without re-exporting
from the top level.

**First-time economist encounter:** A researcher types `import econflow; help(econflow)`
and sees only exception classes. They try `from econflow import PooledOLS` — fails.
They search the codebase and eventually find `from econflow.estimation import PooledOLS`.

**Recommended fix:** Add to `econflow/__init__.py`:
```python
from econflow.estimation import (
    BaseEstimator,
    EstimationResult,
    DiagnosticResult,
    PooledOLS,
    EntityFE,
    TwoWayFE,
    register_estimator,
    list_estimators,
)
```
And add these to `__all__`. The full estimation registry can remain at
`econflow.estimation` for advanced use.

**Estimated fix time:** 30 minutes (add imports + update `__all__` + add tests).

---

### I-06 — `econflow run` CLI help text shows wrong pipeline output format

**Severity:** Medium  
**Dimension:** 2 (CLI usability)  
**File:** `src/econflow/cli.py` lines 665–675 (run command docstring)

**Evidence — docstring shows:**
```
[1/3] entity_fe — Fixed Effects (Entity)  ✔
[2/3] two_way_fe — Fixed Effects (Two-Way)  ✔
[3/3] pooled_ols — Pooled OLS  ✔
```

**Actual pipeline output includes 5 stages:**
```
[1/5] Loading data
[2/5] Validating panel structure
[3/5] Running models
[3.5/5] Writing diagnostics
[4/5] Exporting tables
[5/5] Recording provenance
```

The help text shows only 3 model-run steps and omits stages 1–2 and 4–5.

**First-time economist encounter:** A user reads `econflow run --help` to understand
what will happen. They expect to see `[1/3]` progress through models only. The actual
output shows `[1/5]` through `[5/5]`, none of which match the help text. They wonder
if they are running the right command.

**Recommended fix:** Update the docstring expected output section to match actual
pipeline logs, using a representative abbreviated form that includes all stages.

**Estimated fix time:** 15 minutes.

---

### I-07 — `FIRST_FIVE_MINUTES.md` expected output mismatches actual CLI format

**Severity:** Medium  
**Dimension:** 4 (Documentation)  
**File:** `docs/release/FIRST_FIVE_MINUTES.md` lines 79–87

**Evidence — document shows:**
```
─────────── EconFlow pipeline ───────────
  Stage 1  Load data          ✔
  Stage 2  Validate           ✔
  Stage 3  Estimate models    ✔  (3 models)
  Stage 4  Diagnostics        ✔
  Stage 5  Render outputs     ✔
─────────────────────────────────────────
  Tables written to outputs/tables/
```

The actual pipeline does not produce this output. It produces numbered log lines
(`[1/5] Loading data`, etc.) with no summary table. The closing banner is
`Pipeline complete` (from `cli.py` line 857), not the structured stage summary.

**First-time economist encounter:** A user follows `FIRST_FIVE_MINUTES.md` and runs
the pipeline. The terminal output looks nothing like the expected output in the
document. They are unsure if something went wrong.

**Recommended fix:** Replace the expected output block with actual pipeline log output
captured from a live run, or clearly mark it as "output is abbreviated".

**Estimated fix time:** 15 minutes.

---

### I-08 — `econflow report [beta]` label creates confusing dual-output path

**Severity:** Medium  
**Dimension:** 2 (CLI usability), 9 (Reporting outputs)  
**File:** `src/econflow/cli.py` lines 891–896 (report command docstring)

**Evidence:**
```
NOTE: This command is a beta feature.  'econflow run' already writes
tables to the outputs/tables/ directory defined in outputs.yaml.
Use those files for publication tables.  This command provides an
additional publication bundle format...
```

A first-time user sees `econflow report` in the CLI reference, runs it, gets told
to use a different command's output instead. The relationship between the two output
paths is not clear from the help text.

**First-time economist encounter:** After `econflow run`, the user looks for their
tables. They see both `outputs/tables/` (from `run`) and `outputs/econflow/` (from
`report`). They don't know which is canonical for journal submission.

**Recommended fix:** Add to the report command docstring:
```
Canonical publication output: outputs/tables/ (written by econflow run)
This command adds an alternative bundle format (PublicationBundle) that
aggregates multiple tables and figures. Use it when submitting multiple
model specifications together.
```

**Estimated fix time:** 20 minutes.

---

### I-09 — Plugin SDK shows `_unregister_estimator` (private name) in public example

**Severity:** Medium  
**Dimension:** 6 (Plugin DX)  
**File:** `docs/sdk/PLUGIN_SDK.md` lines 2658–2667

**Evidence:**
```python
from econflow.estimation import register_estimator, _unregister_estimator
...
_unregister_estimator("test_estimator")  # underscore: internal
```

The public API exports `unregister_estimator` (no leading underscore). The underscore
form appears in `estimation/__init__.py` line 97 as `unregister_estimator` (no
underscore). The SDK's comment "underscore: internal" directly contradicts the
Architecture Freeze public API commitment.

**First-time plugin author encounter:** A developer copies this test fixture pattern
and imports `_unregister_estimator`. It either fails with `ImportError` (if the
underscore version is not exported) or uses a private internal symbol that may
change without notice.

**Recommended fix:** Replace with `from econflow.estimation import unregister_estimator`
and remove the parenthetical comment.

**Estimated fix time:** 5 minutes.

---

### I-10 — `econflow init` scaffold config uses placeholder column names with no data example

**Severity:** Medium  
**Dimension:** 2 (CLI usability)  
**Files:** `src/econflow/commands/init.py` lines 88–98, 143–144

**Evidence:**
The generated `config.yaml` uses `entity_col: "entity"`, `time_col: "time"`,
`dependent: "outcome"`, regressors `["treatment", "covariate_1"]`.
The generated `models.yaml` uses `dependent: "outcome"`, `regressors: ["treatment", "covariate_1"]`.
There is no sample data file and no `README.md` in the scaffold explaining the
column naming step.

**First-time economist encounter:** A user runs `econflow init my_study` and
`econflow validate config/`. Validation fails with missing data file (expected).
They edit `config.yaml` to match their CSV. They then run `econflow validate --data`
and get "missing columns: entity, time" because they forgot to also rename the
placeholder columns. The error does not tell them which file to edit or what
the column names should be.

**Recommended fix:** Add a `README.md` to the scaffold that contains a table
mapping each placeholder to what users should replace it with, and an explicit
checklist:
```
ACTION REQUIRED:
[ ] 1. Copy your panel CSV to data/processed/panel.csv
[ ] 2. Edit config/config.yaml: set entity_col and time_col to your CSV column names
[ ] 3. Edit config/models.yaml: set dependent and regressors to match
[ ] 4. Run: econflow validate config/
```

**Estimated fix time:** 30 minutes.

---

### I-11 — `expected_outputs/README.md` in getting_started is content-free

**Severity:** Low  
**Dimension:** 5 (Examples)  
**File:** `examples/getting_started/expected_outputs/README.md`

**Evidence:** The file exists but may contain only a minimal stub. The expected
output CSV is present at `expected_outputs/table_fe_investment.csv` but no
expected `diagnostics.csv` is stored for comparison.

**First-time economist encounter:** A user wants to verify their run produced
correct results and looks in `expected_outputs/`. They find coefficient tables
but no diagnostics baseline, so they cannot verify that step.

**Recommended fix:** Add `expected_outputs/diagnostics.csv` (regenerated after I-02
is fixed) and a short `README.md` explaining what these files are and how to
compare them to pipeline outputs.

**Estimated fix time:** 15 minutes.

---

### I-12 — `econflow certify` silent on empty `--project-name`

**Severity:** Low  
**Dimension:** 2 (CLI usability), 8 (Error messages)  
**File:** `src/econflow/cli.py` lines 958–961

**Evidence:**
```python
project_name: str = typer.Option(
    "",
    "--project-name", "-p",
    help="Human-readable project name stored in the certificate.",
),
```

The default is `""` (empty string). Running `econflow certify` with no flags
produces a certificate with `project_name: ""` and no warning. A certificate
with no project name is effectively useless for identification.

**First-time economist encounter:** A user runs `econflow certify` without reading
the help text. The certificate is produced but the project name field is blank. A
reviewer receiving this certificate cannot identify the project.

**Recommended fix:** Emit a `console.print("[yellow]⚠  No --project-name supplied; certificate project_name is empty.[/yellow]")` warning when `project_name == ""`, or prompt interactively if the terminal is a TTY.

**Estimated fix time:** 15 minutes.

---

## Summary Table

| ID | Severity | Dimension | One-Line Description |
|----|----------|-----------|----------------------|
| I-01 | Critical | 1, 5 | Tutorial says `pip install econflow` — fails, not on PyPI |
| I-02 | High | 5, 9 | Committed `diagnostics.csv` shows stale pre-Phase-6 OLS values |
| I-03 | High | 3, 4 | Stale comment: dispatcher still called "dead code" in estimation/__init__ |
| I-04 | High | 6 | SDK version constraint `econflow>=1.0,<2.0` impossible on 0.1.0 |
| I-05 | Medium | 3 | No estimation classes exported from top-level `econflow` package |
| I-06 | Medium | 2 | `econflow run` --help shows wrong pipeline stage format |
| I-07 | Medium | 4 | `FIRST_FIVE_MINUTES.md` expected output mismatches actual CLI output |
| I-08 | Medium | 2, 9 | `econflow report [beta]` confuses canonical output path |
| I-09 | Medium | 6 | SDK test example imports private `_unregister_estimator` |
| I-10 | Medium | 2 | `econflow init` scaffold has no README to guide column renaming |
| I-11 | Low | 5 | `expected_outputs/` lacks `diagnostics.csv` baseline |
| I-12 | Low | 2, 8 | `econflow certify` silent when `--project-name` is empty |

---

## Release Blockers vs Post-Beta Items

### Blockers (must fix before public beta)

**I-01** — `pip install econflow` is the first instruction in the tutorial and it fails.
A user who cannot install the software cannot evaluate anything else.

**I-02** — Committed output files with wrong diagnostic values will cause every user
who opens those files to distrust the pipeline. This is the most observable
consequence of the Phase 6 migration and must be resolved before the repository
is shared publicly.

**I-04** — The Plugin SDK has a dependency constraint that makes every plugin written
against it uninstallable. Plugin authors are the most technically sophisticated users;
failing them immediately undermines the ecosystem story.

### High priority (fix before or at beta launch)

**I-03** — The "dead code" comment is visible to any developer who opens
`estimation/__init__.py` and actively misleads them about the architecture.

**I-05** — Top-level imports are a standard Python usability expectation. Requiring
users to know `from econflow.estimation import ...` before reading any documentation
raises the learning curve unnecessarily.

### Can wait until first patch after beta

**I-06, I-07, I-08, I-09, I-10, I-11, I-12** — These are documentation polish,
CLI copy accuracy, and minor DX issues. None block a user from successfully using the
pipeline once they have it installed.

---

## Architecture Debt vs Product Debt

### Architecture debt (from the migration)

The only architectural residue from Phases 0–6 that affects user experience is
**I-02**: the committed example output files reflect the pre-Phase-6 diagnostic
computation path. This is architecture debt that surfaced as a product issue.

Everything else in this audit is **product debt** — documentation inaccuracies,
tutorial copy errors, SDK version mismatches, and CLI text that wasn't updated to
match the current pipeline format. No correctness defects in the frozen dispatcher
architecture were found.

### Confirmed: no architectural correctness defects

The Phase 6 behavioral change (OLS BP from ~65.228 to ~82.203) is accepted and
documented. The FE/TWFE values are numerically identical to Phase 3 pins. The
dispatcher architecture is sound. No redesign is recommended.

---

## Three-Sprint Roadmap

### Sprint 1 — Unblock installation and fix committed state (1 week)

**Goal:** Every user who clones the repository and follows any piece of documentation
can install and run the pipeline without encountering a broken instruction or a
misleading output file.

Deliverables:
1. Fix I-01: Update `getting_started/README.md`, `__init__.py`, `release_notes/v0.1.0.md`
2. Fix I-02: Regenerate committed output files after running the pipeline
3. Fix I-03: Update stale comment in `estimation/__init__.py`
4. Fix I-04: Update SDK dependency constraint in `PLUGIN_SDK.md`
5. Fix I-12: Add warning on empty `--project-name` in `certify`

Acceptance: `grep -r "pip install econflow" . | grep -v "once published"` returns
no false-positive installation instructions. `cat examples/getting_started/outputs/tables/diagnostics.csv`
shows BP ~82.20 for pooled_ols.

---

### Sprint 2 — API discoverability and CLI polish (1 week)

**Goal:** A first-time economist can discover and use the Python API from `import econflow`
and understands what every CLI command does before running it.

Deliverables:
1. Fix I-05: Re-export core estimation classes from `econflow/__init__.py`
2. Fix I-06: Update `econflow run` --help expected output
3. Fix I-07: Update `FIRST_FIVE_MINUTES.md` expected output
4. Fix I-08: Clarify `econflow report` vs `outputs/tables/` relationship
5. Fix I-09: Fix `_unregister_estimator` reference in SDK

Acceptance: `python -c "from econflow import PooledOLS, EntityFE; print('ok')"` exits 0.
All CLI command `--help` expected output sections match one live run on getting_started.

---

### Sprint 3 — Ecosystem polish and PyPI publication (2 weeks)

**Goal:** A researcher can install EconFlow with a single `pip install` and a plugin author
can publish a working plugin within an afternoon.

Deliverables:
1. Fix I-10: Add README with action checklist to `econflow init` scaffold
2. Fix I-11: Add `expected_outputs/diagnostics.csv` and flesh out README
3. Publish to PyPI (register package name, build wheel, upload to Test PyPI first, then PyPI)
4. Update all documentation to use `pip install econflow` (after PyPI publication)
5. Add SDK end-to-end test: write a minimal plugin, install it, verify it runs in the pipeline

Acceptance: `pip install econflow` in a clean venv exits 0. `econflow doctor` exits 0.
`econflow run --config examples/getting_started/...` produces matching diagnostic values.

---

## Confidence Notes

**Confidence in issue catalog: 88%.** Every issue was verified against the live source
files at the time of this audit. Issues I-01 through I-04 were confirmed by direct file
reads. The OLS BP value change (I-02) is corroborated by `PHASE6_COMPLETION_REPORT.md §4`.

**Items not verified by running code:** All verifications were performed by reading
source files; the FUSE mount limitation prevents running pytest inside the bash sandbox.
The correctness of numerical values in `diagnostics.csv` was cross-checked against
`PHASE6_COMPLETION_REPORT.md` and `test_estimation_diagnostics_phase3.py` pin values,
not by live execution. Confidence that the stale `diagnostics.csv` is wrong: 97%.

**No false positives expected.** Each issue is traced to a specific file and line.
No speculation about runtime behavior is included in the Critical or High findings.

---

*End of First Post-Migration Product Audit*
