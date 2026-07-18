# EconFlow Release Quality Gate

**Command:** `econflow release-check`
**Location:** `src/econflow/commands/release_check.py`

The Release Quality Gate is a single command that must pass before any release
is tagged or published.  It runs nine structured checks and exits with code 1
if any check marked **BLOCKER** fails.

---

## Quick start

```bash
# Full gate (may take 2–5 minutes)
econflow release-check

# Fast pre-flight (skips build, integration tests, replication)
econflow release-check --quick

# Save a report
econflow release-check \
    --output docs/release/gate_report.md \
    --json docs/release/gate_report.json
```

---

## Check catalogue

| ID | Name | Severity | Skipped by --quick | Description |
|---|---|---|---|---|
| QG-01 | package_build | BLOCKER | ✓ | Wheel builds from source |
| QG-02 | package_import | BLOCKER | – | All public sub-packages import cleanly |
| QG-03 | cli_smoke | BLOCKER | – | `--version` and `doctor` both pass |
| QG-04 | schema_validation | BLOCKER | – | ConfigValidator passes on `blind_replication` example |
| QG-05 | plugin_registry | BLOCKER | – | All registries meet minimum thresholds |
| QG-06 | integration_tests | BLOCKER | ✓ | `pytest tests/integration/` exits 0 |
| QG-07 | blind_replication | BLOCKER | ✓ | `econflow reproduce examples/blind_replication/` |
| QG-08 | doc_api_examples | BLOCKER | – | Documented import patterns work in-process |
| QG-09 | api_consistency | BLOCKER | – | Every `__all__` entry is importable |

All nine checks are BLOCKER severity.  A single failure blocks the release.

---

## Check details

### QG-01 — Package build

**What it does:** Calls `python -m build --wheel --no-isolation` in a temporary
directory.  Verifies the build exits 0 and produces at least one `.whl` file.

**Blocker when:** The build fails (bad `pyproject.toml`, missing `hatchling`,
`src/` layout error, import cycle discovered during build).

**Fix:** `pip install build` if the `build` module is missing.  Otherwise
examine `python -m build --wheel -v` output for the root cause.

**Skipped by `--quick`:** Yes (slow — typically 5–20 s).

---

### QG-02 — Package imports

**What it does:** Calls `importlib.import_module()` in-process for each public
sub-package:

- `econflow`
- `econflow.estimation`
- `econflow.diagnostics`
- `econflow.outputs`
- `econflow.ingestion`
- `econflow.integrity`
- `econflow.replication`
- `econflow.config`
- `econflow.commands`

**Blocker when:** Any package raises `ImportError` or `ModuleNotFoundError`.

**Fix:** Run `python -c "import econflow.<package>"` to isolate which package
fails and read the traceback.  Common causes: missing `__init__.py`, bad
relative import, circular import.

---

### QG-03 — CLI smoke test

**What it does:** Executes two subprocesses:

1. `econflow --version` — verifies exit 0 and that `__version__` appears in stdout.
2. `econflow doctor` — verifies exit 0 (all required checks pass).

**Blocker when:** Either command exits non-zero, or the version string is absent
from `--version` output.

**Fix:** Run `econflow doctor` manually.  If the entry point is missing, check
`[project.scripts]` in `pyproject.toml` and reinstall: `pip install -e .`.

---

### QG-04 — Config schema validation

**What it does:** Runs `ConfigValidator.validate()` on the three YAML files
in `examples/blind_replication/config/` without network access (`check_data=False`).

Passes if `result.issues` contains zero entries with `severity == "error"`.
Degrades to WARN if there are warnings but no errors.

**Blocker when:** Any validation error is found (schema violation, missing
required field, semantic rule failure).

**Fix:** Run `econflow validate examples/blind_replication/config/` for the
full annotated report.  The most common cause is a schema change not reflected
in the example YAML.

---

### QG-05 — Plugin registry integrity

**What it does:** Queries each registry and compares the returned count against
a minimum threshold:

| Registry | Minimum | Query |
|---|---|---|
| estimators | 6 | `list_estimators()` |
| renderers | 5 | `list_renderers()` |
| connectors | 4 | `list_connectors()` |
| diagnostics | 4 | `list_diagnostics()` |
| integrity_checks | 2 | `list_checks()` |

**Blocker when:** Any registry returns fewer items than the minimum, or any
registry call raises an exception.

**Fix:** Check that all `@register_*` decorator calls are executed at import
time.  Verify that the relevant `connectors/__init__.py` (or similar) imports
all plugins.

---

### QG-06 — Integration tests

**What it does:** Runs `pytest tests/integration/ -q --tb=short --timeout=120 -x`
in a subprocess.  Passes if exit code is 0.

**Blocker when:** Any test fails or the directory does not exist.

