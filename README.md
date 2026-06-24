# EconFlow

**Reusable panel econometrics research platform.**

EconFlow provides the infrastructure to run reproducible cross-country panel
econometric analyses from raw data download through publication-ready tables
and figures.  Any project is defined by a configuration file under `projects/`;
the platform handles ingestion, processing, estimation, diagnostics, and output
rendering.

---

## Installation

```bash
pip install econflow
# or, for development
git clone https://github.com/abrhamgs3/econflow.git
cd econflow
uv pip install -e ".[dev]"
```

## Quick Start

```bash
econflow project list              # list registered projects
econflow run example               # run the example project end-to-end
econflow validate example          # validate config and data only
econflow reproduce example         # reproduce a prior run from provenance record
```

## Project Configuration

A project lives under `projects/<name>/` and consists of three files:

| File | Purpose |
|------|---------|
| `config.yaml` | Data sources, sample period, variable definitions |
| `models.yaml` | Model specifications consumed by `SensitivityRunner` |
| `outputs.yaml` | Output directories, figure formats, table formats |

See `projects/example/` for a fully annotated template.

## Package Layout

```
src/econflow/
├── core/           Config, provenance, pipeline, registry, exceptions
├── ingestion/      Data connectors: World Bank, OECD, PWT
├── processing/     Harmonisation, AI index, TFP, transforms, quality
├── estimation/     FE, GLS, IV, GMM, quantile panel estimators
├── diagnostics/    Hausman, Sargan-Hansen, Pesaran CD, Arellano-Bond AR
├── sensitivity/    SensitivityRunner, ResultsComparison
├── visualization/  Publication figures
├── reporting/      LaTeX narrative generation
└── outputs/        Table, figure, and report renderers
```

## Testing

```bash
pytest                          # all tests
pytest tests/regression/        # regression helper tests
pytest tests/test_provenance.py # provenance recorder tests
APRP_RUN_LIVE_REGRESSION=1 pytest tests/regression/test_live_data_reproduction.py
```

## Origin

EconFlow was extracted from the AI & Productivity paper repository
(`ai-productivity-paper`) during Sprint 2 of the platform migration.
The paper repository remains the scientific ground truth; econflow is
the reusable platform that powers it.

## License

MIT
