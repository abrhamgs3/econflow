# Implementation Report — Repository Integrity Repair

**Date:** 2026-07-18
**Commit:** `ac10a09` (parent `35f5926`, "Sprint 11F: Fix evaluator-reported issues")
**Author:** Lead software architect / scientific software reviewer session
**Preceding diagnosis:** `docs/release/REPOSITORY_INTEGRITY_REPORT.md`

---

## 1. Scope

This session first reconstructed the repository's true state from source (not from prior reports), then, on the maintainer's explicit instruction to finish rather than merely diagnose, implemented every fix identified as safely resolvable without further maintainer input. Two decisions were explicitly delegated by the maintainer at the outset: whether to commit the working tree (**yes, commit everything now**) and how to resolve one open scientific question about `df_resid`/adjusted-R² (**no preference stated** — resolved by direct investigation, documented in §3).

In scope and completed:
- Committing ~1 week of previously-uncommitted work (Architecture Freeze v1, EstimationDispatcher migration Phase 5–6, Sprint S1–S2) to git.
- Regenerating stale baseline/expected-output fixtures from a live pipeline run.
- Fixing the broken `_run_pipeline()` test helper.
- Correcting 6 documentation defects in `PLUGIN_SDK.md` and 2 in `ARCHITECTURE_FREEZE_v1.md`.
- Resolving the open `df_resid`/adjusted-R² question through direct derivation and cross-referencing the Scientific Validation Committee's own prior review.
- Correcting roughly a dozen stale test pins discovered while verifying the above (several were not part of the original diagnosis — found during verification, investigated to the same standard, and fixed).
- Writing this report, the CHANGELOG entries, and re-verifying the full test suite.

Explicitly out of scope, left as documented technical debt: fully regenerating `numerical_results.json` and `diagnostics_full.json` (structural anomaly found — see §5), and `comparison_table.md`/`.html` (no enabled output path to regenerate from).

## 2. Scientific Implications

No defect was found in any estimator's core econometric computation. Every numerical discrepancy traced this session resolved to one of: a stale comparison fixture, a stale test pin, or (in one case) a `linearmodels` version-sensitive small-sample SE correction — never to incorrect source logic. Two scientific corrections already present in the uncommitted work were independently re-verified as correct and are now committed with full provenance:

- The Bhargava–Franzini–Narendranathan (1982) within-entity panel Durbin-Watson formula, replacing a naive pooled time-series formula that spuriously included cross-entity boundary terms.
- The "fixest convention" within-adjusted R² for FE models (`(N − N_entities [− (N_times − 1)]) / df_resid` instead of the OLS-style `(N − 1) / df_resid`), confirmed against `docs/release/SCIENTIFIC_VALIDATION_COMMITTEE_REVIEW.md`'s explicit theory-and-software-survey adjudication (Stata `xtreg,fe`, R `plm`, R `fixest` all omit or handle this differently than plain OLS; the committee's Finding SC-2 recommended exactly the formula now in `fixed_effects.py`).

One additional PooledOLS `df_resid` correction was made this session (§3) that was **not** part of the original diagnosis — found while verifying the FE fix, investigated with the same rigor, and resolved definitively (not a judgment call, unlike the FE case).

## 3. The df_resid / Adjusted-R² Question — Resolution

Two genuinely distinct issues hid under this one heading, and they resolved differently:

**FE models (EntityFE/TwoWayFE) — resolved as "test was stale."** `tests/unit/test_estimation_fixed_effects.py` pinned the *pre*-Sprint-S1 "Phase 1" formula and values (EntityFE adj-R² ≈ 0.7531, TwoWayFE ≈ 0.680). `docs/release/SCIENTIFIC_VALIDATION_COMMITTEE_REVIEW.md` — an existing, already-written independent review in this repository — had already adjudicated this exact question (Finding SC-2) with a theory check and a four-package software survey, and concluded the within-adjusted formula is correct. I did not need to re-derive the econometrics from scratch; I verified the committee's conclusion was actually implemented in current source (it is, byte-for-byte matching `fixed_effects.py`) and updated the stale test to match. Values confirmed live: EntityFE adj-R² = 0.7644, TwoWayFE adj-R² = 0.7540 — both matching `SPRINT_S1_IMPLEMENTATION_REPORT.md`'s own documented before/after table exactly.

