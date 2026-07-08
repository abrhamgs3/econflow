# EconFlow CLI Guide

A researcher should never need to read source code to use EconFlow.
This guide covers every command with synopsis, options, examples, common
mistakes, and expected output.

---

## Complete workflow

```bash
# 1. Check your environment
econflow doctor

# 2. Scaffold a new project
econflow init my_study
cd my_study

# 3. Place your panel data
cp /path/to/panel.csv data/processed/panel.csv

# 4. Edit config files (config.yaml, models.yaml, outputs.yaml)
# Then validate them
econflow validate config/

# 5. Run the analysis
econflow run \
    --config  config/config.yaml \
    --models  config/models.yaml \
    --outputs config/outputs.yaml

# 6. Certify reproducibility
econflow certify \
    --project-name "My Study" \
    --data data/processed/panel.csv \
    --config config/config.yaml

# 7. Verify against a baseline
econflow verify --baseline outputs/certificate.json

# 8. Package for journal submission
econflow package \
    --certificate outputs/certificate.json \
    --config config/config.yaml \
    --config config/models.yaml
```

---

## `econflow --version`

Print the installed version.

```
EconFlow 0.1.0
```

---

## `econflow doctor`

Environment health check.  Run this first on any new machine.

**Checks performed:**

| Section | Checks |
|---------|--------|
| System | Python version, OS, CPU, RAM |
| Core packages | pandas, numpy, linearmodels, statsmodels, … |
| External tools | git, LaTeX (pdflatex/xelatex), pandoc, pip, uv |
| Optional | pytest, ruff, pyarrow, jupyter, streamlit |
| Project structure | config/, data/, outputs/ present |
| Configuration | YAML syntax valid, schema + semantic rules pass |

**Exit codes:** `0` = all required checks pass; `1` = one or more required checks fail.

**Examples:**

```bash
econflow doctor
cd my_study && econflow doctor
```

**Common mistakes:**

- Running doctor before activating your virtual environment — package checks
  fail even if the packages are installed.  
  Fix: activate venv first, then re-run `econflow doctor`.

- LaTeX showing WARN but tables still render to `.tex` — the `.tex` file is
  written regardless; WARN means you cannot *compile* it to PDF locally.  
  Fix: `sudo apt install texlive-latex-extra` (Ubuntu) or install TeX Live.

**Expected output (abbreviated):**

```
EconFlow — environment health check

System
  ✔  SYS-01  Python 3.11.9
  ℹ  SYS-02  Operating system     Linux 6.5 (x86_64)

Core packages
  ✔  PKG-01  pandas 2.2.2
  ✔  PKG-04  linearmodels 6.1

External tools
  ✔  EXT-01  git                  git version 2.43.0
  ✔  EXT-02  LaTeX (pdflatex)     pdfTeX 3.141592653

Project structure
  ✔  PRJ-01  config.yaml          config/config.yaml
  ✔  PRJ-02  models.yaml          config/models.yaml

✔ Ready  (24 passed, 2 warning(s))
```

---

## `econflow init [DIRECTORY]`

Scaffold a new project with all required directories and template config files.

**Options:**

| Flag | Description |
|------|-------------|
| `--name TEXT` | Project name (defaults to directory basename) |
| `--force` | Overwrite existing files without prompting |

**Examples:**

```bash
econflow init                     # init in current directory
econflow init my_study            # init in ./my_study/
econflow init my_study --force    # overwrite existing files
```

**Common mistakes:**

- Forgetting to `cd` into the project directory before running other commands.  
  Fix: `cd my_study && econflow doctor`

- Using a project name with spaces.  
  Fix: `econflow init my_study_2024` (underscores, not spaces)

- Running `econflow init` twice without `--force`.  
  Fix: `econflow init my_study --force`

**Expected output:**

