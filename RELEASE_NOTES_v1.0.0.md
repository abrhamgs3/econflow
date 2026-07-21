# EconFlow v1.0.0

**Release date:** 2026-07-19

EconFlow's first tagged release. This is a config-driven, plugin-registry-based
platform for reproducible panel econometric research — from raw data through
publication-ready regression tables, figures, and provenance certificates.

---

## Overview

EconFlow grew out of a single applied research project (*AI Adoption and Total
Factor Productivity: Panel Evidence from 193 Countries*, included as
[`examples/ai_productivity_paper/`](examples/ai_productivity_paper/)) and was
generalized into a reusable framework: any panel study can be defined with
three YAML files (`config.yaml`, `models.yaml`, `outputs.yaml`) and run without
touching Python code.

v1.0.0 marks the point where the estimation dispatcher, diagnostics, output
renderers, and integrity/reproducibility tooling have gone through multiple
independent audit passes (dead-code sweeps, documentation-consistency checks,
clean-checkout installs, and end-to-end reproducibility runs) and settled into
a stable, self-consistent state. Nothing in this release is a "first draft" —
every component listed under Major Features has passing tests and has been
exercised through the CLI, not just imported.

## Highlights

- First tagged release — the package version, CLI `--version` output, and
  `CITATION.cff` are consistent at `1.0.0` for the first time.
- A single `EstimationDispatcher` is now the sole production execution path
  for `econflow run` (no legacy inline estimation code remains).
- Diagnostics (VIF, Breusch-Pagan, Durbin-Watson using the
  Bhargava-Franzini-Narendranathan 1982 panel formula, Hausman, Pesaran CD)
  are computed once per estimator and surfaced consistently across CLI output
  and rendered tables.
- Full provenance chain: `certify` → `verify` → `package` → `reproduce` lets
  a third party re-run your analysis from a replication package and get a
  structured pass/fail comparison against your original outputs.
- Five data connectors (CSV, World Bank, OECD, Penn World Table, FRED) behind
  one registry, with citation and version metadata built in.

## Major Features

- **Panel estimators**: Pooled OLS, Entity FE, Two-Way FE, Random Effects,
  First Difference, and IV (2SLS), all backed by `linearmodels`. Every FE
  estimator reports the within-R² / within-adjusted-R² convention (matching
  Stata `xtreg, fe`, R `plm`, and R `fixest`), not the overall R² common in
  naive implementations.
- **Diagnostics**: VIF, Breusch-Pagan heteroskedasticity, panel Durbin-Watson
  (BFN 1982 within-entity formula), Hausman specification test, Pesaran CD,
  plus IV-specific diagnostics (first-stage F, Sargan-Hansen, Wu-Hausman) and
  a cluster-count warning for small cluster counts.
- **Output rendering**: CSV, LaTeX (booktabs), Markdown, HTML, and JSON
  renderers for regression tables, summary statistics, and coefficient plots.
- **Config validation**: a four-stage validator (YAML syntax → Pydantic
  schema → 13 semantic lint rules → cross-file consistency) that fails fast
  with actionable, file-and-line error messages before any output is written.
- **Reproducibility & integrity**: `econflow certify` generates a
  `ReproducibilityCertificate` with SHA-256 fingerprints of code, data, and
  config; `econflow verify` detects drift against a baseline; `econflow
  package` builds a self-contained, journal-ready replication directory;
  `econflow reproduce` re-executes a package end-to-end and reports a
  structured comparison.
- **Data ingestion**: CSV loader plus World Bank, OECD, Penn World Table, and
  FRED connectors, all behind a shared registry with citation and version
  metadata and a local on-disk cache.
- **Plugin system**: estimators, diagnostics, and renderers are all extended
  via `@register` decorators and are auto-discoverable through
  `[project.entry-points."econflow.plugins"]`, documented in the
  [Plugin SDK](docs/sdk/PLUGIN_SDK.md).

## Installation

EconFlow is not yet published to PyPI for this release. Install from source:

```bash
git clone https://github.com/abrhamgs3/econflow.git
cd econflow
pip install -e ".[dev]"
```

Verify the installation:

```bash
econflow doctor
econflow --version   # EconFlow 1.0.0
```

## Quick Start

```bash
# 1. Create a new project skeleton
econflow init my_study
cd my_study

# 2. Edit config/config.yaml — set data path, entity/time columns, variables

# 3. Validate configuration before running
econflow validate config/

# 4. Run the analysis pipeline
econflow run \
    --config  config/config.yaml \
    --models  config/models.yaml \
    --outputs config/outputs.yaml

# 5. Generate a reproducibility certificate
econflow certify
```

See [`examples/getting_started/`](examples/getting_started/) for a full
10-minute tutorial using the Grunfeld firm investment panel, and
[`examples/blind_replication/`](examples/blind_replication/) for a complete
replication-package walkthrough.

## Documentation

