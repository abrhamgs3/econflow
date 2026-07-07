# EconFlow Platform Boundary

**Date:** 2026-07-07  
**Status:** Authoritative  
**Sprint:** 10.5 — Platform Separation

---

## Why this document exists

EconFlow grew out of a specific research project — *AI Adoption and Total Factor
Productivity: Panel Evidence from 193 Countries* (the "AI & Productivity paper").
The earliest versions of the codebase were tightly coupled to that paper's column
names (`ln_ai`, `ln_tfp`, `country`, `year`), its pipeline assumptions, and its
output directory layout.

As the platform evolved through ten sprints, the generic infrastructure was
extracted and the paper-specific code was progressively isolated.  Sprint 10.5
completed that separation by enforcing a clear architectural boundary: the
**EconFlow platform** and **example applications** are now distinct layers with
no cross-contamination.

A first-time visitor cloning this repository should understand immediately:

> "This is a reusable econometrics platform."

Not:

> "This is the code accompanying one paper."

---

## What constitutes the EconFlow platform

The platform is everything in `src/econflow/` **except** `pipeline.py` (the
legacy paper-specific orchestrator, retained for backward compatibility until
v0.3.0).

Platform modules must be:

- **Paper-agnostic** — no hardcoded column names, country lists, variable
  transformations, or file paths that assume a specific dataset.
- **Config-driven** — all study-specific parameters come from the three YAML
  files (`config.yaml`, `models.yaml`, `outputs.yaml`).
- **Generic by default** — default argument values must not assume the AI & P
  dataset.  Parameters like `entity_col`, `time_col`, `dependent`, and
  `regressors` must be explicitly passed by the caller.

### Platform modules (in `src/econflow/`)

| Module | Role |
|--------|------|
| `pipeline_generic.py` | Canonical pipeline orchestrator |
| `commands/` | CLI command implementations |
| `config/` | Pydantic v2 YAML models, linter, validator |
| `estimation/` | Panel estimator registry and implementations |
| `diagnostics/` | Post-estimation test registry and plugins |
| `outputs/` | Table, figure, and report renderer registry |
| `integrity/` | Provenance certificates, drift detection, packages |
| `replication/` | Blind replication engine |
| `ingestion/` | Generic data connector registry and implementations |
| `datasets/` | Panel, cross-section, time-series dataset abstractions |
| `core/` | Shared exceptions, registry infrastructure |
| `exceptions.py` | Root exception hierarchy |
| `cli.py` | CLI entry point (routes to command modules) |

### Platform exclusions

The following modules are **not part of the platform** and are excluded from
the wheel:

| Module | Reason |
|--------|--------|
| `pipeline.py` | Paper-specific AI & P orchestrator (deprecated, removed in v0.3.0) |
| `econometrics/` | Paper-specific model suites (`run_robustness_suite`, etc.) |
| `visualization/` | Paper-specific figures (`ai_tfp_scatter`, `ai_tfp_trend`, etc.) |
| `reporting/` | Paper-specific LaTeX narrative generator |
| `features/` | Paper-specific feature engineering (AI index, TFP transforms) |
| `data/` | Partially paper-specific; generic parts (`loaders.py`, `validators.py`) are maintained |
| `cli_scaffold/` | Development scaffold excluded from wheel |

---

## What constitutes an example application

An example application is a self-contained study that **uses** the EconFlow
platform without modifying it.  All example applications live in `examples/`.

### Example structure

```
examples/<study_name>/
├── config/
│   ├── config.yaml        ← study-specific configuration
│   ├── models.yaml        ← study-specific model specifications
│   └── outputs.yaml       ← study-specific output settings
├── data/                  ← study data (or scripts to acquire it)
├── outputs/               ← generated outputs (gitignored)
└── README.md              ← how to reproduce this study
```

An example application:

- Contains **only** configuration, data, and study-specific scripts.
- Does **not** define new estimators, renderers, or pipeline stages.
- Runs the generic pipeline via `econflow run --config ... --models ... --outputs ...`.
- Is reproducible using the standard `econflow certify` / `econflow package` chain.

### Current examples

| Directory | Description |
|-----------|-------------|
| `examples/getting_started/` | Minimal tutorial — Grunfeld (1935–1954) firm investment panel |
| `examples/blind_replication/` | Blind replication walkthrough |
| `examples/ai_productivity_paper/` | The original motivating study — AI & TFP panel |

---