```
EconFlow init — creating project my_study …
  ✔  config/config.yaml
  ✔  config/models.yaml
  ✔  config/outputs.yaml
  ✔  data/raw/
  ✔  data/processed/
  ✔  outputs/tables/
  ✔  README.md
Project scaffold complete.  Next: cd my_study && econflow doctor
```

---

## `econflow validate [CONFIG_DIR]`

Validate configuration files against schema and semantic rules.

**Options:**

| Flag | Description |
|------|-------------|
| `--config PATH` | Explicit path to config.yaml |
| `--models PATH` | Explicit path to models.yaml |
| `--outputs PATH` | Explicit path to outputs.yaml |
| `--data` | Also validate the data file referenced in config.yaml |
| `--verbose, -v` | Show passing checks as well as failures |

**Examples:**

```bash
econflow validate                 # validate ./config/ (default)
econflow validate config/         # explicit directory
econflow validate examples/getting_started/config/
econflow validate --data          # also check data columns
econflow validate \
    --config  config/config.yaml \
    --models  config/models.yaml \
    --outputs config/outputs.yaml
```

**Common mistakes:**

- Running `econflow run` before `econflow validate` — validation errors surface
  as confusing runtime errors.  Always validate first.

- YAML files with tabs instead of spaces — YAML parsers reject tabs.  
  Fix: configure your editor to use 2- or 4-space indentation.

- Regressors that don't exist in the data file.  
  Fix: `econflow validate --data` checks column presence.

**Expected output:**

```
EconFlow validate

Schema validation
  ✔  CFG-01  config.yaml syntax valid
  ✔  CFG-02  models.yaml syntax valid
  ✔  CFG-03  outputs.yaml syntax valid

Semantic validation
  ✔  L-01  project_name present
  ✔  L-04  dependent column present in data

✔ Validation passed  (0 errors, 0 warnings)
```

---

## `econflow info`

Display project information, estimator registry, and provenance status.

**Options:**

| Flag | Description |
|------|-------------|
| `--config PATH` | Path to config.yaml |
| `--models PATH` | Path to models.yaml |
| `--outputs PATH` | Path to outputs.yaml |

**Examples:**

```bash
econflow info                          # platform info (no project needed)
econflow info \
    --config  config/config.yaml \
    --models  config/models.yaml \
    --outputs config/outputs.yaml
```

**Expected output (abbreviated):**

```
EconFlow 0.1.0 · Python 3.11.9

Platform
  Project   my_study
  Root      /home/user/my_study

Estimators (8 registered)
  entity_fe  · ols  · two_way_fe  · …

Models
  (1) investment ~ value + capital  [entity_fe]
  (2) investment ~ value + capital  [two_way_fe]
```

---

## `econflow run`

Run the analysis pipeline.  Requires three config files from `econflow init`.

**Options:**

| Flag | Description |
|------|-------------|
| `--config PATH` | Path to config.yaml |
| `--models PATH` | Path to models.yaml |
| `--outputs PATH` | Path to outputs.yaml |
| `--verbose, -v` | Enable DEBUG-level logging |

**Examples:**

```bash
econflow run \
    --config  config/config.yaml \
    --models  config/models.yaml \
    --outputs config/outputs.yaml

# Getting-started example (bundled)
econflow run \
    --config  examples/getting_started/config/config.yaml \
    --models  examples/getting_started/config/models.yaml \
    --outputs examples/getting_started/config/outputs.yaml
```

**Common mistakes:**

- Passing config files in the wrong order — each flag has a specific role.

- Missing or misnamed data file.  
  Fix: `econflow validate --data` before running.

- Omitting one of the three required flags.

**Expected output (abbreviated):**

```
──────────────── EconFlow 0.1.0 ────────────────

[1/3] entity_fe — Fixed Effects (Entity)  ✔
[2/3] two_way_fe — Fixed Effects (Two-Way)  ✔
[3/3] pooled_ols — Pooled OLS  ✔

────────────────── Pipeline complete ──────────────────
  Completed in 3.2 s

outputs/tables/table_fe_investment.csv
outputs/tables/table_fe_investment.tex
```

