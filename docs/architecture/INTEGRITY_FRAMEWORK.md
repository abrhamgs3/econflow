# Research Integrity & Reproducibility Framework

**Sprint 7 — EconFlow v0.1.x**

---

## Overview

The Integrity Framework provides automatic reproducibility certificates,
environment drift detection, research integrity checks, and journal-ready
replication package generation for any EconFlow project.

It is **generic across empirical projects** — no paper-specific assumptions,
fully YAML-driven, with a plugin architecture for integrity checks.

---

## Architecture

```
econflow/
└── integrity/
    ├── __init__.py          ← public API
    ├── fingerprint.py       ← EnvironmentFingerprint, DataFingerprint, ConfigFingerprint
    ├── certificate.py       ← ReproducibilityCertificate
    ├── drift.py             ← DriftItem, DriftReport, detect_drift()
    ├── package.py           ← ReplicationPackage
    └── checks/
        ├── __init__.py      ← public API + triggers plugin registration
        ├── base.py          ← BaseIntegrityCheck, IntegrityCheckResult
        ├── registry.py      ← @register_integrity_check, get_check, list_checks
        └── plugins/
            ├── __init__.py
            ├── coefficient_stability.py
            ├── sample_size.py
            └── pvalue_distribution.py
```

Three CLI commands are wired into `econflow`:

| Command              | Purpose                                   |
| -------------------- | ----------------------------------------- |
| `econflow certify`   | Capture environment + data fingerprints   |
| `econflow verify`    | Compare two certificates for drift        |
| `econflow package`   | Build a journal-ready replication bundle  |

---

## Core Concepts

### Fingerprints

Three lightweight dataclasses snapshot different reproducibility evidence:

**`EnvironmentFingerprint`** — captured via `EnvironmentFingerprint.capture()`:
- Git commit, branch, dirty flag, tags (from `provenance._git_info`)
- Python version and implementation
- OS / platform info (anonymised hostname)
- All tracked package versions
- EconFlow version

**`DataFingerprint`** — captured via `DataFingerprint.from_path(path)`:
- SHA-256 hash of the file
- File size and modification time
- Row count, column count, sorted column names (for CSV / Parquet)
- Format detection (`"csv"`, `"parquet"`, `"unknown"`)

**`ConfigFingerprint`** — captured via `ConfigFingerprint.from_path(path)`:
- SHA-256 of the YAML config file
- First 512 characters for quick visual inspection

All fingerprints re-use the hashing and provenance helpers from
`econflow.provenance` — no code duplication.

---

### ReproducibilityCertificate

A JSON-serialisable record of a complete pipeline run:

```python
cert = ReproducibilityCertificate.build(
    project_name="My Study",
    data_paths=["data/processed/panel.csv"],
    config_path="config/config.yaml",
    check_results=check_results,      # list[IntegrityCheckResult]
)
cert.save("outputs/certificate.json")
```

**Schema version**: `"1.0.0"` (semver — minor bumps add optional keys,
major bumps change or remove existing keys).

**`overall_status`** aggregation rules:
- `"fail"` if any check result is `"fail"`
- `"warn"` if any check result is `"warn"` (and none is `"fail"`)
- `"pass"` otherwise (including all `"skip"`)

---

### Drift Detection

`detect_drift(baseline, current)` compares two certificate dicts and returns
a `DriftReport` listing every detected change.

Comparison axes and severities:

| Axis                         | Severity |
| ---------------------------- | -------- |
| Git commit changed           | `warn`   |
| Working tree dirty           | `warn`   |
| Package version changed      | `warn`   |
| Package removed              | `fail`   |
| New package added            | `none`   |
| Data file SHA-256 changed    | `fail`   |
| Data row count changed       | `warn`   |
| Data file absent in current  | `warn`   |
| Config SHA-256 changed       | `warn`   |

`DriftReport.overall_status`:
- `"fail"` if any `DriftItem` has `severity == "fail"`
- `"warn"` if any `DriftItem` has `severity == "warn"` (and none is fail)
- `"pass"` otherwise

---

### Integrity Check Plugin System

Integrity checks follow the exact same pattern as diagnostic plugins:

```python
from econflow.integrity.checks.registry import register_integrity_check
from econflow.integrity.checks.base import BaseIntegrityCheck, IntegrityCheckResult

@register_integrity_check(
    "my_check",
    label="My Custom Check",
    notes="Checks something specific",
)
class MyCheck(BaseIntegrityCheck):
    check_id = "my_check"
    name = "My Custom Check"
    supported_estimators = ["*"]

    def run(self, result, **kwargs):
        # ... inspect result ...
        return self._pass("Everything looks good.")
```

**Built-in plugins**:

