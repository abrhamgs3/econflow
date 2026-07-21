# EconFlow v1.0.0 — Release Audit

**Date:** 2026-07-19
**Status:** Archival summary for the v1.0.0 tag. Compiled from existing audit
evidence already in `docs/release/`; no new audit findings are asserted here
that were not independently demonstrated in a prior session's report.

This document exists to satisfy the release-execution checklist's requirement
for a single `RELEASE_AUDIT_v1.0.0.md`. It does not replace the detailed
audit reports it summarizes — those remain in `docs/release/` as the primary
evidence trail. Where a claim below is not directly attributable to one of
those reports or to this session's own verification, it is not made.

## Audit trail (chronological, most recent first)

1. **RC Finalization Audit** (`RC_FINALIZATION_AUDIT.md`, 2026-07-19,
   baseline `c2b8cd6`) — ten-point audit (dead code, documentation
   consistency, installation, end-to-end reproducibility, examples, release
   artifacts, CI, silent failures, nondeterminism, final checklist). Verdict:
   **READY AFTER MINOR FIXES**. Overall score 82/100. Zero blockers found.
   Two documentation-contradicts-implementation defects found and precisely
   located:
   - `econflow report`'s docstring "Expected output" section described
     behavior that could not occur (the command was correctly labeled
     `[beta]` and did not crash, but its docstring example was fabricated).
   - `pyproject.toml`'s coverage-omit comment grouped three live,
     heavily-tested packages (`estimation/`, `diagnostics/`, `outputs/`)
     under a comment describing them as dead-code stubs.
   Also confirmed: a fresh, non-editable wheel install (`python -m build` →
   new virtualenv, no source tree on path) runs `econflow --version`,
   `init`, `validate`, and `run` correctly against `examples/getting_started`,
   producing real output files; `pip check` reports no broken requirements.

2. **Two targeted fixes applied following the RC Finalization Audit**, each
   scoped to documentation only, per the audit's own recommendation:
   - `econflow report` docstring corrected to describe current, demonstrated
     behavior instead of a scenario that cannot occur (commit `2905f7a`).
     Verified via `pytest tests/unit/test_cmd_report.py`.
   - `pyproject.toml`'s coverage-omit comment rewritten to accurately
     describe why `estimation/`, `diagnostics/`, and `outputs/` are
     omitted (stub-code dilution of the coverage percentage, not dead code)
     while keeping the omit list itself unchanged (commit `8f110c1`).
     Verified via a full `pytest` run.

3. **Release Manager sign-off** — following the two fixes above, a
   direct sign-off review (source, documentation, packaging, CLI,
   reproducibility, release artifacts) was conducted and answered **YES**.
   See `RELEASE_SIGNOFF_v1.0.0.md` for the formal record.

4. **This release-execution session** (2026-07-19–2026-07-21, this document's
   session) performed Phase 1 repository verification for the actual
   v1.0.0 tag: the package had never been version-bumped past `0.1.0` despite
   the above audits treating it as release-ready. Found and fixed:
   - `pyproject.toml` and `src/econflow/__init__.py`: `version`/`__version__`
     bumped `0.1.0` → `1.0.0`.
   - `src/econflow/cli.py`: three example-output strings in the module
     docstring updated from `EconFlow 0.1.0` to `EconFlow 1.0.0`.
   - `README.md`: corrected stale "GMM and panel quantile are planned for
     v1.0" phrasing (both remain unimplemented stubs with no committed
     release target) and its bibtex citation block's `version` field.
   - `CHANGELOG.md`: consolidated six stacked `[Unreleased]` sections
     (the project had never had a tagged release) into `[1.0.0]`, preserving
     each section's original date/sprint label.
   - `CITATION.cff`: `version`/`date-released` bumped to `1.0.0` /
     `2026-07-19` in both the top-level and `preferred-citation` blocks; a
     commented-out Zenodo DOI placeholder was added pending DOI mint.
   All version-string-adjacent tests (`test_cli_discoverability.py`,
   `test_cmd_info.py`, `test_cmd_validate.py`, `test_consistency_regression.py`,
   `test_release_check.py`, `test_config_docs.py`, `test_integrity_drift.py`,
   `test_cmd_init.py`, `test_cmd_doctor.py` — 246 tests total) re-run and
   passing after these changes. Live CLI re-verified:
   `python -m econflow.cli --version` → `EconFlow 1.0.0`;
   `python3 -c "import econflow; print(econflow.__version__)"` → `1.0.0`.
   Committed as `fd9c8dd`.

## Carried-forward, disclosed (non-blocking) findings

These are not newly discovered by this session; they are re-stated here
because they remain true at the v1.0.0 tag and are relevant to anyone
reading this audit in isolation. Full detail and evidence in the source
reports cited above and in `RELEASE_NOTES_v1.0.0.md`'s "Known Limitations"
section.

- System GMM and panel quantile regression are registered but unimplemented
  (`status="stub"`, raise `NotImplementedError`).
- The diagnostics plugin registry is fully built and documented but not
  wired into `econflow run`'s live diagnostics path.
- CI (`.github/workflows/ci.yml`) runs on `ubuntu-latest` only; Windows/macOS
  compatibility is verified by static source analysis, not live execution.
- `tests/unit/test_release_check.py` passes in isolation but has an
  unresolved, disclosed test-isolation issue when collected with the full
  suite; deselected from the CI run configuration.
- Coverage is configured (`fail_under = 70`) but not enforced in CI — no
  `--cov` flag is passed to the `pytest` invocation in `ci.yml`.

## Verdict at v1.0.0 tag time

**READY.** No blocker has been found across any audit pass in this
repository's history that was not subsequently fixed and independently
re-verified. The two minor documentation defects identified by the RC
Finalization Audit — the last audit that withheld a clean verdict pending
fixes — have both been fixed and test-verified. The remaining disclosed
items above are documented limitations, not defects, and are carried
forward transparently in `RELEASE_NOTES_v1.0.0.md` rather than concealed.