---

## `econflow report [OUTPUT_DIR]`

**[beta]** Render a PublicationBundle from the last pipeline run.

> **Note:** `econflow run` already writes tables to `outputs/tables/`.
> Use those files for publication.  This command provides an additional
> bundle format and will be fully integrated in a future release.

**Options:**

| Flag | Description |
|------|-------------|
| `--formats TEXT` | Comma-separated renderer IDs (default: `csv,latex,markdown,html`) |
| `--overwrite/--no-overwrite` | Overwrite existing output directory |
| `--config PATH` | Path to project config.yaml |

**Examples:**

```bash
econflow report
econflow report outputs/paper --formats csv,latex
econflow report --config config/config.yaml
```

**Common mistakes:**

- Running before `econflow run` — no estimation results to render.

- Unknown format IDs — valid: `csv`, `latex`, `markdown`, `html`, `json`.

---

## `econflow certify`

Generate a reproducibility certificate recording git SHA, package versions,
and dataset fingerprints.

**Options:**

| Flag | Description |
|------|-------------|
| `--project-name TEXT` | Project name stored in the certificate |
| `--data PATH` | Input dataset to fingerprint (repeatable) |
| `--config PATH` | Config file to checksum |
| `--output PATH` | Destination for the JSON certificate |
| `--checks/--no-checks` | Run integrity checks |
| `--repo-root PATH` | Git repository root |

**Examples:**

```bash
econflow certify --project-name "My Study"

econflow certify \
    --project-name "Panel Growth Study" \
    --data data/processed/panel.csv \
    --config config/config.yaml \
    --output outputs/certificate.json
```

**Common mistakes:**

- Certifying before committing — the SHA in the certificate won't match
  the published commit.  Git commit first.

- Forgetting `--data` — reviewers cannot verify inputs without fingerprints.

---

## `econflow verify`

Compare two certificates and report environment/data drift.

**Options:**

| Flag | Description |
|------|-------------|
| `--baseline PATH` | **Required.** Path to the baseline certificate |
| `--current PATH` | Path to current certificate (live env if omitted) |
| `--output PATH` | Destination for the JSON drift report |

**Exit codes:** `0` = pass or warn; `1` = fail.

**Examples:**

```bash
econflow verify --baseline outputs/certificate.json

econflow verify \
    --baseline outputs/baseline_cert.json \
    --current outputs/current_cert.json \
    --output outputs/drift_report.json
```

---

## `econflow package`

Build a journal-ready replication package directory.

**Options:**

| Flag | Description |
|------|-------------|
| `--certificate PATH` | Reproducibility certificate to include |
| `--config PATH` | Config file(s) to copy (repeatable) |
| `--script PATH` | Replication script(s) to copy (repeatable) |
| `--output-dir PATH` | Destination directory (default: `replication_package/`) |
| `--data-readme TEXT` | Data availability note for the README |

**Examples:**

```bash
econflow package --certificate outputs/certificate.json

econflow package \
    --certificate outputs/certificate.json \
    --config config/config.yaml \
    --config config/models.yaml \
    --script scripts/01_download.py \
    --script scripts/02_run.py
```

---

## `econflow fetch CONNECTOR_ID`

Download a dataset using a registered connector.

**Options:**

| Flag | Description |
|------|-------------|
| `--param KEY=VALUE` | Connector parameter (repeatable) |
| `--cache-dir PATH` | Cache root (default: `.cache/econflow`) |
| `--force` | Re-download even if cached |
| `--no-validate` | Skip post-download validation |
| `--manifest PATH` | Write/update a dataset manifest JSON |
| `--project TEXT` | Project name for the manifest |

**Connector IDs** (see `econflow datasets` for the full list):

