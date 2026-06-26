# Getting Started with EconFlow

**Time:** ~10 minutes  
**Dataset:** Grunfeld (1935–1954) — 11 US firms, 20 years, 220 observations

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

## The Problem

In 1958, Yehuda Grunfeld asked a simple question: what determines how much
a firm invests? He proposed that investment should depend on two things — the
firm's market value (a forward-looking measure of expected profitability) and
its existing capital stock (which must be maintained and expanded).

The intuitive model is:

```
invest_it = β₁ value_it + β₂ capital_it + ε_it
```

where `i` indexes firms and `t` indexes years. Estimate this with OLS and
you get column (1) of the table you will produce in a few minutes.

**But OLS is wrong here.** General Motors and a small steel firm are not
comparable observations. GM has more capital, higher market value, *and*
invests more — not because value causes investment in some pure causal sense,
but because GM is GM. Its size, management culture, access to credit, and
industry position are all bundled together and correlated with every variable
in the regression. This is the classic omitted-variable problem.

Fixed effects solve it by asking a narrower question: **within a single firm,
in years when its market value is higher than usual, does it invest more than
usual?** We compare GM to itself over time, not GM to Arrow Steel. By doing
so, we control for everything that is stable about a firm — size, industry,
culture — without having to measure any of it.

The within estimator is equivalent to demeaning by entity:

```
(invest_it − invest̄_i) = β₁(value_it − valuē_i) + β₂(capital_it − capital̄_i) + ε_it
```

The firm mean is subtracted from every observation, removing all variation
between firms and leaving only variation within them. Any time-invariant
omitted variable disappears from the regression — it is in the mean, and
the mean is gone.

---

## The Data

The dataset is included in this repository at `data/grunfeld.csv`. It
covers 11 large US corporations from 1935 to 1954.

| Column | Description |
|--------|-------------|
| `firm` | Firm name |
| `year` | Year (1935–1954) |
| `invest` | Gross investment (millions USD) |
| `value` | Firm market value (millions USD) |
| `capital` | Capital stock at start of year (millions USD) |

The panel is **balanced**: every firm appears in every year, giving
220 observations. Before running any model, verify this:

```python
import pandas as pd
df = pd.read_csv("examples/getting_started/data/grunfeld.csv")
print(df.shape)                      # (220, 5)
print(df.isnull().sum().max())       # 0 — no missing values
print(df.groupby("firm").size())     # 20 per firm
```

A balanced panel is not a requirement for EconFlow — unbalanced panels work
too — but it makes interpreting R² within cleaner.

---

## Step 1 — Install and Verify

```bash
pip install econflow
econflow doctor
```

```
EconFlow v0.1.0 — environment check
  Python         3.10+       ✓
  pandas         2.x         ✓
  statsmodels    0.14+       ✓
  linearmodels   5.3+        ✓
Environment OK
```

---

## Step 2 — Run Three Specifications

The configuration files in `config/` are already set up. Run:

```bash
econflow run \
  --config  examples/getting_started/config/config.yaml \
  --models  examples/getting_started/config/models.yaml \
  --outputs examples/getting_started/config/outputs.yaml
```

EconFlow loads the data, validates the panel structure, estimates three
models in sequence, and writes results to `outputs/tables/`:

```
[1/5] Loading data ................ 220 obs, 11 firms, 20 years  ✓
[2/5] Validating panel ............ balanced, no missing values   ✓
[3/5] Running models
      pooled_ols   OLS (no FE)                                   ✓
      entity_fe    FE — entity effects, clustered SE             ✓
      twoway_fe    FE — entity + time effects, clustered SE      ✓
[4/5] Exporting tables ............ CSV + LaTeX                   ✓
[5/5] Recording provenance ........ outputs/provenance/           ✓
Done in 1.3s
```

The three models are run intentionally in order: pooled OLS first to show
the biased baseline, entity FE to fix firm heterogeneity, two-way FE to
additionally absorb aggregate time shocks.

---

## Step 3 — Read the Table

Open `outputs/tables/table_fe_investment.csv`:

```
                          (1)            (2)            (3)
                     Pooled OLS    Entity FE     Two-Way FE
─────────────────────────────────────────────────────────────
value                 0.115***      0.110***       0.117***
                     (0.006)       (0.014)        (0.011)

capital               0.228***      0.310***       0.351***
                     (0.024)       (0.050)        (0.047)

Firm FE                  No            Yes            Yes
Year FE                  No             No            Yes

N                        220           220            220
R² (within)                —          0.767          0.757
─────────────────────────────────────────────────────────────
Pooled OLS: heteroskedasticity-robust SE. FE: clustered SE by firm. *** p<0.01
```

**Reading column (1).** Pooled OLS treats all 220 observations as if they
came from 220 independent firms. They did not. The estimates conflate
within-firm variation (what we want) with between-firm variation (which
reflects the fact that large firms have large everything). The standard
errors here are heteroskedasticity-robust but do not account for the
serial correlation in investment within a firm over time.

**Reading column (2).** Adding firm fixed effects forces the estimator to
work only within firms over time. The value coefficient falls slightly
(0.115 → 0.110), but the capital coefficient rises substantially
(0.228 → 0.310). This is the omitted-variable bias correcting itself.
In pooled OLS, the capital coefficient was absorbing cross-sectional
differences in firm size. Once we control for firm identity, the coefficient
on capital measures something closer to the marginal propensity to invest
out of an increase in the capital stock — replacement and expansion demand.

The standard errors widen (capital: 0.024 → 0.050). This is not a problem;
it is honesty. The effective sample size for within estimation is smaller,
and clustering by firm accounts for the serial correlation in investment
behaviour within a firm over time.

**Reading column (3).** Year fixed effects absorb aggregate shocks that
affect all firms simultaneously — the sharp drop in investment during the
late 1930s Depression trough, the surge during wartime. Once removed, the
remaining within-firm, within-year variation drives a further shift in the
capital coefficient (0.310 → 0.351). R² within holds at 0.757.

**The core result.** A $1 million increase in firm market value is associated
with roughly $0.110 million in additional investment within that firm in the
same year. A $1 million increase in the capital stock — which a firm must
maintain and expand — is associated with roughly $0.310 million in additional
investment. Both relationships are tight and stable across specifications,
which supports the robustness of the finding.

---

## Step 4 — Export to Your Paper

The LaTeX table at `outputs/tables/table_fe_investment.tex` uses `booktabs`
formatting and is ready to paste directly into a manuscript. No reformatting
required.

Every run also writes a provenance record to `outputs/provenance/run_metadata.json`
containing the SHA-256 hash of the input data, the software version, and a
unique run identifier. Include the run ID in your paper's data appendix so
that any reader can reproduce the exact table from this repository.

---

## Adapting to Your Own Data

EconFlow is configured by three YAML files: `config.yaml` (data location and
column names), `models.yaml` (model specifications), and `outputs.yaml`
(output formats and filenames). To run a new study:

1. Copy `examples/getting_started/config/` to `examples/<your_project>/config/`
2. Edit `config.yaml`: point `path` at your CSV and set `entity_col`,
   `time_col`, `dependent`, and `regressors` to match your column names
3. Run the same command with the new config path

For a production-grade example with 12 model specifications, multiple data
sources, and a full replication package, see
[`examples/ai_productivity_paper/`](../ai_productivity_paper/).

---

## Dataset Citation

> Grunfeld, Y. (1958). *The Determinants of Corporate Investment*.
> PhD dissertation, University of Chicago.
>
> Distributed with the `statsmodels` Python package (public domain).
