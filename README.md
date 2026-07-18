# EconFlow

**Open-source platform for reproducible panel econometric research.**

[![CI](https://github.com/abrhamgs3/econflow/actions/workflows/ci.yml/badge.svg)](https://github.com/abrhamgs3/econflow/actions/workflows/ci.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

EconFlow is an open-source Python framework for running reproducible
panel econometric analyses — from raw data through publication-ready
regression tables, figures, and integrity certificates. It is designed for
any panel study, regardless of dataset, discipline, or research question.

---

## Features

- **End-to-end pipeline** — ingest → validate → estimate → diagnose → render → certify
- **Panel econometrics** — FE, two-way FE, RE, IV estimators via `linearmodels` (GMM and panel quantile are planned for v1.0 — `econflow validate` will warn if you reference them)
- **Reproducibility** — every run produces a provenance certificate with SHA-256 fingerprints
- **Config-driven** — projects defined by three YAML files; no code changes to run a new study
- **Integrity chain** — `certify` → `verify` → `package` → `reproduce` for full replication support
- **Plugin system** — extend estimators, diagnostics, and renderers via `@register` decorators

---

## Installation

EconFlow is not yet published to PyPI. Install directly from source:

```bash
git clone https://github.com/abrhamgs3/econflow.git
cd econflow
pip install -e ".[dev]"
```

This installs EconFlow in editable mode with all dependencies, including
`linearmodels`, `pandas`, `rich`, `pydantic`, and `pytest`.

Verify the installation:

```bash
econflow doctor
```

---

## Quick Start

```bash
# 1. Create a new project skeleton
econflow init my_study
cd my_study

# 2. Edit config/config.yaml — set data path, entity/time columns, variables

# 3. Validate configuration before running
econflow validate config/

# 4. Run the analysis pipeline
econflow run \
    --config  config/config.yaml \
    --models  config/models.yaml \
    --outputs config/outputs.yaml

# 5. Generate a reproducibility certificate
econflow certify
```

See [`examples/getting_started/`](examples/getting_started/) for a complete
10-minute tutorial using the Grunfeld firm investment panel.

---

## Project Layout

Every EconFlow study is defined by three YAML files:

| File | Purpose |
|---|---|
| `config.yaml` | Data path, entity/time column names, variable definitions |
| `models.yaml` | Regression specifications (estimator, regressors, fixed effects) |
| `outputs.yaml` | Output directories and file formats (CSV, LaTeX, HTML) |

```
my_study/
├── config/
│   ├── config.yaml
│   ├── models.yaml
│   └── outputs.yaml
├── data/
│   ├── raw/
│   └── processed/
├── outputs/
│   ├── tables/
│   ├── figures/
│   └── provenance/
├── scripts/
└── docs/
```

---

## Package Structure

```
src/econflow/
├── cli.py            CLI entry point (16 commands)
├── pipeline_generic.py  Config-driven pipeline orchestrator
├── exceptions.py     Domain exception hierarchy (EconFlowError)
├── commands/         CLI command implementations
├── config/           Pydantic v2 config models, linter, validator (13 rules)
├── estimation/       Panel estimators — OLS, FE, TWFE, RE, FD, IV, GMM, Quantile
├── diagnostics/      Post-estimation tests — Hausman, BP, Pesaran CD, VIF, AR(1)
├── outputs/          Table, figure, and report renderers (CSV, LaTeX, MD, HTML, JSON)
├── integrity/        Provenance certificates, drift detection, replication packages
├── replication/      Blind replication engine — inspect, reproduce, compare
├── ingestion/        Data connectors — CSV, World Bank, OECD, PWT, FRED
└── core/             Shared exceptions, registry, and configuration infrastructure
```

---

## CLI Reference

```
econflow init         Create a new project skeleton
econflow validate     Check YAML configuration files
econflow run          Execute the analysis pipeline
econflow report       Render publication bundle (tables + figures)
econflow certify      Generate a reproducibility certificate
econflow verify       Verify a certificate against current outputs
econflow package      Build a self-contained replication package
econflow inspect      Inspect a replication package
econflow reproduce    Re-execute a replication package
econflow compare      Compare two sets of outputs
econflow doctor       Check the EconFlow environment
econflow info         Show platform and project information
econflow fetch        Fetch data from an external connector
econflow cache        Manage the local data cache
econflow datasets     List available data connectors
econflow release-check  Run the release quality gate
```

---

## Testing

```bash
pytest                   # full suite
pytest tests/unit/       # unit tests only
pytest tests/integration/ # integration tests
```

---

## Examples

| Example | Description |
|---------|-------------|
| [`examples/getting_started/`](examples/getting_started/) | 10-minute tutorial — Grunfeld firm investment panel (1935–1954) |
| [`examples/blind_replication/`](examples/blind_replication/) | Blind replication walkthrough |
| [`examples/ai_productivity_paper/`](examples/ai_productivity_paper/) | The original research project that motivated EconFlow's development — *AI Adoption and Total Factor Productivity: Panel Evidence from 193 Countries* |

---

## Contributing

Contributions are welcome. Please read [CONTRIBUTING.md](CONTRIBUTING.md)
before opening a pull request. Bug reports and feature requests go in
[GitHub Issues](https://github.com/abrhamgs3/econflow/issues).

---

## Citation

If you use EconFlow in academic work, please cite it:

```bibtex
@software{econflow2026,
  author  = {Meressa, Abrha Megos},
  title   = {{EconFlow}: Open-source platform for reproducible panel econometric research},
  year    = {2026},
  version = {0.1.0},
  url     = {https://github.com/abrhamgs3/econflow},
  license = {MIT}
}
```

A `CITATION.cff` file is also provided for tools that read it automatically.

---

## License

[MIT](LICENSE) © 2026 Abrha Megos Meressa