| ID | Source |
|----|--------|
| `world_bank` | World Bank Open Data API |
| `fred` | FRED (St. Louis Fed) |
| `oecd` | OECD.Stat (SDMX) |
| `pwt` | Penn World Tables |
| `csv` | Local CSV file |

**Examples:**

```bash
# World Bank internet usage indicator
econflow fetch world_bank \
    --param indicators=IT.NET.USER.ZS \
    --param year_start=2000 \
    --param year_end=2022

# FRED GDP and unemployment
econflow fetch fred \
    --param series_ids=GDPPC,UNRATE \
    --param start_date=2000-01-01

# Local CSV
econflow fetch csv --param path=data/raw/panel.csv

# Force re-download
econflow fetch world_bank \
    --param indicators=NY.GDP.MKTP.CD \
    --force
```

**Common mistakes:**

- Misspelling the connector ID.  Fix: `econflow datasets` lists all IDs.

- Passing list values incorrectly — use comma separation:
  `--param series_ids=A,B` not `--param series_ids=A --param series_ids=B`.

---

## `econflow cache`

Inspect and manage the local dataset cache.

### `econflow cache list`

```bash
econflow cache list
econflow cache list --cache-dir /data/.cache/econflow
```

### `econflow cache inspect KEY`

```bash
econflow cache inspect a1b2c3def456
```

### `econflow cache clear`

Requires `--yes` to confirm.

```bash
econflow cache clear --yes
```

### `econflow cache purge KEY`

```bash
econflow cache purge a1b2c3def456
```

---

## `econflow datasets`

List all registered data connectors.

```bash
econflow datasets
econflow datasets --filter world
```

---

## `econflow inspect [PROJECT_DIR]`

Run pre-flight checks before reproducing a project.

```bash
econflow inspect .
econflow inspect examples/my_study/ --strict
econflow inspect examples/my_study/ --output inspection.json
```

---

## `econflow reproduce [PROJECT_DIR]`

Reproduce a project from its configuration in an isolated subprocess.

**Options:**

| Flag | Description |
|------|-------------|
| `--output-dir PATH` | Destination for reproduced outputs |
| `--skip-inspect` | Skip pre-flight checks |
| `--no-compare` | Skip output comparison |
| `--tolerance FLOAT` | Absolute tolerance for numeric comparison |
| `--timeout INT` | Per-step timeout in seconds |

**Examples:**

```bash
econflow reproduce .
econflow reproduce examples/blind_replication/
econflow reproduce examples/my_study/ --tolerance 1e-4
```

**Common mistakes:**

- Missing `original_outputs/` — comparison is skipped automatically.
  Copy expected outputs there to enable verification.

- Cross-platform floating-point drift — use `--tolerance 1e-4`.

---

## `econflow compare BASELINE_DIR REPLICA_DIR`

Compare two output directories.

```bash
econflow compare original_outputs/ /tmp/replica/tables/
econflow compare baseline/ replica/ --tolerance 1e-4
econflow compare baseline/ replica/ --output comparison.json
```

---

## `econflow release-check`

Run the 9-check EconFlow Release Quality Gate.

```bash
econflow release-check               # full gate
econflow release-check --quick       # skip build/integration/replication
econflow release-check --checks QG-02,QG-05,QG-08
econflow release-check \
    --output docs/release/gate_report.md \
    --json gate.json
```

---

## `econflow docs config`

Generate reference documentation from the live Pydantic schema.

```bash
econflow docs config
econflow docs config --stdout
econflow docs config --output path/to/config_reference.md
```

---

## Configuration reference

See `docs/reference/configuration.md` (or run `econflow docs config`) for
a full description of every option in `config.yaml`, `models.yaml`, and
`outputs.yaml`.

## Getting started example

A complete worked example is bundled with EconFlow:

```bash
econflow run \
    --config  examples/getting_started/config/config.yaml \
    --models  examples/getting_started/config/models.yaml \
    --outputs examples/getting_started/config/outputs.yaml
```

See `examples/getting_started/README.md` for the full walkthrough.
