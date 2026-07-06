# Configuration Validation

**Version:** 1.0  
**Stability:** Stable  
**Date:** 2026-07-06  
**Owner:** Core Team  

---

## The Guarantee

EconFlow **never** silently accepts an invalid configuration.

The pipeline cannot be entered without passing all four validation stages.
`econflow run` calls `ConfigValidator.validate_strict()` before touching any
output file, enforcing an unbreakable `load → validate → execute → report`
flow.

If the configuration is invalid, the run aborts with a structured error
report listing every problem and its fix.  You will never see:

```
KeyError: 'ln_capital'
AttributeError: 'NoneType' object has no attribute 'fit'
ValueError: shapes (12, 3) and (12, 4) not aligned
```

You will see:

```
✘ Configuration validation failed (1 error).

  [cross_file] models.yaml [models → entity_fe → regressors]:
      Model 'entity_fe' uses variable(s) ['ln_capital'] that are not
      declared in config.yaml variables.regressors.
      Fix: Add ['ln_capital'] to config.yaml variables.regressors,
           or correct the typo in models.yaml.
```

---

## Validation Flow

```
config.yaml
models.yaml      ──► Stage 1: YAML syntax
outputs.yaml            │
                        ▼
                  Stage 2: Pydantic schema
                  (unknown keys, wrong types,
                   missing required fields,
                   incorrect nesting)
                        │
                        ▼
                  Stage 3: Semantic validation
                  (ConfigLinter — L-01 through L-13)
                  (value relationships within a file)
                        │
                        ▼
                  Stage 4: Cross-file consistency
                  (X-01: output model refs exist)
                  (X-02: model regressors in config)
                        │
                  ┌─────▼──────────────────────────────┐
                  │  errors?  → abort; print report    │
                  │  ok?      → execute pipeline       │
                  └────────────────────────────────────┘
                        │ (optional, econflow validate --data)
                        ▼
                  Stage 5: Data file
                  (D-01: entity/time columns present)
                  (D-02: analysis variables present)
                  (D-03: no duplicate panel keys)
```

Each stage runs to completion even when the previous stage found errors.
This means a single `econflow validate` pass surfaces **all** problems, not
just the first one.

---

## Stage Reference

### Stage 1 — YAML Syntax

Triggered by: `yaml.YAMLError`

| Condition | Severity |
|-----------|----------|
| File not found | error |
| Malformed YAML (bad indentation, unquoted special chars) | error |
| Root is a list, not a mapping | error |

**Example error:**

```
config.yaml [line 4, column 3]:
  YAML syntax error: while scanning a quoted scalar … found unexpected end of stream
  Fix: Common causes: wrong indentation, missing colon after a key,
       unquoted special characters (: { } [ ] # & * ?).
```

**Common trigger — missing quote:**

```yaml
# Bad — colon inside unquoted string
project:
  name: My Project: Phase 1     # ← ":" in value needs quoting

# Good
project:
  name: "My Project: Phase 1"
```

---

### Stage 2 — Pydantic Schema

All three top-level models (`ProjectConfig`, `ModelsConfig`, `OutputsConfig`)
use `model_config = ConfigDict(extra="forbid")`.  Every unknown key at the
top level — or in any `extra="forbid"` sub-model — is an immediate error.

| Condition | Severity |
|-----------|----------|
| Unknown key at any `extra="forbid"` level | error |
| Missing required field | error |
| Wrong type (list for bool, string for int, …) | error |
| Incorrect nesting (key in wrong sub-block) | error |
| `se_type` not one of `robust \| clustered \| classical` | error |
| Model `id` fails `^[A-Za-z][A-Za-z0-9_-]*$` pattern | error |
| Duplicate model IDs | error |
| `models` list is empty | error |

**Example: unknown key**

```yaml
# Bad — "frequency" is not a valid key in config.yaml
data:
  path: data/panel.csv
  entity_col: country
  time_col: year
  frequency: annual        # ← unknown key → schema error

# Fix: remove 'frequency' or move it to a project note field
```

