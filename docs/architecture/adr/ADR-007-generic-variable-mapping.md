# ADR-007: Generic Variable Mapping

**Status:** Accepted  
**Date:** 2026-06-28  
**Deciders:** Technical Steering Committee  
**Supersedes:** Early hardcoded column names from Sprint 1–2 implementation  
**Superseded by:** —

---

## Context

EconFlow was extracted from a study that analyzed AI adoption and total factor
productivity. The original pipeline assumed specific column names throughout its code:
`country` as the entity identifier, `year` as the time identifier, `log_tfp` as the
dependent variable, and a fixed list of regressors derived from the paper's econometric
specification.

These assumptions were encoded at three levels:
1. **Hard-coded string literals** in pipeline functions (`df["country"]`, `df["year"]`)
2. **Fixed fixture column names** in tests (`conftest.py` created dataframes with
   `country`, `year`, `log_tfp`)
3. **Implicit documentation** in architecture documents that described the pipeline
   in terms of the paper's variables

Extracting EconFlow required eliminating all three levels of assumption. A pipeline
that only works with a `country` column cannot run a study about industries, firms,
households, or counties. A pipeline that assumes `log_tfp` as the outcome cannot run
a labor economics study. Making EconFlow a general platform required a generic variable
mapping that allowed any column name to serve as the entity identifier, time identifier,
outcome, treatment, or control — specified by configuration, not hardcoded in code.

The design also required a naming convention for the generic columns that was consistent
across the entire codebase: the pipeline, the estimators, the diagnostics, the validators,
and the connectors all need to agree on what to call "the entity identifier column"
when passing data between themselves. Using the study-specific column name directly
(passing `"country"` through six layers of code) would re-introduce the paper-specific
assumption at a different level.

---

## Decision

We adopt **four canonical variable roles** that are mapped from study-specific column
names in configuration and then used as generic internal names throughout the pipeline:

| Role | Internal name | Configuration key |
|---|---|---|
| Entity identifier | `entity_col` | `config.variables.entity_col` |
| Time identifier | `time_col` | `config.variables.time_col` |
| Dependent variable | `dependent` | `config.variables.dependent` |
| Treatment variable | `treatment` | `config.variables.treatment` |
| Control variables | `controls` | `config.variables.controls` |

The internal names (`entity_col`, `time_col`, `dependent`, `treatment`, `controls`)
are the names used everywhere in EconFlow's internal code. They are passed as
configuration parameters to estimators, diagnostics, validators, and connectors.
The study-specific column names (`country`, `year`, `log_tfp`, etc.) appear only
in the configuration files and in the raw data files; they never appear in pipeline code.

The mapping is applied at the pipeline entry point. `run_from_config()` reads the
configuration, extracts the five role-to-name mappings, and passes them as explicit
parameters to every downstream function. No downstream function reads column names from
configuration directly; it receives them as arguments. This makes the variable mapping
fully explicit in every function call and eliminates any implicit dependency on
configuration being available in a particular scope.

**Connector output convention.** Every `AbstractConnector.download()` implementation
writes a CSV file using the internal canonical names as column headers: `entity_col`
and `time_col` map to `"entity"` and `"time"` in connector output, or to the names
specified by the connector's `entity_col` and `time_col` constructor parameters.
When a connector is instantiated for a specific study, its constructor parameters
specify the column naming convention of its output CSV, and the pipeline's variable
mapping connects those names to the canonical role names.

**Estimator interface convention.** `BaseEstimator.validate()` and `BaseEstimator.fit()`
both accept `entity_col: str` and `time_col: str` parameters explicitly. No estimator
may read column names from a module-level constant or a class attribute. The variable
names are always passed in; they are never assumed.

**Validator convention.** `DataValidationReport` accepts `entity_col` and `time_col`
as parameters to its structural checks (panel balance, entity count, time period range).
A validator that hardcodes `"country"` as the entity identifier cannot validate a
study that uses `"firm_id"`.

---

## Alternatives Considered

### Alternative 1: Rename All Datasets at Ingest

When a dataset is loaded into the pipeline, rename all columns to match internal
canonical names (`entity`, `time`, `outcome`, `treatment`). The pipeline works only
with these four names; original names are never used after the first transformation.

**Why not chosen:** Renaming all columns at ingest loses the original column names,
which are needed in output tables (a regression table must show `log_tfp`, not
`outcome`) and in validation error messages (a validator must report that `country` is
missing, not `entity`). Renaming would also prevent the pipeline from handling datasets
with multiple potential outcome variables, where the "active" outcome changes across
estimator specifications.

### Alternative 2: Column Name Configuration Object

Define a `ColumnMapping` object that is passed through the entire pipeline as a single
parameter, carrying all five role-to-name mappings. Every function accepts a
`ColumnMapping` parameter instead of individual `entity_col`, `time_col`, etc.

**Why not chosen:** A `ColumnMapping` object adds a level of indirection that makes
function signatures less readable. `fit(data, entity_col="country", time_col="year")`
is immediately clear about what the function needs. `fit(data, col_map=mapping)` is
not. The object pattern would also require every caller to understand the `ColumnMapping`
API, adding to the onboarding cost for plugin authors.

### Alternative 3: Convention Over Configuration

Define a convention: all EconFlow datasets must use `entity`, `time`, `outcome`, and
`treatment` as column names. Researchers must rename their columns before using EconFlow.

