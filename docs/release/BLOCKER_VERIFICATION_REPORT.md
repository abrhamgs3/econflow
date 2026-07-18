# Blocker Verification Report

**Purpose:** Independent re-verification of the three CRITICAL blockers reported in `docs/release/RELEASE_CHECKLIST_v1.0.md`, performed with the explicit premise that the prior audit could be wrong. Every finding below was reproduced from source or live execution in this session; nothing is carried forward from the prior report on trust.

**Date:** 2026-07-17

---

## Blocker 1 — Repository State

### Evidence

```
HEAD:   35f5926dded9cdea20da299052316abc273370e7
        2026-07-09 18:31:09 -0400
        "Sprint 11F: Fix evaluator-reported issues (F1/F3/F5/F6/F7/F8/F9/F10/F11)"
branch: main (no divergence from HEAD; not detached)

git status --short, by status code:
    426  MM   (modified in index, further modified in working tree)
     35  AM   (added to index, not yet committed; further modified in working tree)
     16   D   (deleted in working tree, not yet staged)
     10  ??   (untracked)
    487  total
```

Reproduced fresh this session with `git log -1`, `git status --short`, and `git branch -vv`.

**What is actually missing from git, precisely:** every commit dated after `35f5926` (2026-07-09) — i.e. the entire Architecture Freeze (`ARCHITECTURE_FREEZE_v1.md` dated 2026-07-10), the EstimationDispatcher migration (Phase 5/6, both dated 2026-07-10), Sprint S1/S2, and Release Sprints R1–R3 (dated 2026-07-13 through 2026-07-17) — has **zero corresponding commits**. Direct confirmation: `git show HEAD:src/econflow/estimation/dispatcher.py` returns `fatal: path ... exists on disk, but not in 'HEAD'`. This file is 355 lines and is the concrete implementation of the frozen `EstimationDispatcher` — central to the entire migration this repository's documentation describes — and it has never been committed.

**A refinement the prior report did not make:** "uncommitted" is not one uniform state. This session checked the git *index* (not just the working tree) and found two distinct layers:

1. **Staged but never committed.** `dispatcher.py` is fully present in the git index (`git ls-files --stage` shows blob `61f25aa6...`); `git diff --cached --stat` shows it as a clean 355-line addition; `git diff` (working tree vs. index) shows only a file-mode change (644→755, a mount/checkout artifact confirmed elsewhere in this session, not real content). The same is true of `pipeline_generic.py`'s Phase-5 rewiring (344 lines changed, fully staged, zero unstaged content diff) and most of the `AM`-status architecture/release documents and the `tests/integration/fixtures/baseline/*` fixtures. For these files, `git commit` alone (no `git add` needed) would capture them.
2. **Not even staged — real, additional, unstaged edits on top of an already-stale index.** `git diff --stat` (working tree vs. index, filtering out mode-only noise) shows genuine content diffs in `src/econflow/__init__.py` (53 lines), `src/econflow/exceptions.py` (112 lines), `src/econflow/estimation/_diagnostics.py` (308 lines), `src/econflow/estimation/base.py` (76 lines), `src/econflow/estimation/fixed_effects.py` (57 lines), `src/econflow/estimation/iv.py` (279 lines), `src/econflow/config/validator.py` (81 lines), `src/econflow/ingestion/validation.py`, `src/econflow/ingestion/__init__.py`, `src/econflow/config/__init__.py`, and three test files. For `__init__.py` specifically, `git diff --cached` shows the index holds an earlier version (the Phase-5 README/estimation-re-export update); this session's own C-2 fix (removing `AIProdError` from `__all__`, adding the PEP 562 `__getattr__`) is a further, wholly unstaged edit on top of that. A bare `git commit` would **not** capture these; `git add -A` is required first.

