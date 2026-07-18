# EconFlow Repository Integrity Report

**Type:** Repository Integrity Audit (diagnosis only — no code, tests, or documentation were modified)
**Date:** 2026-07-17
**Scope:** Post-separation consistency of the EconFlow repository (formerly part of the AI & Productivity monorepo)
**Method:** Direct inspection of git state, installed package metadata, filesystem structure, file mtimes, and source-vs-documentation cross-reference. No prior report (including this session's own earlier RELEASE_CHECKLIST_v1.0.md and BLOCKER_VERIFICATION_REPORT.md) was accepted without re-verification; where this report reuses a finding from those documents, it is re-grounded here in the underlying evidence rather than cited on authority.

---

## 1. Git Integrity

**Branch:** `main` (single local branch; no evidence of feature branches).

**HEAD commit:** `35f5926dded9cdea20da299052316abc273370e7`, 2026-07-09 18:31:09 -0400, `"Sprint 11F: Fix evaluator-reported issues"`.

**Working tree status:** Dirty. Two distinct layers of uncommitted change exist:

- **Staged but not committed** (in the git index, ahead of HEAD): `src/econflow/estimation/dispatcher.py` (new file, blob `61f25aa6…`), `src/econflow/pipeline_generic.py` (344 lines changed). `git commit` alone would capture these.
- **Unstaged on top of an already-stale index**: `src/econflow/__init__.py` (53 lines, including this session's own PEP 562 `__getattr__` fix), `src/econflow/exceptions.py`, `src/econflow/estimation/_diagnostics.py`, `src/econflow/estimation/base.py`, `src/econflow/estimation/fixed_effects.py`, `src/econflow/estimation/iv.py`, `src/econflow/config/validator.py`. These require `git add -A` before a commit would capture them.

**Untracked files:** present (not exhaustively enumerated here; confirmed via `git status --porcelain` during Blocker 1 verification).

**Phase 6 source at HEAD:** **Absent.** `git log --all --oneline -- src/econflow/estimation/dispatcher.py` and the same for `src/econflow/estimation/_diagnostics.py` return **zero commits in any ref** — these files have never been committed anywhere in this repository's history, on any branch. Everything described in the Architecture Freeze document, the Phase 5/Phase 6 migration reports, and Sprint S1/S2/R1–R3 reports exists **only** as working-tree/index state layered on top of a HEAD that predates all of it by git-log evidence.

**Finding:** The gap between "documented architecture" and "committed architecture" is total for the dispatcher/diagnostics subsystem: the files exist on disk and are functional, but git has no record of them. This is the single largest integrity fact in this audit and downstream of nearly every other finding in this report.

**Classification: A (repository corruption)** — not in the sense of file corruption, but in the sense that the repository's version-control record and its actual working state have diverged to the point that `git log`, `git blame`, and any commit-based provenance are silently wrong about what code produced what output. A clone of this repository at HEAD would not build the system currently being tested and documented.

---

## 2. Package Integrity

- **Editable installation:** confirmed. `pip show econflow` → `Version: 0.1.0`, `Editable project location: /sessions/lucid-hopeful-faraday/mnt/econflow`.
- **Import location:** confirmed via live interpreter — `econflow.__file__` resolves into the working tree, not into a site-packages copy.
- **`direct_url.json`:** `{"dir_info": {"editable": true}, "url": "file:///sessions/lucid-hopeful-faraday/mnt/econflow"}` — consistent, no stale editable-install pointer to a different (e.g. pre-separation monorepo) path.
- **`__version__`:** `0.1.0`, matching `pyproject.toml`.
- **`pyproject.toml` / package metadata:** internally consistent with the installed distribution; no leftover monorepo package name, no stray dependency on an internal "ai_productivity" package.

**Finding:** No evidence of package corruption or of the separation from the former monorepo having left broken metadata. This layer is clean.

**Classification: no finding (PASS)** — not applicable to A–E.

---

## 3. Repository Completeness

Top-level: `agents/, app/, dist/, docs/, examples/, my_test_study/, outputs/, src/, tables/, tests/`.

- **`examples/`** — present, non-empty: `getting_started/`, `blind_replication/`, `ai_productivity_paper/`, plus a top-level `README.md`. `getting_started/` has the expected `config/`, `data/`, `expected_outputs/`, `outputs/{provenance,replication_package,report,tables}` structure. `blind_replication/` has `config/`, `data/`, `original_outputs/tables/`, `outputs/{provenance,tables}`, `replication_report/`. **Complete relative to what the docs describe.**
- **`outputs/`** — present at repo root, but its contents are governed by `.gitignore` (`outputs/*/tables/`, `outputs/*/figures/`, `outputs/*/run_metadata.json` ignored, with explicit un-ignores for `outputs/.gitkeep`, `outputs/provenance/schema.json`, `outputs/provenance/REPRODUCIBILITY_REPORT.md`). This is by design, not a gap.
- **`fixtures/`** — present at `tests/integration/fixtures/baseline/`: `README.md` + 8 fixture files (`diagnostics.csv`, `diagnostics_full.json`, `comparison_table.{csv,md,html,tex}`, `numerical_results.json`, `provenance_schema.json`). Complete as a set; staleness is addressed separately in §4.
- **`baselines/`** — same directory as above; no separate top-level `baselines/` directory is referenced by any doc read in this audit, so nothing is missing here.
- **`docs/`** — present and extensive: `API_STABILITY.md`, `MIGRATION_PLAN.md`, `SPRINT6_RC1_REVIEW.md`, `SPRINT_MIGRATION_ROADMAP.md`, plus `architecture/`, `development/`, `maintenance/`, `reference/`, `release/` (21 files), `release_notes/`, `reviews/`, `roadmap/`, `sdk/`, `user/`. Structurally complete. (§5 addresses whether the *content* of these directories agrees with itself — it does not, in several places.)
- **`docs/reference/`** — thin: only `configuration.md`. If the SDK or CLI reference docs are expected here rather than in `docs/sdk/`, this could read as a gap, but `docs/sdk/PLUGIN_SDK.md` covers that material elsewhere, so this is an organizational choice, not a missing deliverable.
- **Release reports** — `docs/release/` holds 21 files including this session's own `RELEASE_CHECKLIST_v1.0.md` and `BLOCKER_VERIFICATION_REPORT.md`. Present.

**Anomalies found (not "missing," but structurally irregular):**

- **`my_test_study/`** matches the `.gitignore` pattern `*_study/` (line 106–107), yet `git status --short my_test_study/` shows 15+ tracked files, all marked `D` (deleted from the working tree, not staged). This means the directory **was committed to git history** at some point — predating or contradicting its own gitignore rule — has since been deleted from disk by hand, and that deletion itself has never been committed. The repository is currently in a state where `git status` shows real, uncommitted deletions that nobody has resolved.
- **`tables/data_validation_report.json`** at the repo root is git-tracked (`git ls-files tables/` includes it) and shows status `MM` with a very fresh mtime — this is a legacy-pipeline-default artifact (matches `cli.py`'s legacy `--tables-dir` default of `Path("tables")`) that regenerates at the repo root every time the pipeline or test suite runs from there, and is currently sitting in the tree with uncommitted modifications from this session's own test runs.

**Classification:**
- Core directory completeness vs. documentation: **no finding (PASS)**.
- `my_test_study/` tracked-but-deleted state: **A (repository corruption)** — the git index and working tree disagree about whether this content exists, and nothing in the repo's current state resolves that disagreement.
- `tables/data_validation_report.json` root-level regeneration: **B (stale/stray artifact)** — a build/run byproduct that has been accidentally committed to version control and keeps drifting out of sync with itself on every pipeline run.

---

## 4. Generated Artifact Staleness

Mtimes gathered directly via `stat -c '%y %n'` on files this session had not itself touched or regenerated, to isolate genuine pre-existing repository staleness from side effects of this session's own test runs.

**Source files (the code that produces the artifacts):**

| File | mtime |
|---|---|
| `src/econflow/estimation/dispatcher.py` | 2026-07-10 20:57:06 |
| `src/econflow/pipeline_generic.py` | 2026-07-10 22:01:07 |
| `src/econflow/estimation/_diagnostics.py` | **2026-07-12 07:35:32** |
| `src/econflow/outputs/renderers/latex_renderer.py` | 2026-07-08 15:49:06 |

**Frozen fixtures (`tests/integration/fixtures/baseline/`):**

| File | mtime |
|---|---|
| `numerical_results.json` | 2026-07-10 08:40:00 |
| `diagnostics.csv` | 2026-07-10 08:42:57 |
| `comparison_table.csv` | 2026-07-10 08:45:43 |
| `comparison_table.md` | 2026-07-10 08:45:56 |
| `comparison_table.html` | 2026-07-10 08:46:08 |
| `comparison_table.tex` | 2026-07-10 08:45:51 |
| `README.md` | 2026-07-10 08:46:39 |

**Expected-output reference copies (`examples/getting_started/expected_outputs/`):**

| File | mtime |
|---|---|
| `table_fe_investment.csv` | 2026-07-08 15:04:20 |
| `table_fe_investment.tex` | 2026-07-08 15:52:03 |
| `diagnostics.csv` | 2026-07-10 22:50:17 |

**Reading the evidence:**

`_diagnostics.py` — the module containing the Bhargava–Franzini–Narendranathan (1982) panel Durbin-Watson formula identified as the Blocker 2 root cause in the prior verification report — was last modified **2026-07-12 07:35**. Every one of the six `tests/integration/fixtures/baseline/*` fixtures was generated on **2026-07-10, between 08:40 and 08:46** — roughly a day and a half *before* `_diagnostics.py`'s last change. This is direct, mechanical, timestamp-based corroboration — independent of the content-diffing and docstring-reading method used in the earlier BLOCKER_VERIFICATION_REPORT — that the baseline fixtures predate the diagnostics logic they are supposed to be checking. They cannot reflect a computation that did not exist yet when they were written.

The same pattern recurs one layer out: `examples/getting_started/expected_outputs/diagnostics.csv` (2026-07-10 22:50) also predates `_diagnostics.py`'s 2026-07-12 07:35 mtime, by about 33 hours. This is a *second, independent* copy of stale diagnostics output, separate from the fixtures directory — meaning the staleness is not confined to one file but is a pattern across every frozen diagnostics artifact in the repository.

`table_fe_investment.csv`/`.tex` in `expected_outputs/` are older still (2026-07-08), predating even `pipeline_generic.py`'s 2026-07-10 22:01 mtime by roughly 31 hours — consistent with the previously-established comparison-table column-label discrepancy (raw model IDs vs. human-readable labels): the reference file was frozen before the label-lookup behavior in `_build_comparison_table()` was in its current form.

`numerical_results.json` (2026-07-10 08:40) predates both `dispatcher.py` (2026-07-10 20:57) and `pipeline_generic.py` (2026-07-10 22:01) by 12–13 hours. Coefficients themselves matched exactly when this session ran the pipeline fresh (see Blocker 2 verification), so this particular gap has not produced an observed numerical discrepancy — but the ordering is the same stale-relative-to-source pattern as the diagnostics fixtures, and should not be assumed safe merely because no test currently exercises the affected code path.

**Finding:** Every generated/frozen artifact examined in this repository was captured *before* the source code that generates its content reached its current state. None of the discrepancies traced to this pattern (Durbin-Watson value, comparison-table column headers) reflect a defect in current source — in each traced case the source is econometrically correct and the frozen artifact is what's out of date. But the pattern is repository-wide, not isolated to the one test class already investigated, and nothing in the repository currently regenerates these fixtures automatically (the one helper written for that purpose, `_run_pipeline()` in `test_pipeline_baseline.py`, is dead code and independently broken — see §6).

**Classification: B (stale artifact)** — uniformly, across all files examined in this section.

---

## 5. Architecture Freeze Consistency

`docs/architecture/ARCHITECTURE_FREEZE_v1.md` (dated 2026-07-10, Status: FROZEN) is the governing document. Comparing it, `docs/sdk/PLUGIN_SDK.md`, live source, and the test suite turns up the following inconsistencies, all previously surfaced in this conversation's blocker verification and reconfirmed here:

1. **`EstimationResult.rsq` vs. `rsquared`.** PLUGIN_SDK.md documents the field as `rsq`; `src/econflow/estimation/result.py` (line 159, confirmed by direct read) defines it as `rsquared`. Every consumer in source uses `rsquared`. The SDK doc is wrong.
2. **PLUGIN_SDK.md's "required fields" list for `EstimationResult`** omits `estimator_name`, `conf_int`, `ngroups`, `df_resid`, and `rsquared_adj` entirely, despite all five being present, non-optional dataclass fields in `result.py`. The documented interface is a strict subset of the real one.
3. **`DiagnosticResult.check` vs. `diagnostic_id`.** PLUGIN_SDK.md documents `check`; `result.py` (line 50) defines `diagnostic_id`. Wrong field name in the SDK doc.
4. **`level` vocabulary — three-way disagreement.** PLUGIN_SDK.md says `"info"|"warn"|"error"`. ARCHITECTURE_FREEZE_v1.md §1.3 says `"info"|"warn"|"fail"`. Live source (`result.py` line 40 docstring, and a repository-wide grep for the literal strings `level="warn"` / `level="fail"`) shows the actual values in use are `"info"`, `"warning"` (full word, not `"warn"`), `"error"`, and `"skip"` (the last set explicitly by `BaseDiagnostic._not_applicable()`, confirmed at `diagnostics/base.py` line 156). `"warn"` and `"fail"` occur **zero times** anywhere in `src/econflow/`. Both governing documents disagree with each other *and* with the code; neither is authoritative.
5. **`BaseDiagnostic.run()` signature.** PLUGIN_SDK.md documents `run(self, result, data=None)`. The actual abstract method (`diagnostics/base.py` lines 84–89, confirmed by direct read) is `run(self, result: EstimationResult, **kwargs: Any)`. A plugin author following the documented signature would write an incompatible override.
6. **`_not_applicable()` return value.** PLUGIN_SDK.md documents this helper as returning `level="info"` plus a `status="skip"` field. Neither is accurate: the actual implementation (`diagnostics/base.py` lines 150–157) sets `level="skip"` directly and has no `status` field at all — `DiagnosticResult` has no such field in its dataclass definition (`result.py` lines 50–57).

All six of the above are **documentation defects**, not API defects: in every case the live source is internally consistent with itself (estimators, diagnostics, pipeline, and tests all agree on the real field names and signatures), and it is only the SDK/Architecture-Freeze documentation that is wrong. This matters for release risk — a third-party plugin author has no way to discover this without reading source, defeating the purpose of a frozen SDK document — but it is not evidence of an unstable or contradictory *implementation*.

**Additional inconsistencies found in this pass, not previously enumerated:**

7. **The "frozen" dispatcher/diagnostics files have no git history** (§1). Calling an interface "frozen" as of 2026-07-10 in a document that is itself uncommitted, describing files that are themselves uncommitted and have never been committed, is a freeze in name only — there is no committed reference point anyone could diff against to detect a future violation of the freeze.
8. **`CHANGELOG.md`'s current `[Unreleased]` section is titled "Sprint 11F: Evaluator-Reported Fixes"** and its content maps exactly to the HEAD commit message ("Sprint 11F: Fix evaluator-reported issues"). A full-file grep for `phase 5|phase 6|sprint s1|architecture freeze|dispatcher|estimationdispatcher` (case-insensitive) returns **zero matches** in 612 lines. The single most authoritative "what shipped and when" document in the repository contains no record of the Architecture Freeze, the Phase 5/6 dispatcher migration, or Sprint S1/S2 at all — consistent with §1's finding that none of it has been committed, but worth stating plainly: if a release were cut from the current working tree today, the changelog accompanying it would not mention roughly the last week of architectural work.
9. **`test_pipeline_baseline.py::test_baseline_csv_has_three_model_columns`** (self-consistency test within the fixture's own test file, lines ~540–543, confirmed by full read) asserts that the *fixture itself* uses raw lowercase model IDs (`pooled_ols`, `entity_fe`, `twoway_fe`) as column headers. Current `pipeline_generic.py::_build_comparison_table()` (lines 207–231) looks up each model's `label:` field from `models.yaml` and produces human-readable headers ("Pooled OLS", etc.) instead. The test file thus contains two mutually contradictory assumptions about the same output format, one that matches current source (none of the file-comparison tests) and one that matches the stale fixture (this self-consistency test) — the file was evidently updated piecemeal rather than regenerated as a whole.

**Classification:** Items 1–6, 8, 9 → **C (stale documentation)**. Item 7 (freeze declared over uncommitted files) → **A (repository corruption)**, since it is a version-control state problem, not a wording problem — the fix is not editing prose, it's making a commit.

---

## 6. Test Assumption Verification

Failing or previously-flagged tests, classified against the five categories requested (stale fixtures, stale generated outputs, dependency drift, incorrect CLI assumptions, actual source regressions):

| Test / area | Root cause | Category |
|---|---|---|
| `test_diagnostics_csv_matches_baseline` (Durbin-Watson value) | Fixture frozen 2026-07-10, before `_diagnostics.py`'s 2026-07-12 BFN panel-DW change (§4); the panel formula is a deliberate, cited (Bhargava, Franzini & Narendranathan 1982) econometric improvement over the prior pooled-time-series formula, not a regression | **Stale fixture** |
| `test_comparison_table_csv_matches_baseline` (column headers) | Fixture predates `_build_comparison_table()`'s label-lookup behavior; fixture's own self-consistency test still asserts the old raw-ID convention (§5, item 9) | **Stale fixture** |
| Coefficient/BP-statistic mismatches observed on first read of file-comparison tests | Not a code issue at all — this session's *first* read of these files was contaminated by stale files already sitting on disk before the pipeline was re-run; re-running `econflow run --config … --models … --outputs …` produced values matching the baseline exactly | **Stale generated output** (a testing-methodology artifact of this audit, not a repository defect — flagged here for completeness since it explains why an earlier pass of this investigation reported different numbers) |
| `_run_pipeline()` helper in `test_pipeline_baseline.py` (lines 85–103) | Dead code — never called anywhere in the file — and independently broken: invokes `python -m econflow.cli run <CONFIG_PATH> …` with `CONFIG_PATH` as a bare positional argument, but `econflow run` (per full read of `cli.py`) accepts only `--config`/`-c`, never a positional. Reproduced directly: silent exit 0, zero stdout/stderr, a no-op. This is the reason none of the fixture files ever get automatically refreshed | **Incorrect CLI assumption** |
| `test_release_check.py` — 21 of the file's tests failing under `pytest -n 2` | Parallel-worker collision in subprocess-spawning tests; re-run of the same file without `-n` gave 66/66 passed | **Not a repository defect at all** — a test-execution/harness artifact specific to `xdist` concurrency, orthogonal to the five requested categories. Recorded here so it is not mistaken for a regression in any future audit |
| `test_validate_strict_succeeds_on_valid_cluster` | Fixture path/models mismatch identified in earlier verification pass this conversation | **Stale fixture** |
| `test_plugin_sdk_no_phantom_v1_constraint` | Traced in the prior blocker report to PLUGIN_SDK.md §11.1 describing forward-looking v1.0 guidance that the test misreads as a present-tense constraint | **Stale documentation** driving a false-positive test failure |
| Adjusted-R² / `df_resid` unit-test expectation mismatches (fixed_effects/OLS estimators; off-by-one on `df_resid`, e.g. 217 vs. 218) | These tests exercise live, in-process `EstimationResult` objects (via the `pipeline_results` fixture doing direct linearmodels re-estimation), not frozen files — so unlike the fixture-based failures above, this is either a genuine current-source behavior change or a stale hardcoded expected value in the test itself. The off-by-one pattern is consistent with the same class of Sprint S1 scientific-correctness fix as the Durbin-Watson change (e.g., how the constant term is counted in degrees-of-freedom), but this was flagged as **unconfirmed** in the prior BLOCKER_VERIFICATION_REPORT and remains unconfirmed here — no independent evidence (git history, Sprint S1 changelog entry, or DoF-formula diff) was found this session to settle which side is correct | **Undetermined — could not be classified with available evidence.** Flagged explicitly rather than guessed, per the standing instruction not to invent a conclusion |
| Dependency drift (linearmodels/statsmodels/pandas/numpy version changes) as an explanation for any of the above | Directly disproven in this conversation's earlier `REPRODUCIBILITY_INVESTIGATION_12_FAILURES.md` work via `uv.lock` cross-commit analysis — pinned versions are unchanged across the commits in question | **Ruled out** — no evidence of dependency drift anywhere in this audit |

**Overall test-assumption finding:** Of the failing/flagged tests examined across this conversation, the large majority resolve to stale fixtures or an incorrect CLI assumption in test infrastructure (the broken `_run_pipeline()` helper), not to defects in `src/econflow/`. Exactly one class of failure (the df_resid/adjusted-R² off-by-one) could not be resolved to either side with the evidence available and is reported as genuinely open, not swept into either the "stale fixture" or "regression" bucket by default.

**Classification:** Predominantly **B (stale artifact)** and one instance of **C-adjacent test/CLI-assumption defect** (the `_run_pipeline()` positional-argument bug is a bug in test infrastructure code, arguably its own minor case of **E (real software defect)** — it is broken code, just broken *test-support* code rather than product code). The df_resid/adjusted-R² item is **unclassified — insufficient evidence**, and should not be counted as either B or E until someone with access to the Sprint S1 change record settles it.

---

## 7. Repository Integrity Report — Summary Classification

| # | Finding | Classification |
|---|---|---|
| 1 | Dispatcher/diagnostics/pipeline_generic subsystem has zero git history at HEAD despite being described as "frozen" architecture | **A — repository corruption** |
| 2 | `my_test_study/` tracked-then-manually-deleted, deletion never committed, contradicts its own `.gitignore` rule | **A — repository corruption** |
| 3 | `tables/data_validation_report.json` — committed legacy artifact that regenerates and drifts on every pipeline run from repo root | **B — stale artifact** |
| 4 | All six `tests/integration/fixtures/baseline/*` files predate the source (`_diagnostics.py`) they check by ~1.5 days | **B — stale artifact** |
| 5 | `examples/getting_started/expected_outputs/diagnostics.csv` predates `_diagnostics.py` by ~33 hours (second, independent stale copy) | **B — stale artifact** |
| 6 | `expected_outputs/table_fe_investment.{csv,tex}` predate `pipeline_generic.py`'s label-lookup behavior by ~31 hours | **B — stale artifact** |
| 7 | `numerical_results.json` predates `dispatcher.py`/`pipeline_generic.py` by 12–13 hours (no observed numerical discrepancy yet, but same pattern) | **B — stale artifact** |
| 8 | PLUGIN_SDK.md: `rsq` vs. `rsquared` | **C — stale documentation** |
| 9 | PLUGIN_SDK.md: `EstimationResult` required-fields list omits 5 real fields | **C — stale documentation** |
| 10 | PLUGIN_SDK.md: `check` vs. `diagnostic_id` | **C — stale documentation** |
| 11 | PLUGIN_SDK.md vs. ARCHITECTURE_FREEZE_v1.md vs. source: three-way disagreement on `level` vocabulary | **C — stale documentation** |
| 12 | PLUGIN_SDK.md: `BaseDiagnostic.run()` documented signature doesn't match actual `**kwargs` signature | **C — stale documentation** |
| 13 | PLUGIN_SDK.md: `_not_applicable()` documented behavior (incl. nonexistent `status` field) doesn't match actual implementation | **C — stale documentation** |
| 14 | CHANGELOG.md has zero mentions of Architecture Freeze / Phase 5-6 / Sprint S1 anywhere in 612 lines | **C — stale documentation** (consequence of finding #1) |
| 15 | `test_pipeline_baseline.py` self-consistency test asserts stale raw-ID column convention, contradicting current pipeline output | **C — stale documentation (test-as-spec)** |
| 16 | `_run_pipeline()` helper in `test_pipeline_baseline.py` is dead code and independently broken (positional CLI arg that silently no-ops) | **E — real software defect** (in test infrastructure, not product code) |
| 17 | Durbin-Watson value discrepancy in fixture comparison | **B — stale artifact** (root cause; the source change itself is a deliberate improvement, confirmed correct) |
| 18 | Comparison-table column-header discrepancy in fixture comparison | **B — stale artifact** |
| 19 | `test_release_check.py` 21 failures under `pytest -n 2` | **Not classifiable under A–E** — test-harness concurrency artifact, not a repository property; recorded to prevent future misdiagnosis |
| 20 | df_resid/adjusted-R² off-by-one in live (non-fixture) unit tests | **Unclassified — insufficient evidence to place in B or E** |
| 21 | Dependency drift as a candidate explanation for any observed test failure | **Ruled out** — ✗ not present anywhere in this audit |
| 22 | Package/editable-install integrity | **No finding — PASS** |
| 23 | Core directory structure vs. documentation | **No finding — PASS** |

**Tally:** A = 2, B = 6, C = 7, D = 0 (explicitly ruled out), E = 1 confirmed + 1 unresolved, unclassifiable = 1.

---

### Repository Integrity Score: **58 / 100**

Rationale: package-level integrity and directory-level completeness are both clean (which prevents a lower score), but the two A-classification findings are structurally serious — a "frozen" architecture with no git commit backing it, and a tracked directory with unresolved, uncommitted deletions — and the volume of stale artifacts (6 separate B findings, all traceable to one missing regeneration step) combined with a documentation layer (PLUGIN_SDK.md, ARCHITECTURE_FREEZE_v1.md, CHANGELOG.md) that disagrees with source in at least seven distinct, independently-verified places pulls the score down substantially. Nothing found rises to a confirmed defect in the *scientific/estimation* logic itself — every traced numerical discrepancy resolved to stale comparison data, not incorrect computation — which is the main reason this isn't scored lower.

### Release Confidence: **34 / 100**

Rationale: this number is lower than the integrity score because release confidence has to account for what happens if 1.0 ships in the *current* state rather than what it would take to fix it. Shipping today would mean: releasing a "frozen" architecture that cannot be reproduced from a clean clone (finding #1), a changelog that omits the release's own headline work (#14), an SDK document that would actively mislead a third-party plugin author on six separate points (#8–13), and zero automated mechanism to detect the next time a fixture goes stale (#16, dead+broken regeneration helper) — meaning findings like #4–#7 will silently recur. None of this blocks correctness of the shipped numerical output as verified today, but it blocks the *auditability and reproducibility* guarantees that a 1.0 econometrics tool needs to credibly claim.

### Estimated Effort to Fully Repair the Repository

- **Git/commit hygiene (findings #1, #2, #14):** ~0.5–1 day. Stage and commit the working-tree state (with careful review, given the two-layer staged/unstaged split identified in §1), resolve or intentionally re-commit the `my_test_study/` deletion, and add a CHANGELOG entry for the work once committed. Mechanically simple; the only real cost is deciding what commit boundaries make sense for a week of previously-uncommitted work.
- **Fixture/artifact regeneration (findings #3–#7, #17, #18):** ~0.5 day once #16 is fixed. Fix `_run_pipeline()`'s CLI invocation (change the positional arg to `--config`), wire it into the test file (or a documented `make regenerate-fixtures` step), and re-run it to refresh all six baseline fixtures plus the `expected_outputs/` copies.
- **Documentation corrections (findings #8–#13, #15):** ~1 day. Six PLUGIN_SDK.md corrections are each small, mechanical edits once the correct field names/signatures are known (they are — this report cites them); the `level` vocabulary needs a single decision (pick one of info/warning/error/skip as canonical and make both docs match it) rather than three-way research.
- **Unresolved item (finding #20):** ~0.5–1 day of investigation to determine whether the df_resid/adjusted-R² change was intentional (check Sprint S1's own change notes/commits if they exist, or have the original author confirm) before it can be classified and closed.

**Total estimated repair effort: ~2.5–3.5 days** of focused work, assuming no new issues surface during the fixture regeneration or documentation pass. This is a repair-the-paperwork estimate, not a rewrite — no finding in this audit points to incorrect econometric computation in shipped source.
