"""
econflow.commands.init — ``econflow init`` command implementation.

Creates a complete EconFlow project skeleton in *directory*:

    <directory>/
    ├── config/
    │   ├── config.yaml    ← data paths, variable names, project metadata
    │   ├── models.yaml    ← model specification list
    │   └── outputs.yaml   ← table and figure output settings
    ├── data/
    │   ├── raw/           ← original source files (never modified)
    │   └── processed/     ← cleaned, merged panel CSV
    ├── outputs/
    │   ├── tables/
    │   ├── figures/
    │   └── provenance/
    ├── paper/
    │   └── sections/      ← auto-generated LaTeX narrative fragments
    ├── scripts/
    │   ├── 01_download_data.py
    │   └── 02_clean_data.py
    ├── docs/
    ├── notebooks/
    ├── README.md
    └── .gitignore

Usage
-----
    econflow init                        # scaffold in current directory
    econflow init my_project             # scaffold in ./my_project/
    econflow init my_project --force     # overwrite existing files
"""

from __future__ import annotations

from pathlib import Path

from rich.console import Console

# ---------------------------------------------------------------------------
# Directory structure
# ---------------------------------------------------------------------------

_DIRECTORIES = [
    "config",
    "data/raw",
    "data/processed",
    "outputs/tables",
    "outputs/figures",
    "outputs/provenance",
    "paper/sections",
    "scripts",
    "docs",
    "notebooks",
]

# ---------------------------------------------------------------------------
# File templates
# ---------------------------------------------------------------------------

_CONFIG_YAML = """\
# ============================================================
# EconFlow project configuration
# ============================================================
# Edit this file to match your panel dataset and research question.
# Run `econflow validate` to check this file before running the pipeline.

project:
  name: "{name}"
  description: "Panel econometric analysis"
  version: "0.1.0"
  authors:
    - name: ""
      email: ""

# ------------------------------------------------------------
# Data — point to your processed panel CSV
# ------------------------------------------------------------
data:
  # Path to the processed panel CSV (relative to this config file's directory)
  path: "data/processed/panel.csv"

  # Column names for the two panel dimensions
  entity_col: "entity"   # cross-sectional unit (firm, country, individual, ...)
  time_col:   "time"     # time period identifier (year, quarter, month, ...)

  # EconFlow will check that all of these columns exist in the CSV
  required_columns:
    - "entity"
    - "time"
    - "outcome"
    - "treatment"
    - "covariate_1"

# ------------------------------------------------------------
# Variables — define your outcome and regressors
# ------------------------------------------------------------
variables:
  dependent: "outcome"          # left-hand-side variable
  regressors:                   # right-hand-side regressors (excluding constant)
    - "treatment"
    - "covariate_1"
  # controls: []                # extra controls added to every model specification

# ------------------------------------------------------------
# Sample restrictions (optional)
# ------------------------------------------------------------
# sample:
#   start: 2000
#   end:   2020
#   min_obs_per_entity: 5      # drop entities with fewer than N time periods
"""

_MODELS_YAML = """\
# ============================================================
# EconFlow model specifications
# ============================================================
# Each entry defines one regression model.
# All models below are passed to `econflow run --models`.
#
# Supported estimators
# --------------------
# OLS  — Pooled OLS (linearmodels.PooledOLS, heteroskedasticity-robust SEs)
# FE   — Panel fixed effects (linearmodels.PanelOLS, within estimator)
#
# Cluster options: "entity" | "time" | null (robust)

models:

  # ------------------------------------------------------------------
  # Specification 1 — Pooled OLS baseline
  # ------------------------------------------------------------------
  - id:            "pooled_ols"
    label:         "Pooled OLS"
    estimator:     "OLS"
    dependent:     "outcome"
    regressors:    ["treatment", "covariate_1"]
    entity_effects: false
    time_effects:   false
    description: >
      Baseline specification ignoring panel structure.
      Included to motivate the need for fixed effects.

  # ------------------------------------------------------------------
  # Specification 2 — Entity fixed effects
  # ------------------------------------------------------------------
  - id:            "entity_fe"
    label:         "Entity FE"
    estimator:     "FE"
    dependent:     "outcome"
    regressors:    ["treatment", "covariate_1"]
    entity_effects: true
    time_effects:   false
    cluster:       "entity"
    description: >
      Within estimator with entity (cross-sectional) fixed effects.
      Controls for all time-invariant unit characteristics.

  # ------------------------------------------------------------------
  # Specification 3 — Two-way fixed effects
  # ------------------------------------------------------------------
  - id:            "twoway_fe"
    label:         "Two-Way FE"
    estimator:     "FE"
    dependent:     "outcome"
    regressors:    ["treatment", "covariate_1"]
    entity_effects: true
    time_effects:   true
    cluster:       "entity"
    description: >
      Entity + time fixed effects.
      Also absorbs aggregate time-series shocks common to all units.
"""