- [README](README.md) — project overview, features, package layout
- [CLI Guide](docs/user/CLI_GUIDE.md) — full command reference
- [Configuration Reference](docs/reference/configuration.md) — auto-generated
  from the live Pydantic schema (always in sync with `config.yaml` /
  `models.yaml` / `outputs.yaml`)
- [Plugin SDK](docs/sdk/PLUGIN_SDK.md) — how to register custom estimators,
  diagnostics, and renderers
- [CONTRIBUTING](CONTRIBUTING.md) — development setup and contribution process
- [CHANGELOG](CHANGELOG.md) — full development history

## Scientific Reproducibility

Every `econflow run` reads three declarative YAML files and produces
identical numerical output given the same data, config, and dependency
versions — there is no hidden state or randomness in the estimation path.

- `econflow certify` fingerprints the git commit, Python/package versions,
  and SHA-256 of both the input data and config files, bundling them into a
  `ReproducibilityCertificate`.
- `econflow verify` re-fingerprints the current environment/outputs and
  reports drift against a certificate on 8 axes (git commit, dirty flag,
  package versions, data hash, data row count, data file presence, config
  hash).
- `econflow package` / `econflow reproduce` let a third party (or your future
  self) re-execute the full pipeline from a self-contained directory and get
  a structured, toleranced comparison (numeric tolerance for CSV, structural
  comparison for LaTeX, deep comparison for JSON) against the original
  outputs.
- The `examples/blind_replication/` example demonstrates this end-to-end: a
  synthetic panel with a known data-generating process, run through
  `econflow reproduce`, returns PASS.

This chain has been independently verified this release cycle via a clean,
non-editable wheel install and a full `init → validate → run → certify →
package → reproduce` walkthrough from an empty working directory.

## Known Limitations

- **System GMM and panel quantile regression are not implemented.** Both are
  registered in the estimator registry and both self-report
  `status="stub"`; calling `.fit()` on either raises `NotImplementedError`
  by design, and `econflow validate` warns if a config references them
  (lint rule L-04b). They are not currently scheduled for a specific future
  release.
- **The diagnostics plugin registry (`diagnostics/registry.py` and
  `diagnostics/plugins/*`) is fully built and documented but not wired into
  the `econflow run` pipeline.** The diagnostics you see in CLI output and
  rendered tables come from each estimator's own `diagnostics()` method, not
  the plugin registry. The plugin registry's only current consumer is an
  import smoke-test in `econflow release-check`. This is disclosed in the
  Plugin SDK documentation rather than presented as wired up.
- **Cross-platform compatibility (Windows/macOS) is verified by static
  analysis only.** CI (`.github/workflows/ci.yml`) runs exclusively on
  `ubuntu-latest` across Python 3.10–3.12. No Windows or macOS test run has
  been executed against this release. Known Windows-specific fixes (UTF-8
  console reconfiguration, avoiding bare `econflow` subprocess calls in the
  replication planner) are present in source but not live-verified on
  Windows.
- **`tests/unit/test_release_check.py` passes in isolation (66/66) but has a
  known test-isolation issue when collected together with the full suite.**
  It is deselected from the CI-run configuration; the root cause (shared
  state leaking between test modules) has not been identified.
- **`processing/`, `sensitivity/`, `ml/`, `features/`, and most of `core/`,
  `data/`, `econometrics/`, `reporting/` are architectural stubs**, largely
  unreferenced outside themselves and excluded from coverage accounting
  (see `docs/development/TECHNICAL_DEBT.md` for the per-file breakdown).
  `estimation/`, `diagnostics/`, and `outputs/` are live and load-bearing
  despite sharing the coverage-omit list for a different reason (stub-code
  dilution) — see the comment in `pyproject.toml`.
- **`numerical_results.json` / `diagnostics_full.json`** (integration test
  fixtures, not shipped release artifacts) contain a structural anomaly
  predating the current FE estimator implementation and have not been
  regenerated; tracked as technical debt, does not affect any shipped output.

## Citation

If you use EconFlow in academic or research work, please cite it. A
machine-readable [`CITATION.cff`](CITATION.cff) is provided for tools that
read it automatically (including GitHub's "Cite this repository" widget).

```bibtex
@software{econflow2026,
  author  = {Meressa, Abrha Megos},
  title   = {{EconFlow}: Reusable panel econometrics research platform},
  year    = {2026},
  version = {1.0.0},
  url     = {https://github.com/abrhamgs3/econflow},
  license = {MIT}
}
```

## License

[MIT](LICENSE) © 2026 Abrha Megos Meressa

## Acknowledgements

EconFlow was originally extracted from the *AI Adoption and Total Factor
Productivity* research project and generalized for reuse across panel
studies. Thanks to everyone who filed issues, ran audits, and reviewed the
release-candidate reports archived in [`docs/release/`](docs/release/)
throughout this development cycle.