**Fix:** Run `pytest tests/integration/ -v --tb=long` to see full failure
details.

**Skipped by `--quick`:** Yes (slow — depends on test count, typically 30–120 s).

---

### QG-07 — Blind replication

**What it does:** Runs `econflow reproduce examples/blind_replication/ --output-dir <tmp> --no-compare`
in a subprocess with a 300 s timeout.  Passes if exit code is 0.

The `--no-compare` flag skips the output comparison step so the check
validates pipeline execution only (not numeric reproducibility against
`original_outputs/`).  Numeric comparison is the job of QG-06 integration
tests.

**Blocker when:** The pipeline fails, configuration is invalid, or the
subprocess times out.

**Fix:** Run `econflow reproduce examples/blind_replication/` manually and
examine the output.

**Skipped by `--quick`:** Yes (slow — pipeline execution, typically 20–60 s).

---

### QG-08 — Documentation API examples

**What it does:** Executes every key import pattern documented in
`docs/sdk/PLUGIN_SDK.md` and `docs/API_STABILITY.md` in-process:

- `from econflow.estimation import BaseEstimator, list_estimators, get_estimator`
- `from econflow.estimation import EstimationResult, register_estimator`
- `from econflow.outputs import BaseRenderer, FigureBuilder, ReportTable, ReportFigure`
- `from econflow.outputs import get_renderer, list_renderers, register_renderer`
- `from econflow.ingestion import AbstractConnector, get_connector, list_connectors`
- `from econflow.diagnostics import BaseDiagnostic, list_diagnostics, get_diagnostic`
- `from econflow.integrity import BaseIntegrityCheck, list_checks`
- `from econflow.config.validator import ConfigValidator`

**Blocker when:** Any import raises `ImportError`.

**Fix:** The failing import name is reported.  Either add it to the relevant
`__init__.py` or update the documentation to match the actual API.

---

### QG-09 — API surface consistency

**What it does:** For each public package, reads `__all__` and verifies that
every name listed there is present as an attribute on the module
(`hasattr(module, name)`).  A name in `__all__` that is not importable is a
"phantom export" — the documentation would promise it but `from pkg import name`
would raise `ImportError`.

Packages checked: `econflow`, `econflow.estimation`, `econflow.diagnostics`,
`econflow.outputs`, `econflow.ingestion`, `econflow.integrity`.

Degrades to WARN if a package has no `__all__` at all.

**Blocker when:** Any package contains phantom exports (names in `__all__` that
are not attributes of the module).

**Fix:** Either add the missing symbol to the package's `__init__.py`, or
remove it from `__all__`.

---

## Exit codes

| Code | Meaning |
|---|---|
| 0 | All checks passed (warnings allowed) |
| 1 | One or more BLOCKER checks failed |

---

## Report formats

### Markdown (`--output PATH`)

Human-readable report containing a results table, details for each failed
check, and a summary.  Suitable for attaching to a GitHub Release or PR.

### JSON (`--json PATH`)

Machine-readable report for CI integration:

```json
{
  "version": "0.1.0",
  "timestamp": "2026-07-07T00:00:00+00:00",
  "elapsed_s": 45.2,
  "release_blocked": false,
  "summary": {
    "passed": 9,
    "warned": 0,
    "failed": 0,
    "skipped": 0,
    "blockers": 0
  },
  "checks": [
    {
      "id": "QG-01",
      "name": "package_build",
      "label": "Package build (wheel)",
      "status": "pass",
      "severity": "blocker",
      "detail": "Built econflow-0.1.0-py3-none-any.whl",
      "fix": "",
      "duration_ms": 12400.0,
      "sub_results": []
    }
  ]
}
```

---

## CI integration

Add to `.github/workflows/ci.yml`:

```yaml
- name: Release quality gate
  run: econflow release-check --quick
```

For full pre-release validation (e.g. on `release/*` branches):

```yaml
- name: Release quality gate (full)
  run: |
    econflow release-check \
      --output docs/release/gate_report.md \
      --json   docs/release/gate_report.json
```

---

## Adding a new check

1. Implement `check_<name>() -> CheckResult` in `release_check.py`.
2. Assign the next available `QG-NN` ID.
3. Register it in the `ALL_CHECKS` list (order = display order).
4. Add it to `SLOW_CHECKS` if it typically takes more than 10 seconds.
5. Document it in this file.
6. Add a unit test in `tests/unit/test_release_check.py`.

---

## Severity policy

All current checks are BLOCKER.  The WARN severity is reserved for checks
where the underlying condition degrades quality but does not necessarily
prevent a release (e.g., optional dependencies missing, `__all__` absent but
exports still work).  A WARN check that fails sets status to `"warn"` and
never triggers a non-zero exit code.
