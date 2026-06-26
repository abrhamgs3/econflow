# Getting Started with EconFlow

**Time:** ~10 minutes  
**Dataset:** Grunfeld (1935–1954) — 11 US firms, 20 years, 220 observations  
**Goal:** Run a fixed-effects regression and export a publication-ready table

This tutorial uses the [Grunfeld (1958)](https://www.jstor.org/stable/1058539)
firm investment panel — a textbook dataset included in this repository. No
internet connection or data download required.

---

## Why This Example?

This tutorial introduces the core workflow of panel data analysis using a
classic dataset from econometrics.

By the end you will have:

- loaded a panel dataset
- estimated pooled OLS
- estimated entity fixed effects
- estimated two-way fixed effects
- exported publication-ready regression tables

The same workflow scales from this 220-observation example to multi-country
panels with millions of observations.

---

## What You Will Learn

| Step | Task | Time |
|------|------|------|
| 1 | Verify your environment | 1 min |
| 2 | Inspect and understand the data | 2 min |
| 3 | Configure the project | 2 min |
| 4 | Run fixed-effects estimation | 2 min |
| 5 | Read the regression table | 2 min |
| 6 | Next steps | 1 min |

---

## The Research Question

> **Does a firm's market value predict its investment, controlling for
> firm-specific heterogeneity?**

The model is:

```
invest_it = α_i + β₁ value_it + β₂ capital_it + ε_it
```

Where:
- `invest` = gross investment (millions USD)
- `value` = firm market value (millions USD)
- `capital` = capital stock (millions USD)
- `α_i` = firm fixed effect (absorbs time-invariant firm characteristics)
- `i` = firm, `t` = year

Fixed effects are necessary here because firms differ in size, industry,
and management style — factors that are constant over time but correlated
with investment. Pooled OLS would be biased.

---

## Step 1 — Verify Your Environment

```bash
pip install econflow
econflow doctor
```

Expected output:

```
EconFlow v0.1.0 — environment check
  Python         3.10+       ✓
  pandas         2.x         ✓
  statsmodels    0.14+       ✓
  linearmodels   5.3+        ✓
  rich           13+         ✓
Environment OK
```

If `linearmodels` is missing, install it:

```bash
pip install linearmodels
```

---

## Step 2 — Inspect the Data

Open `data/grunfeld.csv`. It has five columns:

| Column | Type | Description |
|--------|------|-------------|
| `firm` | string | Firm name (11 large US corporations) |
| `year` | int | Year (1935–1954) |
| `invest` | float | Gross investment (millions USD) |
| `value` | float | Firm market value (millions USD) |
| `capital` | float | Capital stock at start of year (millions USD) |

Quick data check — run this in Python:

```python
import pandas as pd

df = pd.read_csv("examples/getting_started/data/grunfeld.csv")
print(df.shape)           # (220, 5)
print(df.isnull().sum())  # all zeros — no missing values
print(df["firm"].unique())
print(df.groupby("firm").size())  # 20 observations per firm
```

Expected output:

```
(220, 5)
firm       0
year       0
invest     0
value      0
capital    0
dtype: int64

['American Steel' 'Arrow' 'Atlantic Refining' 'Diamond Match' 'General
 Electric' 'General Motors' 'Goodyear' 'IBM' 'US Steel' 'Westinghouse'
 'Chrysler']

firm
American Steel       20
Arrow                20
Atlantic Refining    20
...
```

The panel is **balanced** — every firm appears in every year.

> **Why does this matter?** Balanced panels simplify FE estimation.
> EconFlow's validation step will flag unbalanced panels and tell you
> how many firm-year observations are missing.

---

## Step 3 — Configure the Project

The project is configured by three YAML files in `config/`. You do not
need to edit them for this tutorial — they are already set up correctly.

**`config/config.yaml`** — tells EconFlow where your data is and which
columns are the entity and time identifiers:

```yaml
data:
  path: "examples/getting_started/data/grunfeld.csv"
  entity_col: "firm"
  time_col: "year"
  required_columns: [firm, year, invest, value, capital]

variables:
  dependent: "invest"
  regressors: [value, capital]
```

**`config/models.yaml`** — defines three models to run in sequence:

```yaml
models:
  - id: "pooled_ols"
    estimator: "OLS"
    entity_effects: false

  - id: "entity_fe"
    estimator: "FE"
    entity_effects: true
    cluster: "entity"

  - id: "twoway_fe"
    estimator: "FE"
    entity_effects: true
    time_effects: true
    cluster: "entity"
```

Running all three in one command lets you see *why* fixed effects matter
by comparing coefficients and standard errors across specifications.

**`config/outputs.yaml`** — specifies where to write results:

```yaml
outputs:
  base_dir: "examples/getting_started/outputs"
  tables:
    formats: [csv, latex]
    comparison_table:
      filename: "table_fe_investment"
      models: [pooled_ols, entity_fe, twoway_fe]
      stars: true
      se_type: "clustered"
```

---

## Step 4 — Run the Pipeline

```bash
econflow run \
  --config  examples/getting_started/config/config.yaml \
  --models  examples/getting_started/config/models.yaml \
  --outputs examples/getting_started/config/outputs.yaml
```

EconFlow will print a progress log:

```
EconFlow v0.1.0
─────────────────────────────────────────────────────
[1/5] Loading data ................ 220 obs, 11 firms, 20 years  ✓
[2/5] Validating panel ............ balanced, no missing values   ✓
[3/5] Running models
      pooled_ols   OLS (no FE)                                   ✓
      entity_fe    FE — entity effects, clustered SE             ✓
      twoway_fe    FE — entity + time effects, clustered SE      ✓
[4/5] Exporting tables ............ CSV + LaTeX                   ✓
[5/5] Recording provenance ........ outputs/provenance/           ✓
─────────────────────────────────────────────────────
Done in 1.3s   →   examples/getting_started/outputs/
```

---

## Step 5 — Read the Regression Table

Open `examples/getting_started/outputs/tables/table_fe_investment.csv`.

```
                          (1)            (2)            (3)
                     Pooled OLS    Entity FE     Two-Way FE
─────────────────────────────────────────────────────────────
value                 0.116***      0.110***       0.119***
                     (0.006)       (0.014)        (0.015)

capital               0.231***      0.310***       0.361***
                     (0.025)       (0.050)        (0.060)

Firm FE                  No            Yes            Yes
Year FE                  No             No            Yes

N                        220           220            220
R² (within)                —          0.767          0.804
─────────────────────────────────────────────────────────────
Clustered SE by firm in parentheses. *** p<0.01
```

**How to read this table:**

Column (1) is the naive pooled OLS estimate. It treats all 220 observations
as independent — which they are not, since the same firms appear repeatedly.

Column (2) adds firm fixed effects. This controls for all stable differences
across firms (size, industry, management style). Notice that the `capital`
coefficient rises from 0.231 to 0.310 — the pooled estimate was biased
because larger firms have more capital *and* invest more.

Column (3) adds year fixed effects on top. This removes aggregate shocks
common to all firms in a given year (the Great Depression trough in the
late 1930s, wartime expansion). The R² within rises to 0.804.

**The economic interpretation:** A $1 million increase in firm market value
is associated with $0.110 million more investment in the same year, holding
firm characteristics constant. A $1 million larger capital stock is
associated with $0.310 million more investment — replacement and expansion
investment together.

> **The LaTeX version** (`table_fe_investment.tex`) is ready to paste
> directly into your paper. It uses the `booktabs` package and matches
> the style of the *American Economic Review*.

---

## Step 6 — What the Provenance Record Captures

Every EconFlow run writes a `run_metadata.json` to
`examples/getting_started/outputs/provenance/`. Open it:

```json
{
  "run_id": "a3f9...",
  "timestamp": "2026-06-25T14:03:11Z",
  "econflow_version": "0.1.0",
  "data_sha256": "e4c7...",
  "config_sha256": "91b2...",
  "models": ["pooled_ols", "entity_fe", "twoway_fe"],
  "outputs": {
    "table_fe_investment.csv": "sha256:...",
    "table_fe_investment.tex": "sha256:..."
  },
  "platform": "linux / Python 3.11.9"
}
```

Include `run_id` in your paper's appendix. Any reader with this repository
and run ID can reproduce your exact table.

---

## Next Steps

Now that you have completed the tutorial, you can:

**Adapt to your own data**
- Copy `examples/getting_started/config/` to a new folder
- Point `config.yaml` at your own CSV
- Change `entity_col`, `time_col`, `dependent`, and `regressors`
- Run the same command

**Add more specifications**
- Edit `models.yaml` to add IV estimation, GLS, or quantile regressions
- See `examples/ai_productivity_paper/config/models.yaml` for a
  production-grade example with 12 model specifications

**Explore diagnostics**
- EconFlow can run Hausman tests (FE vs. RE), Pesaran CD tests for
  cross-sectional dependence, and Arellano-Bond AR tests for dynamic panels
- See [ARCHITECTURE.md](../../ARCHITECTURE.md) for the full list of
  estimators and diagnostics

---

## Dataset Citation

> Grunfeld, Y. (1958). *The Determinants of Corporate Investment*.
> PhD dissertation, University of Chicago.
>
> The dataset used here is the version distributed with the
> `statsmodels` Python package (public domain).
