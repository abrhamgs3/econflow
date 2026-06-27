# EconFlow Workspace Architecture

This document describes how an EconFlow project workspace is structured,
how the four lifecycle commands relate to one another, and how to extend
each layer.

---

## Philosophy

An EconFlow workspace separates three concerns:

1. **Configuration** — *what* to estimate (YAML, human-editable, version-controlled)
2. **Data** — *inputs* the pipeline reads (CSV, never modified by EconFlow)
3. **Outputs** — *artefacts* the pipeline writes (tables, LaTeX, provenance)

This separation means the same configuration can be re-run on different
datasets, the same dataset can be run with different model specifications,
and all outputs are fully reproducible from the configuration alone.

---

## Project lifecycle

```
econflow init          →   Scaffold directory + YAML templates
       ↓
 Edit config files     →   Customise data path, variables, models
       ↓
econflow validate      →   Catch typos and structural errors before running
       ↓
econflow run           →   Estimate all models, write tables + provenance
       ↓
econflow info          →   Inspect what was produced and when
```

`econflow doctor` can be run at any point to verify the Python environment.

---

## Directory layout

After `econflow init my_project`, the workspace looks like this:

```
my_project/
│
├── config/                         ← Three YAML files drive everything
│   ├── config.yaml                 ← Data path, entity/time cols, variables
│   ├── models.yaml                 ← List of model specifications to run
│   └── outputs.yaml                ← Output directory, formats, table name
│
├── data/
│   ├── raw/                        ← Original source files (never modified)
│   └── processed/
│       └── panel.csv               ← Cleaned panel CSV for estimation
│
├── outputs/
│   ├── tables/
│   │   ├── table_main_results.csv  ← Comparison table (all models)
│   │   └── table_main_results.tex  ← LaTeX version of the same table
│   ├── figures/                    ← Reserved for future chart outputs
│   └── provenance/
│       └── run_metadata.json       ← SHA-256 hashes, timestamp, run ID
│
├── paper/
│   └── sections/                   ← Reserved for auto-generated LaTeX fragments
│
├── scripts/
│   ├── 01_download_data.py         ← Data download stub (user implements)
│   └── 02_clean_data.py            ← Data cleaning stub (user implements)
│
├── tests/
│   ├── __init__.py
│   └── test_pipeline.py            ← Starter tests (smoke + data check)
│
├── docs/                           ← Project-level documentation
├── notebooks/                      ← Exploratory analysis notebooks
├── README.md
└── .gitignore
```

---

## Configuration files

### `config/config.yaml`

The primary project configuration.  Every other file references the
names defined here.

Key sections:

| Section | Purpose |
|---------|---------|
| `project` | Name, description, version, authors |
| `data` | Path to `panel.csv`; `entity_col` and `time_col` names |
| `variables` | `dependent` (LHS) and `regressors` list (RHS) |
| `sample` | Optional `start`/`end` year filters |

### `config/models.yaml`

A list of model specifications.  Each entry has:

| Field | Required | Notes |
|-------|----------|-------|
| `id` | Yes | Unique key, used in output filenames |
| `label` | Yes | Human-readable column header in tables |
| `estimator` | Yes | `OLS` or `FE` (see estimator registry) |
| `dependent` | Yes | Must match a column in the panel CSV |
| `regressors` | Yes | List of column names |
| `entity_effects` | No | `true` for within estimator (FE only) |
| `time_effects` | No | `true` for two-way FE |
| `cluster` | No | `"entity"` or `"time"` for clustered SEs |

### `config/outputs.yaml`

Controls where results are written and in what format.

| Field | Notes |
|-------|-------|
| `outputs.base_dir` | Root output directory (relative to project root) |
| `tables.formats` | List of `["csv", "latex"]` |
| `tables.comparison_table.filename` | Output filename (no extension) |
| `tables.comparison_table.models` | Ordered list of model IDs for columns |

---

## Command reference

### `econflow init [DIRECTORY]`

Scaffolds a fresh workspace.  All config files are populated with
commented templates so the user knows what to fill in.  The command
is idempotent with `--force`; without it, it refuses to overwrite an
existing directory.

Exit codes: `0` success, `1` directory non-empty without `--force`.

### `econflow validate`

Reads the three YAML files and runs a battery of structural checks.
Each check is classified as `pass`, `warn`, `fail`, or `skip`.
Any `fail` causes exit code `1`.

With `--data`, additionally opens the panel CSV and checks that all
referenced columns exist and that the panel index has no duplicate keys.

Use `validate` in CI before `run` to catch config errors cheaply.

### `econflow doctor`

Environment health check — independent of any project.  Verifies:

- Python version ≥ 3.10
- OS, CPU, and RAM (informational)
- All core Python packages at minimum versions
- `git`, LaTeX, `pandoc` (warn if missing)
- `uv`, `pip` (package managers, warn if `uv` absent)
- Optional: `pytest`, `ruff`, `pyarrow`, `jupyter`, `streamlit`

