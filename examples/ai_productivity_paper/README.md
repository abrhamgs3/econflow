# AI & Productivity Paper — Replication Package

The original research project that motivated EconFlow's development:

> *AI Adoption and Total Factor Productivity: Panel Evidence from 193 Countries*

This example demonstrates EconFlow running a production-grade research pipeline
with 13 model specifications, multi-source data ingestion (World Bank, OECD, PWT),
and a full replication package.  It is one example among many — see
[`examples/`](../) for others.

---

## Directory layout

```
examples/ai_productivity_paper/
├── config/
│   ├── config.yaml        # Project-level settings (data sources, variables)
│   ├── models.yaml        # 13 regression model specifications
│   └── outputs.yaml       # Output directories and filenames
├── app/
│   └── streamlit_app.py   # Interactive four-tab research dashboard
└── reference_outputs/     # Frozen paper-version outputs for regression testing
    ├── data/
    ├── figures/
    ├── tables/
    ├── paper_sections/
    └── manifest.yaml
```

---

## Quick start

```bash
# Install EconFlow
pip install -e .

# Validate the paper configuration
econflow validate examples/ai_productivity_paper/config/

# Run the pipeline with the paper configuration
econflow run \
    --config  examples/ai_productivity_paper/config/config.yaml \
    --models  examples/ai_productivity_paper/config/models.yaml \
    --outputs examples/ai_productivity_paper/config/outputs.yaml
```

For the interactive dashboard:

```bash
streamlit run examples/ai_productivity_paper/app/streamlit_app.py
```

---

## Configuration files

| File | Purpose |
|------|---------|
| `config/config.y