**Why not chosen:** Requiring researchers to rename their dataset columns is a
significant usability barrier and a reproducibility risk. A researcher who renames
`country` to `entity` in a preprocessing step has introduced an undocumented
transformation. If that transformation has a bug (wrong mapping, partial rename), the
error is invisible. The configuration mapping approach keeps the original column names
in the data and makes the mapping explicit and versionable.

### Alternative 4: pandas `rename()` Plus a Fixed Internal Schema

Apply `df.rename(columns={config.entity_col: "entity", config.time_col: "time", ...})`
at the pipeline entry point. All downstream code uses the fixed internal schema.
Output tables are produced using the original names (retrieved from configuration for
display purposes).

**Why not chosen:** This is closest to what was ultimately chosen, but with one
difference: renaming the columns means that any diagnostic or error message that
reports a column name must un-map the internal name back to the original. This creates
a mapping that must be maintained in two directions. Passing the original column names
through as parameters avoids the reverse-mapping problem entirely.

---

## Trade-offs

**Accepted costs:**

- Every function that operates on panel data must accept `entity_col` and `time_col`
  as explicit parameters. This adds two parameters to every estimator, diagnostic,
  validator, and connector method. For functions with many parameters, this adds
  verbosity. The verbosity is a feature: it makes the dependency on column names
  explicit rather than implicit.

- The variable mapping is specified in `config/config.yaml` and read by `load_config()`.
  A researcher who runs the pipeline programmatically (via the Python API, not the CLI)
  must explicitly pass `entity_col` and `time_col` to every function they call. There
  is no way to set these globally. This is intentional.

- Connectors must respect the `entity_col` and `time_col` parameters in their
  constructor to determine how to name the output CSV columns. A connector that
  ignores these parameters and always writes `country` as the entity column is a
  broken connector. Enforcement is by code review and by the integration test that
  verifies connector output column names.

**Realized benefits:**

- EconFlow can run any panel study without code changes. The same pipeline code that
  runs the AI & Productivity paper can run a labor economics study with firms as
  entities and employment as the outcome, by changing three lines in `config.yaml`.

- `DatasetMetadata` stores the entity column and time column names of every cached
  dataset. This makes it possible to verify at load time that the cached dataset's
  column names match the current configuration's variable mapping.

- Tests no longer require AI & Productivity-specific column names in fixtures. The
  `sample_panel` fixture in `conftest.py` uses the generic names `entity_id` and
  `period`, which can be passed as `entity_col="entity_id"` to any function under test.

---

## Consequences

**Immediate consequences:**

1. No pipeline module, estimator, diagnostic, validator, or connector may use any
   study-specific column name as a string literal. All column name references must
   come from parameters passed in from the pipeline layer.

2. `load_config()` must raise `ConfigurationError` with a clear message if any of
   the five required variable role mappings is absent from `config.yaml`. The pipeline
   must not start if these mappings are missing.

3. Connector output CSVs must use the `entity_col` and `time_col` names specified
   in the connector's constructor, not any hardcoded column name. The pipeline
   verifies this by comparing `DatasetMetadata.entity_col` against `config.variables.entity_col`.

4. The `examples/ai_productivity_paper/` example must explicitly set
   `entity_col: country`, `time_col: year`, `dependent: log_tfp` in its `config.yaml`.
   These names should not appear anywhere in EconFlow's source code.

**Architectural constraints imposed:**

- The canonical variable roles (`entity_col`, `time_col`, `dependent`, `treatment`,
  `controls`) are the complete and closed set for v1.0. Additional roles (e.g.,
  `weight_col` for weighted regression, `cluster_col` for clustered standard errors)
  may be added in future versions but must go through a schema revision process.

- The variable mapping is the responsibility of the configuration layer, not the
  pipeline layer. The pipeline passes roles to functions; it does not transform or
  validate column names. Validation of column name existence against actual dataset
  columns is the responsibility of `DataValidator.validate()`.

---

## Future Implications

**ADR-007-F1 (Under consideration):** Multiple outcome variables. Some studies estimate
the same model with several dependent variables (for robustness or heterogeneity
analysis). The current design supports one `dependent` per pipeline run. A future
extension would allow `models.yaml` to specify a list of dependent variables, producing
a separate estimation run for each.

**ADR-007-F2 (Under consideration):** Weight and cluster role mappings. Weighted
regression and clustered standard errors are common in panel econometrics. Adding
`weight_col` and `cluster_col` as additional canonical variable roles would make these
options configurable without each estimator defining its own parameter name.

**ADR-007-F3 (Planned):** Schema discovery integration. When `AbstractConnector.schema()`
is implemented (ADR-004-F1), the pipeline will be able to verify that the column names
specified in the variable mapping exist in the connector's declared schema before
downloading any data. This catches configuration errors earlier — at validation time
rather than at runtime.

---

## Cross References

- `src/econflow/core/config.py` — `VariablesConfig` model with the five role mappings
- `src/econflow/pipeline_generic.py` — entry point that reads and distributes role mappings
- `src/econflow/estimation/base.py` — `BaseEstimator.validate()` and `.fit()` signatures
- `src/econflow/ingestion/base.py` — `AbstractConnector` constructor parameters
- `src/econflow/ingestion/validation.py` — `DataValidator` parameter convention
- `examples/ai_productivity_paper/config/config.yaml` — reference variable mapping
- `docs/architecture/MILESTONE_v0.7.md` §1.3 — generic pipeline capability assessment
- `docs/roadmap/V1_RELEASE_CRITERIA.md` §1.4 — `load_config()` as blocking requirement
- ADR-002 — Configuration-First Design (variable mapping in configuration files)
- ADR-004 — Connector Framework (connector output column naming)