_OUTPUTS_YAML = """\
# ============================================================
# EconFlow output configuration
# ============================================================
# Controls where results are written and in which formats.

outputs:
  # All outputs are placed under this directory (relative to project root)
  base_dir: "outputs"

  tables:
    # Supported formats: csv, latex
    formats: ["csv", "latex"]

    comparison_table:
      # Output filename (without extension — both .csv and .tex will be written)
      filename: "table_main_results"

      # Model IDs to include, in column order (must match models.yaml ids)
      models:
        - "pooled_ols"
        - "entity_fe"
        - "twoway_fe"

  # figures:
  #   dpi: 300
  #   format: "pdf"   # pdf | png | svg
"""

_GITIGNORE = """\
# Python
__pycache__/
*.py[cod]
*.pyo
.venv/
.env
*.egg-info/
dist/
build/

# Data (raw and processed data should not be committed if large)
# data/raw/
# data/processed/

# EconFlow generated outputs (reproducible — no need to commit)
outputs/tables/
outputs/figures/
outputs/provenance/
paper/sections/

# Jupyter
.ipynb_checkpoints/

# OS
.DS_Store
Thumbs.db
"""

_README = """\
# {name}

Panel econometric analysis using [EconFlow](https://github.com/abrhamgs3/econflow).

## Quick start

```bash
# 1. Install EconFlow
pip install -e /path/to/econflow   # or: pip install econflow (once published)

# 2. Download and prepare your data
python scripts/01_download_data.py
python scripts/02_clean_data.py

# 3. Validate the project configuration
econflow validate

# 4. Run the pipeline
econflow run \\
    --config  config/config.yaml \\
    --models  config/models.yaml \\
    --outputs config/outputs.yaml
```

## Project structure

```
config/         YAML configuration files
data/raw/       Original source data (unmodified)
data/processed/ Cleaned panel CSV ready for estimation
outputs/        Regression tables, figures, provenance records
paper/          LaTeX manuscript and auto-generated sections
scripts/        Data download and cleaning scripts
docs/           Project documentation
notebooks/      Exploratory analysis notebooks
```

## Configuration

Edit `config/config.yaml` to point to your data file and specify the
entity column, time column, and regression variables.

Edit `config/models.yaml` to define which specifications to run.

Run `econflow validate` after any configuration change to catch errors
before running the full pipeline.

## Reproduce results

```bash
econflow run \\
    --config  config/config.yaml \\
    --models  config/models.yaml \\
    --outputs config/outputs.yaml
```

Tables are written to `outputs/tables/`.
Provenance (SHA-256 hashes, timestamps) is written to `outputs/provenance/`.
"""

_SCRIPT_DOWNLOAD = '''\
"""
scripts/01_download_data.py — Download raw data for {name}.

Edit this script to add your data sources.  When complete, run:

    python scripts/01_download_data.py

All output files should be written to data/raw/.
"""

from pathlib import Path

RAW_DIR = Path(__file__).parent.parent / "data" / "raw"
RAW_DIR.mkdir(parents=True, exist_ok=True)


def main() -> None:
    # TODO: implement data download
    # Example: download from World Bank, OECD, or a local CSV
    raise NotImplementedError(
        "Edit this script to download your raw data files. "
        "Write output files to data/raw/."
    )


if __name__ == "__main__":
    main()
'''

