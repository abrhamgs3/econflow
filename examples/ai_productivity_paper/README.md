# AI & Productivity Paper — Replication Package

Replication assets for:

> *AI Adoption and Total Factor Productivity: Panel Evidence from 193 Countries*

## Directory layout

```
examples/ai_productivity_paper/
├── config/
│   ├── config.yaml        # Project-level settings (data paths, cache)
│   ├── models.yaml        # All 13 regression model specifications
│   └── outputs.yaml       # Output directories and filenames
├── app/
│   └── streamlit_app.py   # Interactive four-tab research dashboard
├── data/
│   └── demo/
│       └── panel_demo.csv # Synthetic 30-country demo dataset (not included in repo)
└── reference_outputs/     # Frozen paper-version outputs for regression testing
    ├── data/
    ├── figures/
    ├── tables/
    ├── paper_sections/
    └── manifest.yaml
```

## Quick start

```bash
# Install EconFlow
pip install -e .

# Launch the interactive dashboard
streamlit run examples/ai_productivity_paper/app/streamlit_app.py

# Run with custom data
econflow run --data path/to/panel_clean.csv \
             --config examples/ai_productivity_paper/config/config.yaml
```

## Configuration files

| File | Purpose |
|------|---------|
| `config/config.yaml` | Data sources (WDI, OECD, PWT), cache directory, logging |
| `config/models.yaml` | 13 model specifications with estimators and controls |
| `config/outputs.yaml` | Output paths and filenames for tables, figures, paper sections |

## Reference outputs

`reference_outputs/` contains the frozen outputs from the published paper run.
These are used by `tests/regression/` to ensure the pipeline is reproducible.
