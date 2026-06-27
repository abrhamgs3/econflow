# Sprint 3B — Project Lifecycle Commands

**Status:** Complete  
**Tests:** 181 passed / 181  
**Lint:** ruff clean  

---

## Overview

Sprint 3B adds four project lifecycle commands that make EconFlow usable by any
economist starting a new research project — without any knowledge of the AI &
Productivity paper or its hardcoded assumptions.

---

## Commands

### `econflow init [DIRECTORY]`

Scaffolds a complete project skeleton.

```
$ econflow init my_study
$ econflow init my_study --name "Trade and AI"
$ econflow init my_study --force   # overwrite existing files
```

**Creates:**
```
my_study/
├── config/
│   ├── config.yaml       ← data path, entity/time cols, variables
│   ├── models.yaml       ← three starter model specifications
│   └── outputs.yaml      ← table formats and output directory
├── data/
│   ├── raw/              ← original source files (never modified)
│   └── processed/        ← cleaned panel CSV
├── outputs/
│   ├── tables/
│   ├── figures/
│   └── provenance/
├── paper/
│   └── sections/
├── scripts/
│   ├── 01_download_data.py   ← placeholder with TODO
│   └── 02_clean_data.py      ← placeholder with TODO
├── docs/
├── notebooks/
├── README.md
└── .gitignore
```

**Exit codes:** 0 (success), 1 (directory non-empty without `--force`)

---

### `econflow doctor`

Comprehensive environment health check. Replaces the old `doctor` that
checked AI&P-specific data files.

```
$ econflow doctor
```

**Checks:**

| Code | Item | Required |
|------|------|----------|
| SYS-01 | Python ≥ 3.10 | Yes |
| SYS-02 | Operating system | Info |
| PKG-01..09 | pandas, numpy, statsmodels, linearmodels, matplotlib, scipy, typer, rich, pyyaml | Yes |
| EXT-01 | git | Warn if missing |
| EXT-02 | LaTeX (pdflatex / xelatex / lualatex) | Warn if missing |
| EXT-03 | pandoc | Warn if missing |
| OPT-01..05 | pytest, ruff, pyarrow, jupyter, streamlit | Warn if missing |

**Exit codes:** 0 (all required checks pass), 1 (any required check fails)

**Migration note:** The old `doctor` checked for
`data/processed/panel_clean.csv`, `data/raw/wdi.csv`, etc. These checks were
AI&P-specific and are removed. Use `econflow validate --data` for project-level
data validation.

---

### `econflow validate`

Validates configuration files and (optionally) the data CSV.

```
$ econflow validate
$ econflow validate \
      --config  config/config.yaml \
      --models  config/models.yaml \
      --outputs config/outputs.yaml \
      --data
```

**Defaults:** looks for `config/config.yaml`, `config/models.yaml`,
`config/outputs.yaml` relative to the current directory.

**Checks performed:**

| Code | Check |
|------|-------|
| C-01..03 | All three YAML files present and parseable |
| S-01..05 | config.yaml has `data.path`, `data.entity_col`, `data.time_col`, `variables.dependent`, `variables.regressors` |
| M-01..05 | models list non-empty; each model has `id`, `estimator`, `dependent`, `regressors`; no duplicate IDs; estimators recognised |
| O-01..02 | outputs.yaml has `outputs.base_dir` and `comparison_table.filename` |
| X-01..02 | Cross-file: output model IDs exist in models.yaml; model regressors are in config regressors |
| D-01..05 | (with `--data`) data file exists, parseable CSV, entity/time cols present, analysis variables present, no duplicate panel keys |

**Exit codes:** 0 (all PASS, warnings allowed), 1 (any FAIL)

---

### `econflow info`

Displays project summary, estimator registry, and provenance status.

```
$ econflow info
$ econflow info \
      --config  config/config.yaml \
      --models  config/models.yaml \
      --outputs config/outputs.yaml
```

**Sections always shown (no config needed):**
- Platform: EconFlow version, Python version, OS, install path
- Registered estimators: OLS, FE (implemented); GMM, IV, RE, Quantile (stubs)
- Registered data connectors: CSV (implemented); WorldBank, OECD, PWT (stubs)