**Fix hint:** `Unknown key 'frequency' in config.yaml. Remove it or run
'econflow docs config' for the full schema.`

**Example: wrong nesting**

```yaml
# Bad — sample: belongs at top level, not inside data:
data:
  path: data/panel.csv
  entity_col: country
  time_col: year
  sample:                  # ← extra key in data block
    start_year: 2000
    end_year: 2020

# Good
data:
  path: data/panel.csv
  entity_col: country
  time_col: year

sample:
  start_year: 2000
  end_year: 2020
```

---

### Stage 3 — Semantic Validation

The `ConfigLinter` runs rules that check *relationships between values*
within a single file.  Pydantic handles field existence and types; the
linter handles logical consistency.

| Code | Severity | Description |
|------|----------|-------------|
| L-01 | error    | `variables.dependent` also in `variables.regressors` |
| L-02 | error    | Duplicate entries in `variables.regressors` |
| L-03 | error    | `sample.start_year ≥ sample.end_year` |
| L-04 | warning  | Unknown estimator string (typo), with fuzzy-match suggestion |
| L-04b | error   | Stub estimator (`gmm`, `quantile`) — registered but not implemented |
| L-05 | warning  | Model regressors not declared in `variables.regressors` |
| L-06 | warning  | `outputs.base_dir` is an absolute path (non-portable) |
| L-07 | warning  | `data.path` has unsupported extension |
| L-08 | warning  | `project.version` is not valid semver |
| L-09 | info     | Model `dependent` differs from `variables.dependent` |
| L-10 | info     | Model `label` is empty (falls back to `id` in output) |
| L-11 | error    | IV estimator with no instruments defined |
| L-12 | warning  | TWFE estimator but `entity_effects` and `time_effects` both False |
| L-13 | warning  | `outputs.tables.formats` contains unknown renderer ID |

**L-01 example:**

```yaml
# Bad
variables:
  dependent: "ln_gdp"
  regressors:
    - "ln_gdp"     # ← same as dependent → L-01 error
    - "ln_capital"

# Fix: remove 'ln_gdp' from regressors
```

**L-04b example:**

```yaml
# Bad — 'gmm' is registered but raises NotImplementedError
models:
  - id: "gmm_baseline"
    estimator: "gmm"    # ← L-04b error

# Fix: use ols, fe, twfe, re, fd, or iv
```

**L-11 example:**

```yaml
# Bad — IV requires excluded instruments
models:
  - id: "iv_dist"
    estimator: "iv"
    # No instruments defined → L-11 error

# Fix: add instruments to config.yaml
variables:
  instruments:
    - "distance_to_coast"
```

**L-12 example:**

```yaml
# Bad — TWFE without effects flags does nothing
models:
  - id: "twfe"
    estimator: "twfe"
    entity_effects: false   # ← L-12 warning
    time_effects:  false

# Fix
    entity_effects: true
    time_effects:  true
```

---

### Stage 4 — Cross-File Consistency

Cross-file checks enforce that references between the three YAML files
resolve correctly.

| Code | Severity | Description |
|------|----------|-------------|
| X-01 | error    | Model ID referenced in `outputs.yaml` not in `models.yaml` |
| X-02 | error    | Model uses regressor not declared in `config.yaml variables.regressors` |

**X-01 example:**

```yaml
# outputs.yaml
outputs:
  tables:
    comparison_table:
      models:
        - pooled_ols
        - entity_fe
        - twfe_robust     # ← X-01 error: 'twfe_robust' not in models.yaml
```

**X-02 example:**

```yaml
# config.yaml
variables:
  regressors: [treatment, covariate_1]

# models.yaml
models:
  - id: "robust_check"
    regressors:
      - treatment
      - covariate_1
      - ln_capital      # ← X-02 error: not in config.yaml regressors
```