Can be run from any directory.  Exit code `1` if any *required* check fails.

### `econflow run`

Executes the full pipeline:

1. Load and validate configuration
2. Read panel CSV into a `pandas.DataFrame`
3. For each model in `models.yaml`, call the appropriate estimator
4. Write comparison table (CSV and/or LaTeX)
5. Write provenance record (`run_metadata.json`)

The `--config`, `--models`, and `--outputs` flags default to
`config/config.yaml`, `config/models.yaml`, `config/outputs.yaml`
relative to the current directory.

### `econflow info`

Reads the three YAML files (if present) and prints:

- Platform section: EconFlow version, Python, OS, install path, project path
- Estimator registry: all estimators with implementation status
- Data connector registry: all connectors with implementation status
- Project config summary (if `config.yaml` found)
- Model table (if `models.yaml` found)
- Output config (if `outputs.yaml` found)
- Provenance status (timestamp + run ID of the last pipeline run)

Always exits `0`.

---

## Module layout

```
src/econflow/
│
├── __init__.py                 ← __version__, public re-exports
├── cli.py                      ← Typer app, thin wrappers over run_*()
│
├── commands/                   ← Sprint 3B: project lifecycle
│   ├── __init__.py
│   ├── init.py                 ← run_init()
│   ├── validate.py             ← run_validate(), ValidationReport, CheckResult
│   ├── doctor.py               ← run_doctor(), EnvCheck
│   └── info.py                 ← run_info(), ESTIMATOR_REGISTRY
│
├── pipeline_generic.py         ← run_from_config(): load → estimate → write
├── provenance.py               ← ProvenanceRecorder (SHA-256 + JSON)
│
├── core/
│   ├── config.py               ← Pydantic settings (ECONFLOW_* env vars)
│   └── exceptions.py           ← EconFlowError hierarchy
│
├── validators.py               ← validate_data() — DataFrame checks
├── table_formatter.py          ← format_comparison_table() → CSV / LaTeX
│
└── ingestion/                  ← Data source adapters (stub except csv)
    ├── __init__.py
    ├── csv_loader.py           ← load_panel_csv()
    ├── world_bank.py           ← stub
    ├── oecd.py                 ← stub
    └── pwt.py                  ← stub
```

---

## Design decisions

### Logic / CLI separation

Every command exposes a `run_*()` function that accepts plain Python
arguments and a `rich.Console`.  The Typer decorators in `cli.py` are
thin wrappers.  This means the entire implementation is testable via
direct Python calls with no subprocess overhead.

### Template embedding

`init.py` embeds config templates as module-level string constants
(`_CONFIG_YAML`, `_MODELS_YAML`, etc.) rather than reading from
`data/` files at runtime.  Templates therefore travel with the wheel
when EconFlow is installed from PyPI, and require no `MANIFEST.in` entry.

### Structured check results

`validate.py` uses `CheckResult` dataclasses with a `Status` literal
(`pass`/`warn`/`fail`/`skip`).  This enables:

- Machine-readable output (`--format json`, planned for Sprint 5)
- Precise assertions in tests (`assert result.status == "fail"`)
- Separation of check logic from display logic

### Static registries

`ESTIMATOR_REGISTRY` and `DATA_CONNECTOR_REGISTRY` in `info.py` are
module-level lists of dicts.  When a plugin discovery system is added
(Sprint 5), these will be replaced by `PluginRegistry.discover()` with
no change to the display layer.

---

## Extension points

### Adding a new estimator

1. Add the estimation logic to `pipeline_generic.py` (or a new module
   under `src/econflow/estimation/`).
2. Add `"estimator": "YOUR_ID"` handling to the `_run_model()` dispatch
   in `pipeline_generic.py`.
3. Add an entry to `ESTIMATOR_REGISTRY` in `info.py`.
4. Update `validate.py` — the `SUPPORTED_ESTIMATORS` set in `M-03`.

### Adding a data connector

1. Implement `load_*(config) -> pd.DataFrame` in `src/econflow/ingestion/`.
2. Wire it into `pipeline_generic.py` based on a `data.source` config key.
3. Add an entry to `DATA_CONNECTOR_REGISTRY` in `info.py`.

### Adding a new validate check

1. Add a `CheckResult` item in the appropriate `_check_*` helper in
   `validate.py`.
2. Assign the next available check code (`S-06`, `M-06`, etc.).
3. Add a unit test in `tests/unit/test_cmd_validate.py`.

---

## CI integration

Recommended CI pre-flight (no data required):

```bash
econflow doctor          # environment OK?
econflow validate        # config files structurally valid?
pytest tests/unit/       # unit tests pass?
```

Full CI with data:

```bash
econflow validate --data           # config + data file valid?
pytest tests/ --cov=src/econflow  # all tests + coverage
```