_SCRIPT_CLEAN = '''\
"""
scripts/02_clean_data.py — Merge and clean raw data into a panel CSV for {name}.

Reads from data/raw/ and writes data/processed/panel.csv.
Run after scripts/01_download_data.py:

    python scripts/02_clean_data.py
"""

from pathlib import Path

import pandas as pd

RAW_DIR       = Path(__file__).parent.parent / "data" / "raw"
PROCESSED_DIR = Path(__file__).parent.parent / "data" / "processed"
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

OUTPUT_FILE = PROCESSED_DIR / "panel.csv"


def main() -> None:
    # TODO: implement data cleaning and merging
    # The output must be a CSV with at least:
    #   - entity column (matches config.yaml data.entity_col)
    #   - time column   (matches config.yaml data.time_col)
    #   - dependent and regressor columns
    raise NotImplementedError(
        "Edit this script to build data/processed/panel.csv from your raw data."
    )


if __name__ == "__main__":
    main()
    print(f"Written: {{OUTPUT_FILE}}")
'''


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def run_init(
    directory: Path,
    name: str,
    force: bool,
    console: Console,
) -> int:
    """
    Scaffold a new EconFlow project in *directory*.

    Parameters
    ----------
    directory:
        Target directory.  Created if it does not exist.
    name:
        Project name used in YAML files and README.  Defaults to the
        directory's basename if empty.
    force:
        If True, overwrite existing files without prompting.
    console:
        Rich console for output.

    Returns
    -------
    int
        0 on success, 1 on failure.
    """
    directory = directory.resolve()

    # Derive project name from directory if not supplied
    if not name:
        name = directory.name if directory.name != "." else directory.parent.name

    # Safety check: non-empty existing directory without --force
    if directory.exists() and any(directory.iterdir()):
        if not force:
            console.print(
                f"[bold red]✘ Directory already exists and is non-empty:[/bold red] {directory}\n"
                "  Use [bold]--force[/bold] to overwrite."
            )
            return 1
        console.print(f"[yellow]⚠ Overwriting existing files in {directory}[/yellow]")

    console.print(f"\n[bold]EconFlow init[/bold] — creating project [cyan]{name}[/cyan]\n")

    # ---------------------------------------------------------------- Directories
    console.print("  [dim]Creating directory structure…[/dim]")
    for rel_dir in _DIRECTORIES:
        target = directory / rel_dir
        target.mkdir(parents=True, exist_ok=True)
        # Write a .gitkeep so empty dirs are tracked by git
        gitkeep = target / ".gitkeep"
        if not gitkeep.exists():
            gitkeep.write_text("", encoding="utf-8")
        console.print(f"  [green]✔[/green]  {rel_dir}/")

    # ---------------------------------------------------------------- Config files
    console.print()
    console.print("  [dim]Writing configuration files…[/dim]")

    _write_file(
        directory / "config" / "config.yaml",
        _CONFIG_YAML.format(name=name),
        force=force,
        console=console,
    )
    _write_file(
        directory / "config" / "models.yaml",
        _MODELS_YAML,
        force=force,
        console=console,
    )
    _write_file(
        directory / "config" / "outputs.yaml",
        _OUTPUTS_YAML,
        force=force,
        console=console,
    )

    # ---------------------------------------------------------------- Scripts
    console.print()
    console.print("  [dim]Writing starter scripts…[/dim]")
    _write_file(
        directory / "scripts" / "01_download_data.py",
        _SCRIPT_DOWNLOAD.format(name=name),
        force=force,
        console=console,
    )
    _write_file(
        directory / "scripts" / "02_clean_data.py",
        _SCRIPT_CLEAN.format(name=name),
        force=force,
        console=console,
    )

    # ---------------------------------------------------------------- README / .gitignore
    console.print()
    console.print("  [dim]Writing README and .gitignore…[/dim]")
    _write_file(
        directory / "README.md",
        _README.format(name=name),
        force=force,
        console=console,
    )
    _write_file(
        directory / ".gitignore",
        _GITIGNORE,
        force=force,
        console=console,
    )

    # ---------------------------------------------------------------- Summary
    console.print()
    console.rule("[bold green]Project ready[/bold green]")
    console.print(f"\n  Project [cyan]{name}[/cyan] created at [dim]{directory}[/dim]\n")
    console.print("  Next steps:\n")
    console.print("    1. Edit [bold]config/config.yaml[/bold] — set data path and variable names")
    console.print("    2. Add your data to [bold]data/raw/[/bold]")
    console.print(
        "    3. Implement [bold]scripts/01_download_data.py[/bold]"
        " and [bold]scripts/02_clean_data.py[/bold]"
    )
    console.print("    4. Run [bold]econflow validate[/bold] to check configuration")
    console.print(
        "    5. Run [bold]econflow run --config config/config.yaml ...[/bold] to estimate"
    )
    console.print()

    return 0


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _write_file(
    path: Path,
    content: str,
    *,
    force: bool,
    console: Console,
) -> None:
    """Write *content* to *path*, respecting *force* flag."""
    rel = path.name  # just filename for display
    try:
        rel = path.relative_to(path.parent.parent)
    except ValueError:
        pass

    if path.exists() and not force:
        console.print(f"  [yellow]–[/yellow]  {rel}  [dim](skipped — already exists)[/dim]")
        return

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    console.print(f"  [green]✔[/green]  {rel}")
