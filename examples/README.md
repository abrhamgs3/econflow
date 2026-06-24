# Examples

This directory contains domain-specific worked examples built on top of
the EconFlow framework.

| Directory | Description |
|-----------|-------------|
| [`ai_productivity_paper/`](ai_productivity_paper/) | Replication package for *AI Adoption and Total Factor Productivity: Panel Evidence from 193 Countries* |

## Adding your own example

1. Create `examples/<your_project>/`
2. Add `config/config.yaml`, `config/models.yaml`, and `config/outputs.yaml`
   (copy from `ai_productivity_paper/config/` as templates)
3. Optionally add `app/streamlit_app.py` for an interactive dashboard