---

### Stage 5 — Data File (optional)

Run with `econflow validate --data` or automatically during `econflow run`.

| Code | Severity | Description |
|------|----------|-------------|
| D-01 | error    | `entity_col` or `time_col` missing from CSV |
| D-02 | error    | Analysis variable (dependent, regressor, instrument) not in CSV |
| D-03 | warning  | Duplicate `(entity_col, time_col)` panel keys |

If the data file does not exist yet, a **warning** (not error) is emitted
so that `validate_strict()` can succeed before data is generated.

---

## Programmatic API

### Non-raising validation

```python
from econflow.config.validator import ConfigValidator, ValidationResult

validator = ConfigValidator()
result = validator.validate(
    config_path="config/config.yaml",
    models_path="config/models.yaml",
    outputs_path="config/outputs.yaml",
    check_data=True,             # optional Stage 5
)

print(f"ok: {result.ok}")
print(f"errors: {len(result.errors)}, warnings: {len(result.warnings)}")

for issue in result.errors:
    print(f"[{issue.stage}] {issue.source} {issue.location}")
    print(f"  {issue.message}")
    if issue.fix:
        print(f"  Fix: {issue.fix}")

# Filter by stage
schema_errors = result.by_stage("schema")
cross_issues  = result.by_stage("cross_file")

# Filter by source file
config_issues = result.by_source("config.yaml")
```

### Raising validation (pipeline use)

```python
from econflow.config.validator import ConfigValidator
from econflow.core.exceptions import ConfigValidationError

validator = ConfigValidator()
try:
    project_cfg, models_cfg, outputs_cfg = validator.validate_strict(
        config_path="config/config.yaml",
        models_path="config/models.yaml",
        outputs_path="config/outputs.yaml",
        check_data=True,
    )
    # All three Pydantic objects are ready to use
    print(project_cfg.project.name)
    print([m.id for m in models_cfg.models])
except ConfigValidationError as exc:
    print(f"{exc.error_count} error(s) found:")
    for issue in exc.errors:
        print(f"  {issue}")
    raise SystemExit(1)
```

### Using the linter directly

```python
from econflow.config.linter import ConfigLinter
from econflow.config.models import ProjectConfig, ModelsConfig, OutputsConfig

project_cfg = ProjectConfig.model_validate(raw_config_dict)
models_cfg  = ModelsConfig.model_validate(raw_models_dict)
outputs_cfg = OutputsConfig.model_validate(raw_outputs_dict)

linter = ConfigLinter()
issues = linter.lint(project_cfg, models_cfg, outputs_cfg)
for issue in issues:
    print(issue.code, issue.severity, issue.message)
```

---

## ValidationIssue Fields

Every issue returned by `ConfigValidator.validate()` is a `ValidationIssue`
dataclass with the following fields:

| Field | Type | Description |
|-------|------|-------------|
| `stage` | `str` | `yaml_syntax` \| `schema` \| `semantic` \| `cross_file` \| `data` |
| `severity` | `str` | `error` \| `warning` \| `info` |
| `source` | `str` | Which file (`config.yaml`, `models.yaml`, `outputs.yaml`, `data file`) |
| `location` | `str` | Key path inside the file (`variables → regressors`) |
| `message` | `str` | Plain-English problem description |
| `fix` | `str` | Actionable remedy instruction |
| `code` | `str` | Rule code (`L-01`, `X-02`, `D-03`, …); empty for YAML/schema errors |

---

## CLI Usage

```bash
# Validate all three files in a directory
econflow validate config/

# Validate also checking the data file
econflow validate --data config/

# Validate with explicit file paths
econflow validate \
  --config config/config.yaml \
  --models config/models.yaml \
  --outputs config/outputs.yaml

# Verbose: show passing stages too
econflow validate --verbose config/
```

Exit codes:
- `0` — all checks passed (warnings are printed but do not block)
- `1` — one or more errors found