Ten files are untracked (`??`) — six release/investigation reports (including the checklist and this report's predecessor work) and four new `test_r1`/`test_r2`/`test_r3`/`test_sprint_s2` test modules.

### Root cause

Standard consequence of an extended body of work being developed entirely in a working tree — with disciplined `git add` staging for the bulk of it — but never reaching `git commit`. There is no evidence of data loss (everything needed to reconstruct the intended commit exists on disk, in the index, or both); this is a process gap, not a corruption.

### Impact

A version-control tag is a pointer to a commit. There is no commit containing this work, so there is nothing to tag `v1.0`. This blocks release by definition, independent of code quality.

### Verdict: **CONFIRMED**

### Recommended fix

`git add -A` (to capture the layer-2 unstaged edits), then commit in reviewable increments — e.g. one commit for the Architecture Freeze docs, one for the dispatcher/pipeline_generic migration, one for the exception-hierarchy/AIProdError/ValidationIssue API-freeze fixes, one for the new test modules — rather than a single monolithic commit, so the history remains reviewable.

### Estimated effort

Low (mechanical), but not zero: given the working tree mixes at least three distinct, log­ically separable bodies of work (Architecture Freeze/migration, API Freeze fixes, this session's own release-audit documents), a careless single `git add -A && git commit` would produce one undifferentiated commit. Splitting it properly is an hour of careful `git add -p`/path-scoped staging, not a multi-day task.

### Release impact

**Blocking.** Cannot be waived.

---

## Blocker 2 — Numerical Stability Test (`tests/integration/test_pipeline_baseline.py`)

The full 880-line file was read in this session (not re-summarized from the prior pass). This blocker required the deepest re-investigation, because the first explanation ("numeric pin drift") and even the second ("stale baseline fixture, needs investigation") both turned out to be incomplete.

### How the baseline is produced and compared — three distinct mechanisms coexist in this one file

1. **`pipeline_results` fixture (module-scoped, lines 148–174).** This is what backs the large majority of the file's tests (`TestCoefficients`, `TestGoodnessOfFit`, `TestCoefficientProperties`, and two of three tests in `TestDiagnostics`). Its own docstring states plainly: *"This fixture does NOT re-run the pipeline on disk — it re-estimates in-process using the same logic as pipeline_generic.py."* It calls `linearmodels.PooledOLS`/`PanelOLS` directly, with hardcoded parameters matching the original Phase-0 specification. This mechanism is self-contained and does not depend on any file on disk being fresh.
2. **Three file-comparison tests** (`TestDiagnostics::test_diagnostics_csv_matches_baseline`, `TestComparisonTableCSV::test_comparison_table_csv_matches_baseline`, `TestComparisonTableLaTeX::test_latex_matches_pipeline_output`) instead read whatever currently exists at `examples/getting_started/outputs/tables/*.csv`/`*.tex` and diff it against the frozen fixture files in `tests/integration/fixtures/baseline/`.
3. **A `_run_pipeline()` helper (lines 85–103)** exists, whose evident purpose is to regenerate those on-disk files fresh via `subprocess.run([sys.executable, "-m", "econflow.cli", "run", str(CONFIG_PATH), "--models", ..., "--outputs", ...])` before mechanism #2 runs.

### Does the helper actually regenerate outputs? No.

Two independent problems, both confirmed by direct reproduction this session:

- **`_run_pipeline()` is never called.** A search of the full file for call sites of `_run_pipeline(` finds only its own `def`. No fixture, no `setup_module`, no `autouse` fixture invokes it. It is dead code.
- **Even if it were called, it is itself broken.** `econflow run` (per `src/econflow/cli.py`, read in full this session) takes `config` exclusively as `--config`/`-c`; it has no positional parameter. `_run_pipeline()` passes `str(CONFIG_PATH)` as a bare positional argument. Reproduced directly this session: running that exact invocation (`python -m econflow.cli run examples/getting_started/config/config.yaml --models ... --outputs ...`) produces **no stdout, no stderr, and exit code 0** — a silent no-op, not a `RuntimeError` (the function's own error-handling only fires on non-zero exit, which never happens here).

### Is the failure a stale fixture or a scientific regression? Both — but not in the proportions first assumed, and for a specific, traceable reason in each case.

This session ran the pipeline itself correctly (`econflow run --config ... --models ... --outputs ...`, the working invocation form) to eliminate the freshness question, then re-ran the three file-comparison tests and diffed the regenerated files against the fixtures directly.

**Finding A — the earlier read of these failures was itself measuring stale files, not current code.** Before this session ran the pipeline, `test_diagnostics_csv_matches_baseline`'s failure showed the live Breusch-Pagan statistic as `82.2029` vs. baseline `65.228`. After this session generated a fresh `diagnostics.csv`, the live BP statistic is `65.228` — **identical to baseline.** The `82.2029` figure was an artifact of a stale file left on disk from an earlier, unrelated process (the exact provenance of that stale file was not traced further; it is not reproducible from current code). This is direct proof of the exact risk mechanism #2/#3 create.

**Finding B — after controlling for freshness, one genuine, well-documented, intentional methodology change remains: Durbin-Watson.** Fresh live diagnostics: `DW = [0.2076, 0.6845, 0.6850]` for pooled_ols/entity_fe/twoway_fe. Baseline fixture: `[0.3707, 0.9718, 0.9161]`. Traced to `src/econflow/estimation/_diagnostics.py::_diag_durbin_watson()` (read in full this session): the function implements **two formulas**, selected automatically based on whether panel entity information is available:
  - *Panel path (Bhargava, Franzini & Narendranathan 1982; used in production since Sprint S1):* `DW = Σᵢ Σₜ₌₂ (eᵢₜ − eᵢ,ₜ₋₁)² / Σᵢ Σₜ eᵢₜ²` — sums squared within-entity differences only, explicitly excluding the spurious "difference" between the last observation of one entity and the first of the next.
  - *Naive time-series path (the old, pre-Sprint-S1 behavior, and what both `test_pipeline_baseline.py::test_dw_statistic` at line 469–476 and the frozen `diagnostics.csv` fixture still use):* `DW = Σₜ (eₜ − eₜ₋₁)² / Σₜ eₜ²` over the pooled, undifferentiated residual vector — which, for an 11-entity panel, includes 10 meaningless cross-entity boundary terms in the numerator.

  The function's docstring cites the academic source explicitly and documents the change as deliberate. Because the naive formula sums extra (non-negative) boundary terms into the numerator, it necessarily produces a *larger* DW value than the panel formula — exactly the direction and rough magnitude observed. **This is a scientific improvement (correcting a methodologically inappropriate formula for panel data), not a regression, and the test/fixture pair that fails was never updated to reflect it.**

**Finding C — the "column labels differ" finding from the first pass was also a stale-file artifact, and the underlying code is correct by inspection, not merely by assumption.** After a fresh run, `table_fe_investment.csv`'s header row reads `Pooled OLS, Entity FE, Two-Way FE` — matching the human-readable `label:` fields in `examples/getting_started/config/models.yaml`. Traced to `src/econflow/pipeline_generic.py:230-231`: `id_to_label = {s["id"]: s.get("label", s["id"]) for s in model_specs}; col_names = [id_to_label.get(mid, mid) for mid in model_ids]` — this label-lookup is not a new or accidental behavior; it reads a field that has been present in `models.yaml` throughout. `ARCHITECTURE_FREEZE_v1.md` §3 F-3 (forbidden changes) names exactly four frozen formatting functions — `_stars()`, `_fmt_coef()`, `_fmt_se()`, `_fmt_r2()` — and `_build_comparison_table()`'s label lookup is not one of them, so this is not a forbidden-change violation either. **The frozen baseline fixture's own self-consistency test (`test_baseline_csv_has_three_model_columns`, line 540–543) asserts the *fixture itself* uses the raw lowercase IDs as column names — proving the fixture was authored to that older convention and simply predates (or was captured from a config without) `label:`-based headers.** The live code is very likely correct; the fixture is stale.

**Finding D — one further, small, genuinely unexplained discrepancy remains.** `SE: capital` for Entity FE: live `0.0500` vs. baseline `0.0501` — a difference in the fourth displayed decimal. This is consistent in direction and magnitude with the already-documented D3 finding (`docs/architecture/PHASE5B_NUMERICAL_EQUIVALENCE.md`: ~0.23% SE difference from a rank-0 demeaned constant column), but this session did not re-derive that specific arithmetic from first principles for this exact cell — it is flagged as *likely* the known D3 effect, not confirmed to that same standard as Findings B and C.

### Root-cause summary (layered, per the instruction not to stop at the first explanation)

| Layer | Explanation | Verdict |
|---|---|---|
| 1st (surface) | "Numeric pin drift" | Incomplete — true for one root cause (DW), not for the others |
| 2nd | "Stale baseline fixture" | Partially true, but conflated two different things |
| 3rd (actual) | (a) The test file's own freshness-guarantee mechanism is dead and broken, so an initial read reflects stale files, not current code. (b) Once freshness is controlled for: the DW discrepancy is a deliberate, documented, econometrically-justified methodology upgrade (naive pooled DW → BFN 1982 panel DW) that its own fixture/naive-formula test were never updated to match. (c) The column-label discrepancy is the frozen fixture being stale relative to a pre-existing, intentional label-lookup feature — not a code change at all. (d) One small SE rounding difference remains, plausibly but not confirmed to be the known D3 effect. | **Confirmed as the complete picture** |

### Impact

The freeze document's own named enforcement test for numerical/formatting stability (`ARCHITECTURE_FREEZE_v1.md` §2, invariant I-1) currently fails — but the underlying science is, on this session's evidence, more sound than the raw test output suggests. The real, actionable problems are: (1) a test-infrastructure gap (no guaranteed-fresh comparison), and (2) three fixture files that need deliberate reconciliation against known, intentional changes — not a hunt for a hidden regression.

### Verdict: **PARTIALLY CONFIRMED**

The blocker is real (the test fails; I-1 is not currently green) but the underlying premise in the original checklist — that this represented an open, uninvestigated scientific-correctness question — is superseded by this session's finding that the dominant cause (DW) is a known, deliberate, well-documented improvement, and a second cause (labels) is a stale fixture, not a code defect. Only the SE-rounding discrepancy remains a genuinely open, unconfirmed item.

### Recommended fix

1. Fix `_run_pipeline()` to call the CLI with `--config` (not a bare positional), and add an assertion that output was actually produced (given the observed silent-exit-0 failure mode) rather than trusting the return code alone.
2. Wire the fixed `_run_pipeline()` into a module-scoped `autouse` fixture so the three file-comparison tests always compare against freshly generated output.
3. Regenerate `tests/integration/fixtures/baseline/diagnostics.csv`, `comparison_table.csv`, and `comparison_table.tex` from a fresh run, and update `test_dw_statistic` (line 469–476) to use the same BFN panel formula `_diag_durbin_watson()` uses, so the in-process check and the file-based check test the same methodology.
4. Add a one-line note to `ARCHITECTURE_FREEZE_v1.md` or `PHASE5B_NUMERICAL_EQUIVALENCE.md` documenting the DW methodology change as an accepted, intentional deviation from the Phase 0 baseline, in the same style as the existing D3 entry.
5. Separately confirm the SE:capital 0.0500-vs-0.0501 cell against the D3 arithmetic.

### Estimated effort

Half a day: steps 1–3 are mechanical once diagnosed; step 5 requires redoing the D3-style derivation for this specific cell.

### Release impact

**Blocking until fixture reconciliation is done**, but with much lower scientific risk than the unqualified failure count suggested — this is closer to test/fixture maintenance debt than to an open correctness question.

---

## Blocker 3 — Plugin SDK Mismatch

`docs/sdk/PLUGIN_SDK.md` was compared section-by-section against the live source it documents: `src/econflow/estimation/result.py` (both dataclasses, read in full this session), `src/econflow/diagnostics/base.py` (read in full this session), and `docs/architecture/ARCHITECTURE_FREEZE_v1.md` §1.2/§1.3 (the frozen specification both are supposed to agree with).

### Every mismatch found

| # | PLUGIN_SDK.md says | Live source actually is | Classification |
|---|---|---|---|
| 1 | `EstimationResult.rsq: float \| None` (§2.3 dataclass, line 380; also in `fit()`'s docstring, line 240; and lines 559, 566, 2760 elsewhere in the document) | `EstimationResult.rsquared: float` (`result.py:159`, no default, required) — no field named `rsq` exists anywhere in the dataclass | **Documentation defect** |
| 2 | §2.3's documented `EstimationResult` "required fields" list: `params, std_err, pvalues, nobs, rsq, estimator_id` | Live dataclass's actual no-default (required) fields, in order: `estimator_id, estimator_name, params, std_err, conf_int, pvalues, nobs, ngroups, df_resid, rsquared, rsquared_adj` (`result.py:145-160`) — the documented list omits `estimator_name`, **`conf_int`** (a field the freeze document separately calls out with its own forbidden-change rule, F-2, for the field-vs-method distinction), `ngroups`, `df_resid`, and `rsquared_adj` entirely | **Documentation defect** (the `conf_int` omission is the most severe instance — a plugin author building `EstimationResult` from this snippet alone would hit a missing-required-argument error) |
| 3 | `DiagnosticResult.check: str` (§4.3, line 1490; also referenced in `BaseDiagnostic.run()`'s docstring, line 1426) | `DiagnosticResult.diagnostic_id: str` (`result.py:50`) — no field named `check` exists | **Documentation defect** |
| 4 | `DiagnosticResult.level: str = "info" \| "warn" \| "error"` (§4.3, line 1495; repeated in `BaseDiagnostic.run()`'s docstring, line 1440, and in `BaseEstimator.diagnostics()`'s docstring, line 284) | Grepped every `level=` assignment in `src/econflow/`: the values actually used at runtime are `"info"`, `"warning"` (full word, not `"warn"`), `"error"`, and `"skip"` — `"warn"` is never used anywhere in the codebase | **Documentation defect** (minor — one word short) |
| 5 | `BaseDiagnostic.run(self, result, data: pd.DataFrame \| None = None) -> DiagnosticResult` (§4.1, line 1403-1407) | `BaseDiagnostic.run(self, result: EstimationResult, **kwargs: Any) -> DiagnosticResult` (`diagnostics/base.py:84-89`) — no named `data` parameter; the real signature takes `**kwargs` | **Documentation defect** |
| 6 | `BaseDiagnostic._not_applicable()`: *"Return a DiagnosticResult with level="info" and status="skip""* (§4.1, line 1481) | Live implementation (`diagnostics/base.py:150-157`) constructs `DiagnosticResult(..., level="skip")` directly — there is no `status` field anywhere on `DiagnosticResult`, and the level used is `"skip"`, not `"info"` | **Documentation defect** |

**A finding about the freeze document itself, not just the SDK:** on mismatch #4, `ARCHITECTURE_FREEZE_v1.md` §1.3 independently claims the frozen vocabulary is `"info" \| "warn" \| "fail"` — which is *also* wrong (confirmed by the same grep: `"fail"` and `"warn"` appear zero times in `src/econflow/`). Neither document exactly matches source on this point; `PLUGIN_SDK.md`'s `"error"` happens to be closer to reality than `ARCHITECTURE_FREEZE_v1.md`'s `"fail"`, but both say `"warn"` where the code says `"warning"`. Per the standing rule that source is authoritative, the correct vocabulary to document going forward is `"info"`, `"warning"`, `"error"`, `"skip"`.

**Not found to be mismatched (checked, not assumed) this session:** `register_estimator` as the canonical decorator name (confirmed matches `estimation/registry.py`); `FigureBuilder`/`BaseRenderer` exports (previously corrected per `docs/release/DOCUMENTATION_VALIDATION.md` and independently re-confirmed present in `econflow.outputs.__all__` earlier this session); the entry-point auto-loading description; `IntegrityCheckResult`/`BaseIntegrityCheck` were not re-verified in this pass (time-boxed; flagged as not re-checked rather than assumed correct).

### Classification summary

All six confirmed mismatches are **documentation defects**, not API defects. In every case the live source is internally consistent, unambiguous, and (based on this session's test runs) functioning correctly; the problem is exclusively that `PLUGIN_SDK.md` describes an interface that does not match it. No evidence was found in this session of the live API itself being broken, inconsistent, or ambiguous.

### Root cause

`PLUGIN_SDK.md`'s `EstimationResult`/`DiagnosticResult` sections (§2.3, §4.1, §4.3) appear to predate the dataclasses' current shape — `rsq`→`rsquared` and `check`→`diagnostic_id` read like an early naming convention that was later revised in source without a corresponding sweep through the SDK document. The `conf_int` omission is consistent with the same story: `conf_int` is explicitly called out in `ARCHITECTURE_FREEZE_v1.md` as an easy-to-get-wrong field (it's a method on the underlying `linearmodels` object but a field on `EstimationResult`) — exactly the kind of field a documentation pass would need to add deliberately, and evidently didn't.

### Impact

Directly violates Architecture Freeze invariant I-8 ("a plugin written against PLUGIN_SDK.md v1.0 ... must continue to load, register, and execute correctly"). A plugin author who builds `EstimationResult(rsq=..., estimator_id=...)` per the documented snippet would fail with a missing-required-argument `TypeError` (for the five omitted required fields) compounded by an unexpected-keyword-argument `TypeError` (for `rsq`) — the plugin would not even construct, let alone run.

### Verdict: **CONFIRMED** (all six listed mismatches independently reproduced against source in this session; zero were found to be false positives)

### Recommended fix

Rewrite PLUGIN_SDK.md §2.3 and §4.3's dataclass listings to be copied directly from (or generated from) the live `result.py` dataclasses rather than hand-maintained, and add a regression test — parallel to the existing `test_consistency_regression.py` pattern — that imports the real dataclasses via `dataclasses.fields()` and asserts the SDK's documented field names are a subset of the real ones. This closes the class of defect permanently rather than fixing today's six instances only.

### Estimated effort

One day: the rewrite itself is small (two dataclass blocks plus the `run()`/`_not_applicable()` docstrings), but writing and validating the regression test that prevents recurrence is the larger share of the work.

### Release impact

**Blocking.** This is a direct, freshly-confirmed violation of a named Architecture Freeze invariant (I-8), not a stylistic nit.

---

## Release Readiness

### **NOT READY**

### Justification, from this session's re-verification only

- **Blocker 1 (repository state): CONFIRMED.** Unchanged from the original finding, with added precision (staged-vs-unstaged layering) that does not change the verdict — there is still no commit to tag.
- **Blocker 2 (numerical stability): PARTIALLY CONFIRMED.** The test genuinely fails today, so it remains blocking as a literal gate status. But the deep-dive materially changes the *risk* it represents: the dominant cause is a deliberate, well-documented econometric improvement (BFN panel Durbin-Watson) whose fixtures were never refreshed, not an unexplained numerical regression, and the "column label" finding turned out to indict the frozen fixture rather than the code. This lowers the scientific-correctness risk substantially, though the test-infrastructure gap it exposed (a freshness-guarantee mechanism that is both dead code and independently broken) is itself worth fixing regardless of the numeric question.
- **Blocker 3 (Plugin SDK): CONFIRMED**, and found to be broader than originally reported (six mismatches, not two) — but also more precisely scoped: it is purely a documentation defect, isolated to `PLUGIN_SDK.md`, with no evidence the underlying API is unstable or broken.

None of the three blockers turned out to be a false positive. One (Blocker 2) turned out to be less severe on the scientific-correctness axis than first reported, but no less blocking as a literal test-suite gate, and it surfaced an additional, independent finding (the broken/dead freshness-guarantee helper) that was not part of the original report at all. This is consistent with — and does not overturn — the prior checklist's overall NOT READY conclusion; it refines the reasoning behind it.

### What would change this decision

Fixing Blocker 1 is necessary but not sufficient by itself (there would be nothing to release safely — the release would still carry Blockers 2 and 3). Fixing Blocker 3 is close to a pure documentation change and could plausibly be turned around fastest. Blocker 2's mechanical fixes (steps 1–4 in that section) are also fast; only the SE-rounding item (step 5) requires further open investigation, and it is small enough in magnitude that it should not by itself gate a release once documented with the same rigor as the existing D3 entry.
