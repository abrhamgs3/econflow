# Examples

| Directory | Description | Level |
|-----------|-------------|-------|
| [`getting_started/`](getting_started/) | 10-minute tutorial — Grunfeld firm investment panel (1935–1954) | Beginner |
| [`ai_productivity_paper/`](ai_productivity_paper/) | Replication package — *AI Adoption and Total Factor Productivity: Panel Evidence from 193 Countries* | Advanced |

## Which example should I start with?

Start with **`getting_started/`** if you are new to EconFlow.
It uses a small built-in dataset, requires no downloads, and takes 10 minutes.

Open **`ai_productivity_paper/`** once you are comfortable with the
config-driven workflow and want to see a production-grade research pipeline
with 12 model specifications, multiple data sources, and a full replication
package.

## Adding your own example

1. Create `examples/<your_project>/`
2. Add `config/config.yaml`, `config/models.yaml`, and `config/outputs.yaml`
   (copy from `getting_started/config/` as a minimal template)
3. Run `econflow run --config examples/<your_project>/config/config.yaml ...`