---

## CLI Flow Enforcement

`econflow run` enforces the strict validation contract:

```
econflow run \
  --config config/config.yaml \
  --models config/models.yaml \
  --outputs config/outputs.yaml
```

Internal flow:
```
1. load_yaml_safe(config)  → raw dict
2. ConfigValidator.validate_strict(...)
     Stage 1 — YAML syntax
     Stage 2 — Schema
     Stage 3 — Semantic
     Stage 4 — Cross-file
     Stage 5 — Data (check_data=True)
   → raises ConfigValidationError if any errors
3. run_from_config(...)    → pipeline execution
4. render outputs
```

**There is no path from an invalid configuration to pipeline execution.**

---

## Migration Notes

### Upgrading from pre-1.0

If you are upgrading from an earlier version of EconFlow, you may encounter
validation errors on configs that previously ran without complaint.  This is
intentional — earlier versions allowed invalid configs to pass silently and
crash deep in the pipeline.

**Most common migration issues:**

| Error | Old behaviour | Fix |
|-------|---------------|-----|
| `X-02: model uses undeclared regressor` | KeyError at runtime | Add the regressor to `config.yaml variables.regressors` |
| `L-04b: gmm/quantile is a stub` | NotImplementedError at runtime | Change to `fe` or another implemented estimator |
| `schema: extra inputs not permitted` | Extra key silently ignored | Remove the unknown key from the YAML file |
| `L-01: dependent in regressors` | Collinear regression, silent | Remove dependent from `variables.regressors` |
| `X-01: model ref not in models.yaml` | Empty output tables | Fix the model ID in `outputs.yaml` |

### Suppressing specific warnings

Warnings (not errors) do not block execution.  To suppress a warning
intentionally, document it in your project's `NOTES.md`.  There is no
`# noqa`-style suppression mechanism — warnings exist to inform, not to
block.

### Strict mode and `extra="allow"` on ModelSpec

`ModelSpec` uses `extra="allow"` intentionally so that estimator-specific
kwargs (e.g. `cov_type`, `bandwidth`) can be passed through to the
underlying estimation library.  These extra keys are **not** validated by
EconFlow — they are forwarded verbatim to the estimator's `fit()` call.

---

## Adding Custom Validation Rules

Custom rules can be added by subclassing `ConfigLinter`:

```python
from econflow.config.linter import ConfigLinter, LintIssue

class MyLinter(ConfigLinter):
    def _lint_models(self, cfg, raw, project_cfg, raw_config):
        issues = super()._lint_models(cfg, raw, project_cfg, raw_config)
        # Add custom rule: all models must have a cluster column
        if cfg is not None:
            for m in cfg.models:
                if not m.cluster:
                    issues.append(LintIssue(
                        code="MY-01",
                        severity="warning",
                        message=f"Model '{m.id}' has no cluster column.",
                        fix="Set cluster: 'entity' for cluster-robust SEs.",
                        location=f"models.yaml: model '{m.id}'",
                    ))
        return issues

# Use with ConfigValidator
from econflow.config.validator import ConfigValidator, _stage_semantic
```

For full custom validation pipelines, subclass `ConfigValidator` and
override individual `_stage_*` functions.

---

## Architecture Notes

- `econflow.config.validator` is the **only** import needed for validation.
  All other modules (`linter`, `models`) are implementation details.
- `ConfigValidator` is stateless and thread-safe.  A single instance can
  validate multiple projects concurrently.
- All four stages run to completion before returning — no fail-fast behaviour.
  This ensures users see all errors in one pass.
- `validate_strict()` is the public contract consumed by `cli.py run`.  Its
  signature is stable and guaranteed not to change in v1.x.
- `ConfigValidationError` inherits from `ConfigurationError` → `EconFlowCoreError`
  → `EconFlowError`, so a single `except EconFlowError` at the top of the
  pipeline captures all configuration failures.