## Rules for adding new examples

1. Create `examples/<study_name>/` with the standard layout above.
2. Write a `README.md` that explains: the research question, data sources, how
   to run the pipeline, and what the expected outputs are.
3. Add an entry to `examples/README.md`.
4. Do **not** add any study-specific Python code to `src/econflow/`.
5. If the study requires a data connector not yet in the platform, implement it
   in `src/econflow/ingestion/connectors/` as a generic connector — not as a
   study-specific script.
6. If the study requires an estimator not yet in the platform, implement it in
   `src/econflow/estimation/` as a generic estimator.
7. All platform extensions must pass the paper-agnosticism test: "would this
   work for any study using a similar method, not just this one?"

---

## Rules preventing paper-specific logic from entering the core platform

The following are **prohibited** in any file under `src/econflow/`
(except the deprecated `pipeline.py` and the excluded modules above):

### Prohibited patterns

```python
# ✘ Hardcoded paper column names
DEFAULT_REQUIRED_COLUMNS = ["country", "year", "ln_ai", "ln_tfp"]

# ✘ Hardcoded default that assumes the AI&P dataset
def sample_selection_summary(df, indicator_col="ln_ai"):  ...

# ✘ Paper-specific output directories
paper_dir = Path("paper/sections")

# ✘ Paper-specific error messages
"Run scripts/02_clean_data.py to generate it."

# ✘ Importing paper-specific modules in generic paths
from econflow.pipeline import run  # legacy AI&P pipeline
```

### Required patterns

```python
# ✔ Config-driven column names
def validate_data(path, required_columns=None):
    required_columns = required_columns or []  # caller specifies

# ✔ Explicit caller-provided column names
def sample_selection_summary(df, indicator_col):  # no default
    ...

# ✔ Generic output directories
outputs_dir = Path(config["outputs"]["base_dir"])

# ✔ Generic error messages
"Ensure the data file exists and the path in config.yaml is correct."

# ✔ Only importing the generic pipeline
from econflow.pipeline_generic import run_from_config
```

---

## The `econflow run` command

Before Sprint 10.5, `econflow run` dispatched to the AI & P legacy pipeline
when `--config` was absent.  This was the single largest product boundary
violation: a first-time user running `econflow run --data-path my.csv` would
execute the AI & P pipeline and receive a confusing error about missing
`ln_ai` and `ln_tfp` columns.

After Sprint 10.5:

- `econflow run` **always** invokes the generic config-driven pipeline.
- `--config`, `--models`, and `--outputs` are **required**.
- `--data-path` is **deprecated** and hidden from `--help`.  It still works
  (with a deprecation warning) to preserve backward compatibility, but is
  removed in v0.3.0.
- Running `econflow run` with no arguments produces a helpful error with
  example commands pointing to the Getting Started tutorial.

---

## The `econflow init` scaffold

The project skeleton created by `econflow init` no longer includes a
`paper/sections/` directory.  That directory was an AI & P paper artifact
(auto-generated LaTeX narrative fragments).  The generic scaffold now creates:

```
my_study/
├── config/
├── data/raw/
├── data/processed/
├── outputs/tables/
├── outputs/figures/
├── outputs/provenance/
├── scripts/
├── tests/
├── docs/
└── notebooks/
```

Users who want a `paper/` subdirectory for LaTeX manuscripts can create it
manually.  It is not a platform convention.

---

## Verification

After any change to `src/econflow/`, run the platform separation test suite:

```bash
pytest tests/unit/test_platform_separation.py -v
```

These tests assert:

1. `econflow run` with no arguments exits 1 with a clear error (not a legacy run).
2. `econflow run --data-path` prints a deprecation warning.
3. `econflow init` does not create `paper/sections/`.
4. `DEFAULT_REQUIRED_COLUMNS` in `data/validators.py` is empty.
5. `sample_selection_summary` has no default value for `indicator_col`.
6. No platform module imports `econflow.pipeline` (the legacy orchestrator).

---

## Migration from legacy commands

| Old command | New command |
|-------------|-------------|
| `econflow run --data-path data/processed/panel_clean.csv` | `econflow run --config config/config.yaml --models config/models.yaml --outputs config/outputs.yaml` |
| (implicit AI&P pipeline) | `econflow run --config examples/ai_productivity_paper/config/config.yaml ...` |

The legacy `--data-path` option continues to work until v0.3.0 with a deprecation warning.