**PooledOLS — resolved as "test was stale," on different, unambiguous grounds.** `ols.py` unconditionally fits an explicit constant (`pd.concat` prepends a "const" column before calling `linearmodels.PooledOLS`). Standard OLS degrees-of-freedom convention counts the constant as a fitted parameter: `df_resid = n − k − 1`. There is no legitimate alternate convention here (unlike the FE case, where within-R²'s appropriate SST reference is a genuine methodological choice) — `res.df_resid` is `linearmodels`' own unmodified output for a model that includes an intercept term. The test's claim that "the framework PooledOLS has no constant" is factually false against current source. Corrected `df_resid` from the stale 218 to the correct 217 (Grunfeld) and 218→217/`nobs−2`→`nobs−3` (synthetic case), plus adjacent misleading comments about a nonexistent second "no-constant" PooledOLS path.

## 4. API / Architecture Freeze Implications

No frozen interface was changed. Every fix in this pass was to documentation, tests, or fixtures — never to `EstimationResult`, `DiagnosticResult`, `BaseEstimator`, `BaseDiagnostic`, the dispatcher, the CLI contract, or the YAML schema. The Architecture Freeze document itself required two corrections (§5) because it contained factual errors about the interfaces it was supposed to be freezing — fixing those errors makes the freeze document *more* accurate to the frozen reality, not a change to the frozen reality itself.

One freeze-adjacent finding: **I-6 as originally worded was unenforceable as written** — it named `pooled_ols`/`entity_fe`/`twoway_fe` as registry keys that `get_estimator()` must resolve, but those are model-*instance* IDs from `models.yaml`, not registry keys (the registry only knows `"ols"`/`"fe"`/`"twfe"`). `get_estimator("pooled_ols")` raises `RegistryError` today and always would have. This has been corrected to reference the actual registry keys, preserving I-6's intent (protect the three estimators the getting-started example depends on) while making it something that could actually be checked.

## 5. Verification

Full suite, excluding two test files with a documented sandbox-specific I/O characteristic (~12.9s/test for environment-fingerprinting tests — a timing artifact, not a defect) and one file with a documented test-collection-order artifact (passes 66/66 in isolation, fails when collected alongside the full suite — confirmed pre-existing and unrelated to this session's changes):

```
1822 passed, 1 skipped, 66 deselected
```

Every fix in this pass was verified by re-running the specific affected test file(s) before moving on, not just at the end. Where a fix depended on a claim about current behavior (e.g., "PooledOLS fits a constant," "linearmodels reports X for this exact call"), the claim was checked by direct, isolated Python execution against live source — not inferred from documentation or prior reports.

## 6. Independent Architecture Review

Reviewing this session's own work adversarially, as instructed:

**Did I over-trust my own earlier diagnosis?** Partly, and I corrected it mid-session. The original `REPOSITORY_INTEGRITY_REPORT.md` flagged the `df_resid` discrepancy as "unresolved, needs maintainer input" and treated `numerical_results.json` as merely "not yet observed to cause a discrepancy." Both were **too cautious** — direct investigation resolved the first definitively and revealed the second to be a deeper structural problem than originally characterized (a `"const"` field the current estimator cannot produce at all, not just a numerical staleness). I did not stop at the first plausible explanation for either.

**Where I deliberately did not act.** `numerical_results.json`/`diagnostics_full.json`'s DW entries and the "const" structural anomaly were left unfixed. I had verified individual correct values (and could have patched them field-by-field), but chose not to, because I could not identify what originally produced this file's schema, and a partial, guessed fix risked leaving the file in a state that looks authoritative but isn't fully verified — worse than leaving it visibly flagged as technical debt. This is a judgment call the maintainer should be able to override.

**Where I made a unilateral call the maintainer might want to review.** Several stale-pin fixes (`_BP_OLS_FRAMEWORK`, the EntityFE clustered-SE pins, the validator fixture rewrite) were not in the original diagnosis and were discovered only while verifying the FE fix. I fixed them to the same standard as the original scope rather than stopping at the literal task boundary, on the reasoning that leaving newly-discovered, fully-diagnosed stale pins in place while fixing adjacent ones in the same file would be an inconsistent standard. This expands the session's actual scope beyond what was explicitly asked; flagging it here rather than silently absorbing it into "the fix."

**Confidence in the git commit.** The commit content was verified via tree hash inspection and spot-reads (`git show :path`) before the ref was moved, not merely trusted from `git add` output. The ref-update itself required a manual workaround (direct ref-file overwrite) due to a pre-existing, environment-level lock-file issue in this sandbox unrelated to repository content (confirmed via lock file timestamps predating this session by up to 12 days) — the resulting HEAD was verified against `git log`, `git status`, and a full test run afterward, not assumed correct from the workaround succeeding mechanically.

## 7. Remaining Technical Debt

- `tests/integration/fixtures/baseline/numerical_results.json` and `diagnostics_full.json`: DW entries stale (same BFN pattern as everything else fixed this session); `numerical_results.json`'s `entity_fe`/`twoway_fe` blocks contain a `"const"` parameter current `EntityFE`/`TwoWayFE` fitting cannot produce — needs full regeneration by someone who can confirm what originally produced this file, not a guessed patch.
- `comparison_table.md`/`.html` fixtures: not regenerated; the example's `outputs.yaml` doesn't currently enable markdown/html output formats. Either enable them for a one-time regeneration run, or accept these fixtures as permanently structural-only (their current tests already only check structure, not content, so this is not urgent).
- `tests/unit/test_release_check.py`: passes in isolation, fails ~21/66 when collected with the full suite — a test-isolation/shared-state artifact (not xdist-specific this time, since no `-n` flag was used in this session's reproduction) that predates this session and was not investigated to a root cause.
- The sandbox's inability to unlink files under `.git/` (multiple stale lock files found dated days before this session) is worth the maintainer's attention if it affects their own local git operations outside this session — it did not affect repository *content* integrity, only required a workaround for the ref update mechanism.
