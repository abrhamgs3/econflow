# EconFlow — First Five Minutes

A verified step-by-step tutorial. Every command below has been executed in a
clean virtual environment and confirmed to produce the output shown.

---

## Prerequisites

- Python 3.10 or later
- `git`

---

## Step 1 — Clone and install (≈ 2 minutes)

```bash
git clone https://github.com/abrhamgs3/econflow.git
cd econflow
pip install -e ".[dev]"
```

Verify:

```bash
econflow doctor
```

Expected output (abbreviated):

```
─────────────── EconFlow doctor ───────────────
  Python       ✔  3.10+
  linearmodels ✔  installed
  pandas       ✔  installed
  rich         ✔  installed
  pydantic     ✔  installed
```

All rows should show ✔. If any show ✘, install the missing package with
`pip install <package>`.

---

## Step 2 — Run the getting-started example (≈ 2 minutes)

The `examples/getting_started/` directory contains a complete, self-contained
tutorial project using the Grunfeld firm investment panel (1935–1954).

```bash
cd examples/getting_started

econflow validate config/
```

Expected output:

```
─────────────── EconFlow validate ───────────────
  ✔  config/config.yaml     — syntax OK, schema OK
  ✔  config/models.yaml     — 3 model specification(s)
  ✔  config/outputs.yaml    — outputs config OK
─────────────────────────────────────────────────
  All checks passed.
```

Then run the pipeline:

```bash
econflow run \
    --config  config/config.yaml \
    --models  config/models.yaml \
    --outputs config/outputs.yaml
```

Expected output (abbreviated):

```
─────────── EconFlow pipeline ───────────
  Stage 1  Load data          ✔
  Stage 2  Validate           ✔
  Stage 3  Estimate models    ✔  (3 models)
  Stage 4  Diagnostics        ✔
  Stage 5  Render outputs     ✔
─────────────────────────────────────────
  Tables written to outputs/tables/
```

Check the output:

```bash
ls outputs/tables/
```

You should see:

```
table_fe_investment.csv
table_fe_investment.tex
```

Inspect the LaTeX table:

```bash
cat outputs/tables/table_fe_investment.tex
```

The significance stars should look like `$^{***}$`, `$^{**}$`, `$^{*}$`
(not broken cascaded forms like `$^{$^{*}$}$`).

---

## Step 3 — Start your own project (≈ 1 minute)

```bash
# Return to your working directory
cd ~/my_research

econflow init my_study
cd my_study
```

The scaffold creates:

```
my_study/
├── config/
│   ├── config.yaml    ← edit these three files
│   ├── models.yaml
│   └── outputs.yaml
├── data/raw/
├── data/processed/    ← put panel.csv here
├── outputs/
├── scripts/
└── tests/
```

Edit `config/config.yaml` to point to your data file and name your variables,
then validate:

```bash
econflow validate config/
```

Once your data is in `data/processed/panel.csv`, run the pipeline with the
same command as in Step 2 (substituting `my_study`'s config paths).

---

## Troubleshooting

**`econflow: command not found`**
The package was not installed into your active Python environment. Run
`pip install -e ".[dev]"` from the `econflow/` directory again, or activate
the correct virtual environment.

**`validate` fails with `data file not found`**
The `--data` flag checks whether the CSV exists. On a fresh project, skip it:
`econflow validate config/` (without `--data`) validates only the YAML files.

**Pipeline fails with `KeyError: 'entity'`**
Your CSV column names don't match `config.yaml`. Check `data.entity_col` and
`data.time_col` in `config/config.yaml`.

**LaTeX stars appear as `$^{$^{*}$}$`**
This was a bug fixed in Sprint 11A. Make sure you have the latest code:
`git pull && pip install -e ".[dev]"`.

---

## What to read next

- `examples/getting_started/README.md` — annotated walkthrough of the
  Grunfeld example
- `docs/architecture/WORKSPACE.md` — project layout conventions
- `docs/architecture/CONFIG_REFERENCE.md` — every YAML option documented
- `CONTRIBUTING.md` — how to report issues and submit patches
