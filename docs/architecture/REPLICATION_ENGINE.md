# Replication Engine

**EconFlow — Architecture Document**

*This document describes the design of the EconFlow Replication Engine: the
subsystem responsible for inspecting, executing, and verifying reproductions
of published empirical results.*

---

## Motivation

A reproducibility certificate (see `INTEGRITY_FRAMEWORK.md`) records *what
was done* during a run. The Replication Engine answers a different question:
*can someone else reproduce it?*

These are distinct. A certificate proves that a run completed and documents
its environment. A replication proves that a different execution — possibly
by a different person, on a different machine, starting from only the
project directory — produces numerically equivalent outputs.

The Replication Engine provides tooling for both: pre-flight checks before
attempting a replication, execution of the replication itself, and structured
comparison of outputs.

---

## Three Commands, One Workflow

```
econflow inspect <project_dir>          # Can we replicate?
econflow reproduce <project_dir>        # Replicate it
econflow compare <baseline> <replica>   # Did it match?
```

Each command can be used independently. The typical workflow runs all three.

```
$ econflow inspect examples/my_study/
✔ Config found         config/config.yaml
✔ Data found           data/panel.csv (SHA-256 verified)
✔ Dependencies         econflow 0.1.0, pandas 2.2.0, linearmodels 6.1
✔ Estimators           pooled_ols ✔  entity_fe ✔  twoway_fe ✔
● Status: PASS (4 checks, 0 warnings, 0 failures)

$ econflow reproduce examples/my_study/ --output-dir /tmp/replica/
[1/3] Validating project …  pass
[2/3] Executing pipeline … 14.2 s
[3/3] Writing report …     done
● Status: SUCCESS  outputs → /tmp/replica/

$ econflow compare examples/my_study/original_outputs/ /tmp/replica/tables/
comparison_table.csv  ✔ match (max Δ = 0.000000)
table_pooled_ols.csv  ✔ match (max Δ = 0.000000)
● Status: PASS (2 files compared, 0 mismatches)
```

---

## Components

### `replication.models` — Data Structures

All three commands exchange structured data through dataclasses defined in
`models.py`. Every dataclass is serialisable to JSON and reloadable from it.

```
ProjectCheck           Single check item with status / message
InspectionReport       Aggregation of all ProjectChecks
ExecutionStep          One pipeline step with command and dependencies
ExecutionPlan          Ordered list of ExecutionSteps
StepResult             Result of running one ExecutionStep
ReplicationResult      Full outcome of an econflow reproduce run
OutputComparison       Comparison result for a single file pair
ComparisonReport       Aggregation of all OutputComparisons
```

**Status values** follow the same convention throughout:
`"pass"` — expected | `"warn"` — unexpected but non-fatal | `"fail"` — fatal

### `replication.inspector` — Pre-flight Checks

The inspector reads a project directory and runs a battery of checks before
any execution begins. It never modifies the project directory.

**Checks performed (in order):**

| Check ID | What it verifies |
|----------|-----------------|
| `config_found` | `config/config.yaml` exists and is valid YAML |
| `models_found` | `config/models.yaml` exists and is valid YAML |
| `outputs_cfg_found` | `config/outputs.yaml` exists and is valid YAML |
| `data_found` | Data file declared in config exists on disk |
| `data_checksum` | SHA-256 of data file matches provenance record (warn if no provenance) |
| `estimators_registered` | Every model in `models.yaml` maps to a registered estimator |
| `python_version` | Python version at or above minimum (`3.10`) |
| `dependencies` | Key packages installed; versions noted from provenance if available |

Checks that cannot run because a prerequisite failed are recorded as
`"skip"`. A single `"fail"` sets the overall status to `"fail"`. One or
more `"warn"` with no `"fail"` sets the status to `"warn"`.

The inspector never calls the pipeline. Its output is an
`InspectionReport` that can be saved as JSON or printed as formatted text.

### `replication.planner` — Execution Planning

The planner reads the project's configuration files and produces an ordered
`ExecutionPlan` describing the steps required to reproduce the pipeline. The
plan is deterministic: the same project directory always produces the same
plan.

A step carries:
- A human-readable description
- The concrete command to execute (`["econflow", "run", "--config", ...]`)
- A list of step IDs it depends on

Currently EconFlow projects have a single pipeline step. The planner
architecture supports multi-step projects for future expansion (e.g.,
pre-processing step → estimation step → reporting step).

### `replication.executor` — Execution

The executor runs an `ExecutionPlan` in a subprocess. Running in a subprocess
provides:
- Clean separation between the replication environment and the calling process
- Captured stdout/stderr per step for failure diagnostics
- Accurate timing per step
- Isolation from any state the calling process has accumulated

Each step is executed sequentially. If a step fails, dependent steps are
skipped. The executor always produces a `ReplicationResult` — even when
steps fail, so that partial results can be compared and failure diagnostics
can be reported.

The executor writes outputs to a specified output directory, separate from
the original project's `outputs/` directory, so originals are never
overwritten.

### `replication.comparator` — Output Comparison

