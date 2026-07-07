# my_test_study

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
econflow run \
    --config  config/config.yaml \
    --models  config/models.yaml \
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
econflow run \
    --config  config/config.yaml \
    --models  config/models.yaml \
    --outputs config/outputs.yaml
```

Tables are written to `outputs/tables/`.
Provenance (SHA-256 hashes, timestamps) is written to `outputs/provenance/`.