**Sections shown when config files are present:**
- Project configuration: name, description, data path, entity/time columns, variables
- Model specifications: table of all models with estimator, FE flags, cluster
- Output configuration: base directory, formats, comparison table filename
- Provenance: timestamp and run ID of the last pipeline run, or "no record found"

**Exit codes:** always 0

---

## Architecture

### Module layout

```
src/econflow/
├── commands/
│   ├── __init__.py      ← package docstring
│   ├── init.py          ← run_init()
│   ├── validate.py      ← run_validate(), ValidationReport, CheckResult
│   ├── doctor.py        ← run_doctor(), EnvCheck, _check_package(), _check_external_tool()
│   └── info.py          ← run_info(), ESTIMATOR_REGISTRY, DATA_CONNECTOR_REGISTRY
└── cli.py               ← typer wiring for init, doctor, validate, info, run
```

### Design decisions

**Separation of logic and CLI wiring.** Each command exposes a `run_*()` function
that takes plain Python arguments and a `rich.Console`. The typer decorators in
`cli.py` are thin wrappers that parse CLI options and call these functions. This
makes the logic fully testable without invoking the CLI layer.

**`validate` uses a structured result model.** Each check returns a `CheckResult`
dataclass with `code`, `name`, `status` (pass/warn/fail/skip), `message`, and
`detail`. This allows machine-readable output in future (e.g. `--format json`)
and makes the test suite check specific status values rather than string parsing.

**`doctor` is now environment-only.** It no longer checks for project-specific data
files. Those checks belong in `validate --data`. This separation means `doctor` can
be run in any directory and will always give a meaningful result.

**`info` has a static registry.** `ESTIMATOR_REGISTRY` and `DATA_CONNECTOR_REGISTRY`
are module-level lists of dicts with `id`, `label`, `status`, and `notes`. When a
dynamic plugin system is added (Sprint 5), these lists can be replaced by a
`PluginRegistry.discover()` call while preserving the same display format.

**`init` embeds templates as string constants.** Templates are not read from
external files; they are `_CONFIG_YAML`, `_MODELS_YAML`, etc. defined at module
level. This keeps `init` self-contained with no file I/O at import time and
ensures the templates travel with the package when installed as a wheel.

---

## Migration notes

### Breaking changes from the old `doctor`

The old `doctor` (in `cli.py` inline) checked for four hardcoded data files:
- `data/processed/panel_clean.csv`
- `data/raw/wdi.csv`
- `data/raw/pwt.csv`
- `data/raw/ai_proxy.csv`

These checks are removed from `doctor`. They were AI&P-specific and would
always fail for any other project. The new `validate --data` performs
equivalent checks in a config-driven way.

**Action required for AI&P users:** Run `econflow validate --data` instead of
relying on `econflow doctor` to confirm data files.

### Backward-compatible changes

- `econflow run` is unchanged. Both generic (`--config`) and legacy
  (`--data-path`) modes continue to work exactly as before.
- All existing tests continue to pass.
- `__init__.py` exports are unchanged.

---

## Test coverage

| File | Tests | What is covered |
|------|-------|-----------------|
| `tests/unit/test_cmd_init.py` | 23 | Directory structure, config file content, YAML validity, --name, --force, .gitkeep |
| `tests/unit/test_cmd_validate.py` | 20 | All YAML checks, cross-file consistency, --data flag, exit codes |
| `tests/unit/test_cmd_doctor.py` | 21 | CLI smoke, version helpers, package check, external tool mock, exit codes |
| `tests/unit/test_cmd_info.py` | 19 | No-config run, all sections, provenance display, registry integrity |

Total Sprint 3B tests: **83**  
Full suite after Sprint 3B: **181 passed**

---

## Usage examples

### Start a new research project

```bash
# Create project skeleton
econflow init my_trade_study

# Edit config to match your data
nano my_trade_study/config/config.yaml

# Check the environment
econflow doctor

# Validate configuration
cd my_trade_study
econflow validate

# Run the pipeline
econflow run \
    --config  config/config.yaml \
    --models  config/models.yaml \
    --outputs config/outputs.yaml

# Check what was produced
econflow info \
    --config  config/config.yaml \
    --models  config/models.yaml \
    --outputs config/outputs.yaml
```

### CI pre-flight (no data required)

```bash
econflow doctor          # environment OK?
econflow validate        # config files valid?
```

### CI with data

```bash
econflow validate --data  # config + data file valid?
```
