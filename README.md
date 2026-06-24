# EconFlow

**Reusable panel econometrics research platform.**

[![CI](https://github.com/abrhamgs3/econflow/actions/workflows/ci.yml/badge.svg)](https://github.com/abrhamgs3/econflow/actions/workflows/ci.yml)
[![PyPI version](https://img.shields.io/pypi/v/econflow.svg)](https://pypi.org/project/econflow/)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

EconFlow is an open-source Python framework for running reproducible
cross-country panel econometric analyses — from raw data download through
publication-ready regression tables, figures, and LaTeX narrative sections.
It was extracted from the *AI Adoption and Total Factor Productivity* paper
and is designed to be reused for any panel study.

---

## Features

- **End-to-end pipeline** — ingest → process → estimate → diagnose → render
- **Panel econometrics** — FE, two-way FE, GLS, IV, GMM, quantile estimators powered by `linearmodels`
- **Reproducibility** — every run hashes its inputs and outputs to a `run_metadata.json` provenance record
- **Configurable** — projects defined by three YAML files; no code changes required to run a new study
- **Tested** — 100-test suite covering regression helpers, exception hierarchy, and provenance recording
- **Interactive dashboard** — optional Streamlit interface for exploring results

---

## Installation

```bash
pip install econflow
```

For development:

```bash
git clone https://github.com/abrhamgs3/econflow.git
cd econflow
pip install -e ".[dev]"
```

To add the optional Streamlit dashboard:

```bash
pip install "econflow[app]"
```

---

## Quick Start

```bash
# Verify the environment
econflow doctor

# Run the full pipeline against your panel CSV
econflow run --data-path path/to/panel_clean.csv

# Specify custom output directories
econflow run --data-path path/to/panel_clean.csv \
             --tables-dir results/tables \
             --figures-dir results/figures \
             --paper-dir  results/paper/sections
```

The pipeline expects a CSV with at minimum the columns specified in your
`config.yaml` (`country`, `year`, and log-transformed variables by default).
See [examples/ai_productivity_paper/](examples/ai_productivity_paper/) for
a fully annotated project with config files, reference outputs, and an
interactive dashboard.

---

## Project Layout

A project is defined by three YAML files, conventionally placed under
`examples/<project_name>/config/`:

| File | Purpose |
|---|---|
| `config.yaml` | Data sources, sample period, variable definitions, cache directory |
| `models.yaml` | Model specifications consumed by `SensitivityRunner` |
| `outputs.yaml` | Output directories, file names, figure formats |

---

## Package Structure

```
src/econflow/
├── cli.py            CLI — doctor and run commands
├── pipeline.py       Sequential pipeline orchestrator
├── provenance.py     ProvenanceRecorder — SHA-256 run metadata
├── exceptions.py     Domain exception hierarchy (EconFlowError)
├── data/             Panel CSV validation and loading
├── econometrics/     Active panel econometrics suites (FE, robustness, sensitivity, falsification)
├── features/         Feature engineering (AI index, TFP, transforms)
├── visualization/    Publication-quality figures
├── reporting/        LaTeX narrative generation
├── core/             Scaffold infrastructure (config, registry, provenance)
├── ingestion/        Data connectors — World Bank, OECD, PWT
├── processing/       Harmonisation, quality checks
├── estimation/       Estimator classes — OLS, FE, RE, IV, GMM, quantile
├── diagnostics/      Hausman, Sargan-Hansen, Pesaran CD, Arellano-Bond AR
├── sensitivity/      SensitivityRunner, ResultsComparison
└── outputs/          Table, figure, and report renderers
```

---

## Testing

```bash
pytest                           # full suite (100 tests)
pytest tests/regression/         # regression helper tests
pytest tests/test_provenance.py  # provenance recorder tests

# Live-data reproduction test (requires network access)
ECONFLOW_RUN_LIVE_REGRESSION=1 pytest tests/regression/test_live_data_reproduction.py
```

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
  author  = {Ab},
  title   = {{EconFlow}: Reusable panel econometrics research platform},
  year    = {2026},
  version = {0.1.0},
  url     = {https://github.com/abrhamgs3/econflow},
  license = {MIT}
}
```

A `CITATION.cff` file is also provided for tools that read it automatically.

---

## License

[MIT](LICENSE) © 2026 Ab