| Check ID                  | What it checks                                          |
| ------------------------- | ------------------------------------------------------- |
| `coefficient_stability`   | Max |coef| bounds; NaN/Inf coefficient detection        |
| `sample_size`             | `nobs` ≥ warn/fail thresholds                          |
| `pvalue_distribution`     | Identical p-values; all < 0.001; suspicious >90% sig   |

All thresholds are configurable via keyword arguments to `.run()`.

`IntegrityCheckResult` fields: `check_id`, `name`, `status` (`"pass"` /
`"warn"` / `"fail"` / `"skip"`), `message`, `extra`.

---

### ReplicationPackage

Builds a structured directory for journal submission:

```
replication_package/
    README.md           ← auto-generated replication instructions
    certificate.json    ← ReproducibilityCertificate
    environment.txt     ← pinned packages (pip install -r environment.txt)
    config/             ← copied config files
    scripts/            ← copied replication scripts
    manifest.json       ← machine-readable bundle index
```

```python
from econflow.integrity import ReplicationPackage, ReproducibilityCertificate

cert = ReproducibilityCertificate.load("outputs/certificate.json")

manifest = (
    ReplicationPackage("replication_package")
    .set_certificate(cert)
    .add_config(Path("config/config.yaml"))
    .add_script(Path("scripts/01_run.py"), label="Step 1: Run pipeline")
    .set_data_readme("Data available at https://example.com/data")
    .build()
)
```

---

## CLI Reference

### `econflow certify`

```bash
econflow certify \
    --project-name "Panel Growth Study" \
    --data data/processed/panel.csv \
    --config config/config.yaml \
    --output outputs/certificate.json
```

Options:
- `--project-name` / `-p` — human-readable project name
- `--data` / `-d` — dataset path(s) (repeat for multiple)
- `--config` / `-c` — config YAML path
- `--output` / `-o` — certificate destination (default: `outputs/certificate.json`)
- `--checks` / `--no-checks` — run integrity checks
- `--repo-root` — git repository root

### `econflow verify`

```bash
# Compare live environment against stored certificate
econflow verify --baseline outputs/certificate.json

# Compare two stored certificates
econflow verify \
    --baseline outputs/baseline_cert.json \
    --current  outputs/current_cert.json \
    --output   outputs/drift_report.json
```

Exit code: 0 for `pass`/`warn`, 1 for `fail`.

### `econflow package`

```bash
econflow package \
    --certificate outputs/certificate.json \
    --config config/config.yaml \
    --script scripts/01_download.py \
    --script scripts/02_run.py \
    --output-dir replication_package/
```

---

## Design Decisions

**Re-use provenance helpers**: `EnvironmentFingerprint.capture()` delegates to
`_git_info()`, `_python_info()`, `_platform_info()`, `_package_versions()` from
`econflow.provenance`. This avoids duplication and keeps the two subsystems
consistent.

**No paper-specific assumptions**: all paths (`data_paths`, `config_path`,
`output_dir`) are parameters. No hardcoded filenames.

**Plugin architecture**: `@register_integrity_check()` follows the same
auto-registration pattern as `@register_diagnostic()` and
`@register_renderer()`. Adding a new check requires only creating a class in
`integrity/checks/plugins/` and importing it in `plugins/__init__.py`.

**Atomic writes**: `ReproducibilityCertificate.save()` and `DriftReport.save()`
write to a `.tmp` file and use `os.fsync()` + `Path.replace()` to prevent
partial writes.

**Semver schema versions**: `certificate.json` carries `schema_version: "1.0.0"`.
Minor bumps add optional keys; major bumps require a migration path.

**Thresholds are kwargs**: all three built-in plugins accept threshold
overrides as keyword arguments to `.run()`, making them testable and
project-configurable without subclassing.

---

## Exception Hierarchy

```
EconFlowCoreError
└── IntegrityError           ← base for all integrity errors
    └── CertificateError     ← raised by ReproducibilityCertificate.save/load
```

---

## Testing

| File                                        | Scope                            | Tests |
| ------------------------------------------- | -------------------------------- | ----- |
| `tests/unit/test_integrity_fingerprint.py`  | Fingerprint classes              | 25    |
| `tests/unit/test_integrity_certificate.py`  | Certificate build/serde/persist  | 18    |
| `tests/unit/test_integrity_drift.py`        | Drift detection                  | 15    |
| `tests/unit/test_integrity_checks.py`       | Registry + 3 built-in plugins    | 22    |
| `tests/integration/test_integrity_pipeline.py` | Full E2E pipeline             | 10    |

Run with:

```bash
pytest tests/unit/test_integrity_*.py tests/integration/test_integrity_pipeline.py -v
```