The comparator takes two directories (the original outputs directory and the
replica's outputs directory) and compares all matching files.

**CSV comparison:**
- Loads both files with `pandas.read_csv`
- Aligns on common columns in declared order
- Numeric columns: compared with absolute tolerance (default `1e-6`)
- String columns: compared for exact equality
- Reports per-file: status, max absolute difference, number of differing rows

**LaTeX comparison:**
- Strips `% comments` and normalises whitespace
- Compares structure (tabular environments, `\hline` counts, column specs)
- Does not require byte-for-byte equality (run timestamps differ)
- Produces `"warn"` rather than `"fail"` for structural matches with minor
  formatting differences

**JSON comparison:**
- Deep equality with float tolerance for numeric leaves
- Keys must match exactly; ordering is normalised

Files present in baseline but absent from replica produce a `"fail"`.
Files present in replica but absent from baseline produce a `"warn"`
(unexpected but not a replication failure).

### `replication.reporter` — Report Generation

The reporter converts `InspectionReport`, `ReplicationResult`, and
`ComparisonReport` objects into human-readable documents.

**Formats:**
- Markdown — suitable for inclusion in replication packages
- JSON — machine-readable; suitable for CI assertions
- Console — formatted with Rich for terminal output

The `ReproducibilityReport` bundles all three into a single document:

```
ReproducibilityReport
├── InspectionReport       (pre-flight)
├── ReplicationResult      (execution)
└── ComparisonReport       (comparison)
```

When saved, the report is written as:
- `replication_report.md` — the human-readable summary
- `replication_report.json` — the machine-readable record

---

## Failure Diagnostics

The engine captures structured failure information at each layer:

**Inspection failures:**
- Missing config → `config_found: fail` with exact path
- Missing data → `data_found: fail` with path from config
- Unregistered estimator → `estimators_registered: fail` with estimator ID

**Execution failures:**
- Non-zero subprocess exit code → `StepResult.status = "failed"`
- Captured stdout/stderr included in `StepResult.output`
- Downstream steps skipped with `status = "skip"` and reason

**Comparison failures:**
- Column mismatch → `OutputComparison.status = "mismatch"` with column name
- Missing file → `OutputComparison.status = "missing_replica"` with filename
- Numeric drift above tolerance → `status = "mismatch"` with `max_abs_diff`

The CLI commands surface the most actionable failure information in the
terminal. The full diagnostics are available in the JSON report.

---

## Project Directory Convention

The replication engine expects a standard EconFlow project layout:

```
<project_dir>/
├── config/
│   ├── config.yaml       (required)
│   ├── models.yaml       (required)
│   └── outputs.yaml      (required)
├── data/
│   └── <dataset>.csv     (path declared in config.yaml)
├── original_outputs/     (baseline for comparison — optional)
│   └── tables/
│       └── *.csv
└── outputs/              (created by econflow run)
    ├── tables/
    ├── figures/
    └── provenance/
        └── run_metadata.json
```

The `original_outputs/` directory contains the reference results produced
by the original author. When present, `econflow reproduce` automatically
compares its outputs against it and includes the comparison in the report.

When `original_outputs/` is absent, `econflow reproduce` produces outputs
and reports success or failure of execution only (no comparison).

---

## Numeric Tolerances

Replication of floating-point computation is not expected to be
bit-for-bit identical across platforms, compiler versions, or BLAS
implementations. The comparator applies absolute tolerances:

| Comparison type | Default tolerance | Rationale |
|----------------|------------------|-----------|
| Coefficient estimates | `1e-6` | Double-precision arithmetic; differences above this indicate non-determinism |
| Standard errors | `1e-6` | Same |
| Test statistics | `1e-4` | May use different numerical routines across platforms |
| p-values | `1e-4` | Derived from test statistics; inherits same tolerance |

These defaults can be overridden via `--tolerance` on `econflow compare`.

A comparison that passes with a tolerance larger than the default produces
a `"warn"` rather than a `"pass"` in the report, to flag that results
were not exactly reproducible within the default bounds.

---

## Relationship to Other Subsystems

The Replication Engine uses but does not replace the integrity and
provenance subsystems:

- **Provenance** (`provenance.py`) records *what happened* in a run.
  The replication executor reads provenance records to validate data
  checksums during inspection.
- **Certificates** (`integrity/`) certify a single run's environment.
  The replication engine verifies that a *new* run produces the same
  outputs as an *original* run.

The three subsystems together answer three different questions:

| Subsystem | Question |
|-----------|---------|
| Provenance | What did this run do, in what environment? |
| Integrity / Certificate | Was this run internally consistent? |
| Replication Engine | Can an independent run reproduce these results? |

---

## Design Decisions

**Why run in a subprocess?**
Running `run_from_config()` directly in the same process would be faster,
but it would share Python state with the caller (imports, registry state,
log configuration). Subprocess isolation is the only way to guarantee that
the replication sees the same environment a real user would.

**Why not use `docker` or virtualenv isolation?**
Stronger isolation is deliberately out of scope for the current engine.
The goal is to verify computational reproducibility given the same
software environment. Platform-level isolation belongs in a dedicated
archival layer (e.g., Binder, Zenodo) that wraps an EconFlow replication
package.

**Why is `original_outputs/` optional?**
Not every use of `econflow reproduce` is a replication. It is also used
to re-execute a pipeline after modifying data or config, to verify that
the change had the expected effect. In that case, comparison is not needed.

**Why is comparison toleranced, not byte-identical?**
Byte-identical replication is unrealistic across platforms and library
versions. The goal is numerical equivalence within the precision of the
estimation. Toleranced comparison is honest about what can be reproduced.
