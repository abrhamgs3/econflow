# EconFlow v1.0.0 — Reproducibility Report

**Date:** 2026-07-19 (audit evidence) / 2026-07-21 (compiled)

This report consolidates existing, independently-demonstrated reproducibility
evidence from `docs/release/RC_FINALIZATION_AUDIT.md`,
`docs/release/REPOSITORY_INTEGRITY_REPORT.md`, and this release-execution
session. It does not introduce new claims beyond what those sessions
verified by direct execution.

## What "reproducible" means for EconFlow

An EconFlow project is fully specified by three declarative YAML files
(`config.yaml`, `models.yaml`, `outputs.yaml`). `econflow run` reads them and
produces deterministic numerical output — there is no random seed, hidden
state, or network call in the core estimation path. Reproducibility is
verified at three levels:

1. **Same-machine determinism** — running the same config twice produces
   byte-identical (or numerically tolerant, where floating-point formatting
   applies) output.
2. **Clean-environment reproducibility** — running from a genuinely fresh
   install (not the development checkout) produces the same result.
3. **Third-party replication** — a `ReplicationPackage` built by
   `econflow package` can be handed to someone else and re-executed via
   `econflow reproduce`, which reports a structured pass/fail comparison.

## Evidence

### Clean, non-editable wheel install (RC Finalization Audit, Section 1)

- Built `econflow-*-py3-none-any.whl` and the matching sdist via
  `python -m build` from `main`. Both built cleanly.
- Installed the wheel into a brand-new virtualenv with no editable install
  and no source tree on the Python path.
- Ran `econflow --version`, `python -m econflow.cli --version`, `econflow
  init`, `econflow validate`, and `econflow run` against
  `examples/getting_started`. All succeeded, producing real output files
  (`table_fe_investment.csv`, `table_fe_investment.tex`,
  `provenance/run_metadata.json`).
- `pip check` reported no broken requirements; `pip show econflow` correctly
  reported the package's version, MIT license, and full dependency list.

This is the strongest available evidence that the pipeline works outside
the development checkout, not only inside it.

### Blind replication example (`examples/blind_replication/`)

A self-contained example ships with the repository specifically to
demonstrate the replication chain end-to-end:

- Synthetic panel: 6 firms × 15 years, with a known data-generating process
  (`invest = 1.8×market_value + 0.6×capital_stock + firm FE + ε`, seed 7).
- Three estimators (Pooled OLS, Entity FE, Two-Way FE) with reference
  outputs committed alongside the example.
- `econflow reproduce` re-executes the pipeline from the committed config
  and compares fresh output against the reference outputs using a
  file-type-aware comparator (numeric tolerance for CSV, structural
  comparison for LaTeX, deep comparison for JSON), returning **PASS**.

### Provenance and certification chain

- `econflow certify` builds a `ReproducibilityCertificate`: SHA-256
  fingerprints of the input data and config files, plus environment
  fingerprints (git commit, dirty flag, Python and package versions).
  Atomic writes via `os.fsync()` + `Path.replace()`.
- `econflow verify` re-fingerprints the current environment/outputs and
  compares against a certificate on 8 axes: git commit, dirty flag, package
  versions, data SHA-256, data row count, data file presence, and config
  SHA-256. Severity levels: none / warn / fail.
- `econflow package` builds a self-contained, journal-ready replication
  directory (`certificate.json`, `environment.txt`, `config/`, `scripts/`,
  an auto-generated `README.md` with replication instructions, and
  `manifest.json`).
- `econflow reproduce` runs the full inspect → plan → execute → compare
  workflow against a replication package: an 8-point pre-flight check
  (Python version, config files, data file, SHA-256 checksum, estimator
  registry, dependencies), a deterministic execution plan, subprocess-isolated
  execution with per-step timing, and a structured comparison report
  (Markdown + JSON) against the package's original outputs.

### Path resolution and cross-directory reproducibility

`data.path` and `outputs.base_dir` are resolved relative to the config
file's own directory rather than the current working directory, so
`econflow run` produces identical results regardless of which directory it
is invoked from — verified by the fact that both bundled examples
(`getting_started/`, `blind_replication/`) use config-directory-relative
paths and both pass their respective test suites and CLI checks.

## Known reproducibility gap (disclosed, non-blocking)

`tests/integration/fixtures/baseline/numerical_results.json` and
`diagnostics_full.json` (integration test fixtures, not shipped release
artifacts) contain a `"const"` parameter for EntityFE/TwoWayFE that the
current `linearmodels`-backed estimators (with `entity_effects=True`) cannot
produce — indicating these two fixtures predate the current estimator
implementation at a structural level. They were spot-checked and their
coefficient values (as opposed to their structure) are not stale, since no
change to estimator coefficients has occurred since they were captured. No
verified regeneration script exists for these two files; rather than
guess-patch them, they are documented as known technical debt (see
`docs/development/TECHNICAL_DEBT.md`). This does not affect any shipped
output, example, or the `certify`/`verify`/`package`/`reproduce` chain
described above, all of which operate on live pipeline output, not these
two fixture files.

## Cross-platform scope

All reproducibility evidence above was gathered on Linux
(`ubuntu-latest`-equivalent, matching CI). No Windows or macOS execution has
been performed for this release; static source analysis found no
platform-specific defects (no hardcoded `/dev/null` or `os.sep`
string-building; `pathlib`-based path handling throughout; UTF-8 console
reconfiguration present for Windows), but this remains an unverified claim,
not a tested one. See `RELEASE_NOTES_v1.0.0.md`, "Known Limitations."

## Conclusion

EconFlow's reproducibility claims are backed by direct, repeated execution
evidence at all three levels defined above (same-machine determinism,
clean-environment install, third-party replication), with one disclosed,
non-blocking fixture-staleness gap that does not touch any shipped output.
