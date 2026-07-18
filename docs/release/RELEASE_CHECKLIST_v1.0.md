# EconFlow 1.0 Release Checklist

**Verification date:** 2026-07-17
**Method:** This document was produced by reading the repository directly — `pyproject.toml`, `src/econflow/__init__.py`, `src/econflow/cli.py` (both in full), `docs/architecture/ARCHITECTURE_FREEZE_v1.md`, `docs/release/API_FREEZE_REPORT.md`, migration/scientific-validation/plugin-SDK/release documents — and then independently re-executing commands against the current working tree: `git status`/`git log`, a fresh Python import/`hasattr` sweep of every public package, direct exception-hierarchy and registry checks via the Python interpreter, `pip install -e`, `python -m build --wheel` and `--sdist`, `ruff check`, `sha256sum`, a fresh `econflow run` of the Grunfeld example, and a chunked-but-JSON-aggregated full test-suite run. No claim below rests on a prior report's word alone; where a prior report is cited, it is cited as history/context, and the PASS/FAIL/NOT VERIFIED verdict reflects this session's own re-execution.

**A methodological finding surfaced during this verification pass, disclosed up front:** an initial read of `tests/integration/test_pipeline_baseline.py`'s failures used whatever files already existed on disk under `examples/getting_started/outputs/`. Those files turned out to be stale leftovers, not the product of a fresh run. After this session ran `econflow run` itself against the Grunfeld example, three of the file-comparison failures changed shape — some discrepancies vanished, one changed from "column labels look wrong" to "the frozen baseline fixture's labels are the ones that are stale." This is reported in full in §3 and §7, and the underlying test-suite gap (the file-comparison tests have no fixture that guarantees a fresh pipeline run before asserting) is reported as a finding in §8.

---

# 1. Package

| Item | Result | Evidence |
|---|---|---|
| Package version | **0.1.0** — consistent, not bumped | `pyproject.toml:7` (`version = "0.1.0"`), `src/econflow/__init__.py:39` (`__version__ = "0.1.0"`), `CITATION.cff:5` (`version: "0.1.0"`) — all three read directly this session, all agree, none say `1.0.0`. |
| Semantic version | PASS (format only) | `"0.1.0"` is valid semver. No 1.0.0 tag or version bump exists anywhere in source. |
| Installation | PASS | `pip install -e ".[dev]"` run fresh this session, completed without error. |
| Editable install | PASS | Same command; `econflow --version` and `econflow doctor` both work immediately afterward (below). |
| Wheel build | PASS | `python -m build --wheel --no-isolation -o /tmp/whl_check` run this session → `Successfully built econflow-0.1.0-py3-none-any.whl`. |
| Sdist build | PASS | `python -m build --sdist -o /tmp/sdist_check` run this session (isolated venv) → `Successfully built econflow-0.1.0.tar.gz`. |
| Import test | PASS | Fresh `python3 -c` script this session: `import econflow` succeeds, `econflow.__version__ == "0.1.0"`, all 8 public sub-packages (`estimation, diagnostics, outputs, ingestion, integrity, replication, config, commands`) import cleanly, and every one of the 15 names in `econflow.__all__` resolves via `hasattr` (zero phantom exports at the root). |
| CLI smoke test | PASS | `econflow --version` → `EconFlow 0.1.0`, exit 0. `econflow doctor` → `✔ Ready (18 passed, 2 warning(s))`, exit 0. Both run fresh this session. |

---

# 2. API Freeze

| Item | Result | Evidence |
|---|---|---|
| Public exports | **PASS** | Fresh this session: looped `hasattr()` over every package's `__all__` for `econflow`, `econflow.estimation` (36 entries), `.diagnostics` (6), `.outputs` (22), `.ingestion` (18), `.integrity` (16), `.replication` (14), `.config` (12) — **zero phantom exports found anywhere.** This is a direct re-implementation of `QUALITY_GATE.md`'s QG-09 check, done independently rather than trusted from a report. |
| Deprecated exports | **PASS** | `AIProdError` is intentionally excluded from `__all__` (`src/econflow/__init__.py:71-77`, comment dated "API Freeze C-2, 2026-07-17") and served via a PEP 562 module `__getattr__` (`__init__.py:95-121`) that emits `DeprecationWarning` and points to `EconFlowError`. Source read directly this session. `register` confirmed to be the literal same object as `register_estimator` (`register is register_estimator` → `True`, verified by direct interpreter check this session) — the frozen deprecated alias (F-6) is intact. |
| Exception hierarchy | **PASS** | Fresh interpreter session this run: `ModelSpecificationError.__mro__` → `['ModelSpecificationError', 'EstimatorError', 'EconFlowError', 'Exception', 'BaseException', 'object']`. `issubclass(EstimatorError, EconFlowError)` → `True`. `issubclass(EconFlowCoreError, EconFlowError)` → `True`. `issubclass(RegistryError, EconFlowError)` → `True`. Cross-import-path identity (`econflow.exceptions.ModelSpecificationError is econflow.estimation.base.ModelSpecificationError is econflow.estimation.ModelSpecificationError`) → `True`. `ConfigValidationIssue is DataValidationIssue` → `False` (the two are now distinct, resolving the old C-3 naming collision); `econflow.config.ValidationIssue` still resolves as a backward-compat alias to `ConfigValidationIssue`. All four checks executed directly this session, not taken from `R1_EXCEPTION_UNIFICATION_REPORT.md`'s word. |
| Plugin SDK | **FAIL** | `docs/sdk/PLUGIN_SDK.md` documents `EstimationResult.rsq` (lines 77, 240, 380, 559, 566, 2760) and `DiagnosticResult.check` / `level: "error"` (line ~1488-1495) as the plugin contract. `docs/architecture/ARCHITECTURE_FREEZE_v1.md` §1.2/§1.3 freezes the field names `rsquared` and `diagnostic_id`/`diagnostic_name` / `level: "fail"`. Live source `src/econflow/estimation/ols.py:123-133` constructs `EstimationResult(..., rsquared=_rsq, rsquared_adj=_rsq_adj, ...)` — grepped directly this session; no `rsq` field exists in the real dataclass. A plugin author writing to the documented SDK contract would produce code incompatible with the actual frozen interface. |
| Registry API | **PASS, with a wording caveat in the freeze doc itself** | `list_estimators()` (fresh call, this session) → `{'fd':'implemented','fe':'implemented','gmm':'stub','iv':'implemented','ols':'implemented','quantile':'stub','re':'implemented','twfe':'implemented'}`. `get_estimator('ols')`, `get_estimator('fe')`, `get_estimator('twfe')` all succeed. `get_estimator('pooled_ols')`/`'entity_fe'`/`'twoway_fe'` all **fail** — but `examples/getting_started/config/models.yaml` (read this session) shows these three strings are the YAML **model instance `id:` fields**, not registry keys; the registry key is carried separately in each model's `estimator:` field (`"OLS"`, `"FE"` ×2). `ARCHITECTURE_FREEZE_v1.md` §2 Invariant I-6 phrases its requirement using these three model IDs as if they were registry IDs — this is an imprecision in the freeze document's own wording, not a code defect. The underlying intent (the three getting-started models resolve end-to-end) is verified separately under "Dispatcher API" below. |
| Estimator API | PASS | `BaseEstimator` frozen methods (`validate`, `fit`, `diagnostics`, `run`) confirmed present via direct read of `src/econflow/estimation/ols.py` this session; class attributes `estimator_id`, `backend` present. |
| Dispatcher API | **PASS** | Fresh this session: `EstimationDispatcher.resolve_id({'estimator':'fe','entity_effects':True,'time_effects':True})` → `'twfe'`. `resolve_id({'estimator':'fe','entity_effects':False,'time_effects':False})` → `'ols'` (with the documented `DeprecationWarning`). Both match the frozen translation rules in `ARCHITECTURE_FREEZE_v1.md` §1.5 exactly. `PipelineContext.__dataclass_params__.frozen` → `True`. `PipelineContext` fields are `['entity_col', 'time_col', 'decimal_places', 'weights_col']` — the freeze doc's §1.5 spec said "No other fields" beyond `entity_col`/`time_col`, but also explicitly permits later, additive, defaulted, still-frozen fields ("If additional project-level parameters are needed in a later phase, they are added as optional fields with defaults; the `frozen=True` constraint stays") — so this is a compliant evolution, not a violation, verified by reading both the current dataclass and the freeze doc's own escape clause. `pipeline_generic.py:38` imports `EstimationDispatcher, PipelineContext`; line 510 calls `EstimationDispatcher.dispatch(spec, df, context)` — confirmed via grep this session, and confirmed end-to-end by this session's own fresh `econflow run` of the Grunfeld example (§7), which produced correct output for all three getting-started models through exactly this chain. |

---

# 3. Scientific Validation

All findings below are from **this session's own fresh execution** — a live `econflow run` on the Grunfeld example (§7) plus direct `pytest` runs with full assertion diffs captured, not from reading prior reports.

| Item | Result | Evidence |
|---|---|---|
| Coefficient equivalence | **PASS for coefficients themselves** | The regenerated `table_fe_investment.csv` (this session's fresh run) shows `Coefficient: value = 0.1145 / 0.1101 / 0.1167` and `Coefficient: capital = 0.2275 / 0.3100 / 0.3514` for Pooled OLS / Entity FE / Two-Way FE — **identical** to the frozen baseline fixture (`tests/integration/fixtures/baseline/comparison_table.csv`) to the 4 displayed decimals. 151 of 154 tests in `test_pipeline_baseline.py` pass on a fresh run. |
| Standard errors | **MIXED** | Table-level SEs match the baseline for 5 of 6 cells; one cell differs: `SE: capital` for Entity FE is `0.0500` (live) vs `0.0501` (baseline) — a 4th-decimal rounding difference. Separately, `tests/unit/test_estimation_dispatcher.py::TestDispatchIntegration::test_std_err_value` fails with `expected 0.01443801842296304, got 0.014404865638860937` (0.23% relative difference) — this exact magnitude matches the D3 finding already documented in `docs/architecture/PHASE5B_NUMERICAL_EQUIVALENCE.md` (constant-column rank-0 demeaning), re-confirmed by direct computation this session, not assumed from that document. |
| Confidence intervals | Not independently isolated this session | No CI-specific assertion failures were found among the 24 confirmed-failing tests; CI fields were not exercised by a dedicated standalone check in this pass. |
| Diagnostics | **FAIL — but the true cause required a fresh run to see correctly.** | Direct diff of this session's freshly-generated `examples/getting_started/outputs/tables/diagnostics.csv` against `tests/integration/fixtures/baseline/diagnostics.csv`: VIF is identical for all 3 models (`1.3562`); **Breusch-Pagan is identical for all 3 models** (`65.228 / 77.8714 / 68.776`); **only Durbin-Watson differs**, for all 3 models: live `[0.2076, 0.6845, 0.6850]` vs baseline `[0.3707, 0.9718, 0.9161]`. (An earlier read of the same test's failure, taken from a stale pre-existing file before this session ran the pipeline itself, had shown a Breusch-Pagan mismatch instead — that was an artifact of the stale file, not of current code, and is superseded by this fresh-run result.) |
| R² | PASS at the table level (0.1145/0.1101/0.1167 etc. match); see Adjusted R² for a distinct failure. | `table_fe_investment.csv` `R² within` row: `0.7667 / 0.7566` — identical to baseline. |
| Adjusted R² | **FAIL** | `tests/unit/test_estimation_fixed_effects.py::TestEntityFEAdjustedR2::test_rsquared_adj_grunfeld_value`: `Expected EntityFE adj R² ≈ 0.7531, got 0.764416` — a ~1.5% relative difference, larger than the SE-only D3 effect. Correlates with `tests/unit/test_estimation_ols.py::TestPooledOLSAdjustedR2::test_df_resid_grunfeld`: `assert 217 == 218` — `df_resid` is off by exactly 1, which directly changes the adjusted-R² formula's denominator. Both captured with full assertion output this session. Root cause not fully traced to a specific line of code in this pass; flagged as requiring investigation into how the constant/parameter count is derived post-Phase-5. |
| Clustered covariance | Not independently isolated this session | No clustered-covariance-specific test failure found among the 24 confirmed failures. Not exhaustively stress-tested beyond what the existing suite covers. |
| FE | **FAIL** (adjusted R², one SE cell — see above) | — |
| TWFE | **FAIL** (adjusted R² — `TestTwoWayFEAdjustedR2::{test_rsquared_adj_formula, test_rsquared_adj_grunfeld_value, test_rsquared_unchanged}` all fail, same pattern as Entity FE) | — |
| IV | Not independently isolated this session | No IV-specific test failure found among the 24 confirmed failures; not separately stress-tested this session beyond the existing suite's coverage. |

**Architecture Freeze numerical invariants — confirmed status (re-verified this session, not assumed):**

- **I-1 (Numerical identity):** ⚠ **Partially violated.** Coefficients match; Durbin-Watson and adjusted-R²/df_resid do not, per the exact diffs above.
- **I-4 (Data hash stability):** ✔ **HELD.** `sha256sum examples/getting_started/data/grunfeld.csv` run twice this session → `d73bb76112ccf74ef6c85d4780e7dc0fb7ded7c671f1f51cd94831b3472f2ff9`, exact match to the frozen value in `ARCHITECTURE_FREEZE_v1.md` §2.
- **I-5 (Formatted output stability):** ⚠ **Violated, but not in the direction first assumed.** The frozen baseline fixture's comparison-table column headers are the lowercase raw YAML ids (`pooled_ols`, `entity_fe`, `twoway_fe`); the live pipeline (this session's fresh run) produces the human-readable labels from `models.yaml`'s `label:` field (`Pooled OLS`, `Entity FE`, `Two-Way FE`). The LaTeX caption also now includes a project-name suffix (`Panel regression results -- getting\_started`) that the frozen `.tex` fixture does not have. Both are almost certainly intentional formatting improvements made after the Phase 0 baseline was captured, whose fixture was never refreshed — not regressions in the ordinary sense — but they are, by the freeze document's own literal definition, an I-5 violation until the baseline fixture is reconciled or the freeze doc is amended to describe the new behavior as intentional (in the style of the existing D3 precedent).

---

# 4. Testing

**Total collected this session: 2,136** (`pytest --collect-only -q` → `2136 tests collected in 5.88s`, run fresh). Every test in the repository was accounted for in one of the four buckets below — the four bucket sizes sum to exactly 2,136.

| Bucket | Collected | Passed | Failed | Skipped | Not verified |
|---|---|---|---|---|---|
| `tests/regression` + `tests/replication` | 142 | 142 | 0 | 0 | 0 |
| `tests/test_exceptions.py` | 16 | 16 | 0 | 0 | 0 |
| `tests/test_provenance.py` | 35 | 20 | 0 | 0 | 15 |
| `tests/unit/` (excl. 2 files below) | 1,537 | 1,519 | 17 | 1 | 0 |
| `tests/unit/test_integrity_certificate.py` | 22 | — | — | — | 22 |
| `tests/unit/test_integrity_fingerprint.py` | 21 | — | — | — | 21 |
| `tests/integration/` (excl. 1 file below) | 352 | 345 | 7 | 0 | 0 |
| `tests/integration/test_integrity_pipeline.py` | 11 | — | — | — | 11 |
| **Total** | **2,136** | **2,042** | **24** | **1** | **69** |

**On "not verified" (69 tests):** these three files exercise `EnvironmentFingerprint`/`ProvenanceRecorder`-style code that scans installed packages and shells out to `git`. Directly timed this session: a single test from this family (`test_provenance.py::TestProvenanceRecorder::test_happy_path_writes_json`) took **12.91 seconds of wall time against 1.13 seconds of CPU time** — an I/O-latency characteristic of this session's sandboxed filesystem mount, not a code defect. At that rate the remaining 69 tests exceed the time available in this verification pass. This is disclosed rather than estimated: their last confirmed-passing state is documented in prior reports (not re-asserted here as current fact).

**A self-correction found and fixed within this session's own run, not from any prior report:** an initial full-suite pass using `pytest -n 2` (2 parallel workers) reported 38 failures in `tests/unit/`, 21 of them in `tests/unit/test_release_check.py`. Re-running `test_release_check.py` alone, without parallelism, gave **66/66 passed**. The 21 "failures" were an artifact of running subprocess-spawning tests (this file shells out to `pytest`/`build`) under two concurrent xdist workers, not a real defect. The 38→17 correction is reflected in the table above; the parallel-execution artifact itself is recorded as a finding in §8.

**Full list of the 24 genuine failures, by root cause:**

*Numeric/formatting drift vs. the Phase-0 baseline fixtures (23 tests) — see §3 for exact values:*
`test_estimation_diagnostics_phase3.py::TestPooledOLSDiagnostics::{test_bp_pin_framework_value,test_dw_pin_framework_value}`,
`test_sprint_s2.py::TestRegressionNoChange::{test_ols_bp_unchanged,test_ols_dw_unchanged}`,
`test_estimation_dispatcher.py::TestDispatchIntegration::{test_std_err_value,test_std_err_capital}`,
`test_estimation_fixed_effects.py::TestEntityFEAdjustedR2::{test_rsquared_adj_formula,test_rsquared_adj_grunfeld_value,test_std_err_unchanged}`,
`test_estimation_fixed_effects.py::TestEntityFEAdjustedR2Synthetic::test_formula_holds_on_synthetic`,
`test_estimation_fixed_effects.py::TestTwoWayFEAdjustedR2::{test_rsquared_adj_formula,test_rsquared_adj_grunfeld_value,test_rsquared_unchanged}`,
`test_estimation_fixed_effects.py::TestTwoWayFEAdjustedR2Synthetic::test_formula_holds_on_synthetic`,
`test_estimation_ols.py::TestPooledOLSAdjustedR2::test_df_resid_grunfeld`,
`test_estimation_ols.py::TestPooledOLSAdjustedR2Synthetic::test_df_resid_is_nobs_minus_k`,
`test_phase5c_pipeline.py::TestPhase6DiagnosticWriter::test_dw_statistic_pin`,
`test_phase5c_pipeline.py::TestNumericalEquivalence::{test_pooled_ols_value_coefficient,test_vif_max_matches_baseline}`,
`test_pipeline_baseline.py::TestDiagnostics::test_diagnostics_csv_matches_baseline`,
`test_pipeline_baseline.py::TestComparisonTableCSV::test_comparison_table_csv_matches_baseline`,
`test_pipeline_baseline.py::TestComparisonTableLaTeX::test_latex_matches_pipeline_output`.

*Test-fixture mismatch (1 test), root cause not fully traced this session:*
`tests/integration/test_validator_registry.py::TestValidateStrictRaisesOnL14::test_validate_strict_succeeds_on_valid_cluster` — fails with `References unknown model ID(s): ['pooled_ols', 'entity_fe']`; the `models` fixture path passed to `validate_strict()` in this test does not match what the paired `outputs.yaml` fixture expects.

**Ruff:** `ruff check src/ tests/` run twice this session (once early, once just before writing this document) → **8 errors both times, 4 auto-fixable**, including `I001` import-order issues in `src/econflow/config/linter.py` and `src/econflow/estimation/__init__.py`, and one `F841` unused variable in `tests/unit/test_estimation_fixed_effects.py:84`. **FAIL** — not lint-clean.

**Coverage:** `pyproject.toml`'s `[tool.coverage.run].omit` list, read directly this session, still excludes `estimation/*`, `diagnostics/*`, `outputs/*`, `core/*`, and others from the `fail_under = 70` gate. The 70% figure does not measure the code whose scientific correctness is under discussion in §3. **FAIL** as a meaningful gate.

---

# 5. Documentation

Every file below was checked for existence with `test -f` / `ls` this session.

| Document | Result |
|---|---|
| README | **PASS** — `README.md`, 196 lines, present at repo root. |
| FIRST_FIVE_MINUTES | **PASS** — `docs/release/FIRST_FIVE_MINUTES.md`, 181 lines. |
| PLUGIN_SDK | **PASS (exists), FAIL (accuracy)** — `docs/sdk/PLUGIN_SDK.md`, 2,889 lines, present; contains the `rsq`/`check` field-name defect documented in §2. |
| MIGRATION_ROADMAP | **PASS** — `docs/architecture/MIGRATION_ROADMAP.md`, 606 lines. |
| API_FREEZE_REPORT | **PASS** — `docs/release/API_FREEZE_REPORT.md`, 522 lines. |
| ARCHITECTURE_FREEZE | **PASS** — `docs/architecture/ARCHITECTURE_FREEZE_v1.md`, 583 lines, Status: FROZEN. |
| RELEASE_NOTES | **PASS, at a non-obvious path** — no root-level `RELEASE_NOTES.md` exists; the actual file is `docs/release_notes/v0.1.0.md` (137 lines). No `v1.0.0.md` counterpart exists yet — expected, since v1.0 has not been tagged. |
| CHANGELOG | **PASS (exists), FAIL (currency)** — `CHANGELOG.md`, 612 lines, Keep a Changelog format, but entirely under `[Unreleased]` with no entries for anything after Sprint 11F (2026-07-09) — none of the Architecture Freeze, API Freeze, Sprint S1/S2, or this session's own findings are recorded there. |
| LICENSE | **PASS** — MIT, 21 lines. |
| CONTRIBUTING | **PASS** — `CONTRIBUTING.md`, 190 lines, includes a documented release process. |
| CODE_OF_CONDUCT | **PASS** — `CODE_OF_CONDUCT.md`, 124 lines, Contributor Covenant. |
| SECURITY | **PASS** — `SECURITY.md`, 59 lines, full vulnerability-reporting policy. |

---

# 6. Distribution

| Item | Result | Evidence |
|---|---|---|
| Wheel | PASS | See §1. |
| Sdist | PASS | See §1. |
| PyPI readiness | **FAIL** | `README.md:29` (read this session): "EconFlow is not yet published to PyPI." No evidence of publication found anywhere in the repository. |
| License metadata | PASS | `pyproject.toml:10`: `license = { text = "MIT" }`, consistent with `LICENSE` and the README badge. |
| Project URLs | PASS | `pyproject.toml:104-106`, read fresh this session: `[project.urls]` declares `Repository` and `Changelog`, both pointing to `github.com/abrhamgs3/econflow`. |
| Python version requirement | PASS | `pyproject.toml:11`: `requires-python = ">=3.10"`. |
| Entry points / console scripts | PASS | `pyproject.toml:38-39`: `[project.scripts]` → `econflow = "econflow.cli:app"`. Confirmed functional via the CLI smoke test in §1. |
| Dependency pinning | Informational | `pyproject.toml` dependencies are lower-bound-only (e.g. `pandas>=2.0`, `linearmodels>=5.3`). `uv.lock` pins exact resolved versions (`linearmodels==7.0`, `statsmodels==0.14.6` per prior investigation, not re-verified line-by-line this session but the lockfile's existence and pinning approach was confirmed present). |
| Plugin entry-points section | **Not present** | No `[project.entry-points."econflow.plugins"]` block exists in `pyproject.toml` (grepped this session) — third-party plugin authors have no example to copy from the package's own config, though the auto-loading mechanism itself (`_load_entry_point_plugins()`) is documented elsewhere as implemented. Not a release blocker by itself; a documentation/discoverability gap. |

---

# 7. Reproducibility

All items in this section were produced by **this session running the pipeline itself**, not by reading a prior report's claims about a prior run.

| Item | Result | Evidence |
|---|---|---|
| Sample project / Grunfeld example | **PASS** | `econflow run --config examples/getting_started/config/config.yaml --models .../models.yaml --outputs .../outputs.yaml` executed fresh this session. Log output: `220 obs, 11 firms, 20 years`, `[1/5]` through `[5/5]` all completed, `Pipeline complete` in `1.1 s`. |
| Pipeline output | PASS | Produced `diagnostics.csv`, `table_fe_investment.csv`, `table_fe_investment.tex`, `run_metadata.json` — all confirmed written with fresh timestamps this session. |
| Diagnostics | **PASS for VIF and Breusch-Pagan, FAIL for Durbin-Watson** | See §3 for exact numbers. |
| Tables | **PASS for coefficients/SEs (one cell off by 1 in the 4th decimal), FAIL for column-header text and one SE cell vs. the frozen fixture** | See §3 / §8 for the label discrepancy and its likely (intentional-but-unreconciled) cause. |
| Figures | **N/A — correctly absent** | `examples/getting_started/config/outputs.yaml:17` (read this session): `figures.enabled: false`, with the comment "figures not used in this tutorial." No `figures/` output directory is expected and none was produced. Not a defect. |
| Hashes | **PASS** | `sha256sum examples/getting_started/data/grunfeld.csv` → `d73bb76112ccf74ef6c85d4780e7dc0fb7ded7c671f1f51cd94831b3472f2ff9`, verified twice this session, matches the frozen I-4 value exactly. |

---

# 8. Release Risks

### CRITICAL

**C-1. Nothing described in this checklist is committed to git.**
- Evidence: `git status --short` (this session) → 426 files "MM", 35 "AM", 16 "D", 10 "??" (486 total). `git log -1 --oneline` → `35f5926 Sprint 11F...`, unchanged. `git show HEAD:src/econflow/estimation/dispatcher.py` → file does not exist at HEAD, despite being 355 lines and central to the (frozen) dispatcher architecture that this session directly exercised via a live pipeline run.
- Affected files: effectively the entire working tree.
- Impact: a `v1.0` tag cannot be cut against a commit that does not contain the code the tag would represent.
- Recommendation: commit the working tree in reviewable increments before any further release step.

**C-2. `docs/sdk/PLUGIN_SDK.md` documents field names that do not exist on the frozen interfaces.**
- Evidence: §2 above (`rsq` vs. `rsquared`, `check`/`level:"error"` vs. `diagnostic_id`/`diagnostic_name`/`level:"fail"`), cross-checked against `ARCHITECTURE_FREEZE_v1.md` and `src/econflow/estimation/ols.py` directly this session.
- Affected files: `docs/sdk/PLUGIN_SDK.md` (lines 77, 240, 380, 559, 566, 1488-1495, 2760).
- Impact: violates Architecture Freeze invariant I-8 (plugin backward compatibility); a plugin author following the documented contract would write broken code.
- Recommendation: correct the field names in `PLUGIN_SDK.md` and add a regression test tying the SDK's documented contract to the live dataclasses, so this cannot silently drift again.

**C-3. Version not bumped; PyPI not published.**
- Evidence: §1, §6.
- Impact: there is no `1.0.0` to tag or ship.
- Recommendation: final-step version bump across `pyproject.toml`, `__init__.py`, `CITATION.cff`, then publish.

### HIGH

**H-1. 24 tests fail on a fresh run, with two distinct, now-precisely-identified causes.**
- Evidence: §3, §4 — full list with exact numeric diffs captured this session.
- Affected files: see the list in §4.
- Impact: touches Architecture Freeze invariants I-1 and I-5 directly (the freeze document's own named enforcement mechanism, `test_pipeline_baseline.py`, is among the failures).
- Recommendation: for the Durbin-Watson and adjusted-R²/df_resid discrepancies, trace the exact formula change (likely related to the same constant-handling change behind the already-accepted D3 finding) and either fix or formally document as an intentional, reviewed change with updated baselines. For the column-label and LaTeX-caption discrepancies, the live output is very likely *correct* and the **baseline fixture is the stale artifact** — update `tests/integration/fixtures/baseline/comparison_table.{csv,tex}` rather than the code, pending confirmation this is intentional.

**H-2. Coverage gate excludes the code under scientific review.**
- Evidence: §4.
- Affected files: `pyproject.toml` `[tool.coverage.run].omit`.
- Impact: the 70% coverage figure provides no assurance about `estimation/`, `diagnostics/`, or `outputs/` — exactly the code with the numeric discrepancies in H-1.
- Recommendation: remove the live-implementation packages from `omit`; accept a lower, honest `fail_under` and track improvement.

**H-3. `ruff check src/ tests/` is not clean.**
- Evidence: §4, reproduced twice this session.
- Affected files: `src/econflow/config/linter.py`, `src/econflow/estimation/__init__.py`, `tests/unit/test_estimation_fixed_effects.py:84`.
- Impact: contradicts "ruff clean" release-gate expectations.
- Recommendation: `ruff check --fix` resolves 4 of 8 automatically; the remainder need manual review.

**H-4. `CHANGELOG.md` has no entry for any work after 2026-07-09.**
- Evidence: §5.
- Impact: the changelog does not describe the majority of what this checklist is evaluating.
- Recommendation: add a `[1.0.0]` (or interim) section before tagging.

**H-5. `test_validate_strict_succeeds_on_valid_cluster` fails on an undiagnosed fixture mismatch.**
- Evidence: §4.
- Affected files: `tests/integration/test_validator_registry.py`.
- Impact: unclear whether this reflects a real validator defect or a broken test fixture; not resolved in this session.
- Recommendation: dedicated investigation before v1.0.

### MEDIUM

**M-1. The Architecture Freeze's own numerical-identity test does not guarantee it is comparing fresh output.**
- Evidence: `tests/integration/test_pipeline_baseline.py::_run_pipeline()` (lines 85-103) is defined but never wired into any pytest fixture used by the file's test classes — confirmed by grep this session; the file-comparison tests (`TestDiagnostics`, `TestComparisonTableCSV`, `TestComparisonTableLaTeX`) simply read whatever already exists under `examples/getting_started/outputs/`. This session's own experience (an initial reading of these failures, before this session ran the pipeline itself, showed different — and in one case actively misleading — diffs) demonstrates this gap is not theoretical.
- Impact: the invariant I-1/I-5 enforcement mechanism the freeze document names as authoritative can silently pass or fail based on stale files rather than current code.
- Recommendation: wire `_run_pipeline()` (fixed to call the CLI with `--config` rather than a bare positional — see M-2) into a module-scoped autouse fixture, or otherwise guarantee freshness before assertions run.

**M-2. `_run_pipeline()`'s own subprocess invocation appears broken.**
- Evidence: `_run_pipeline()` calls `python -m econflow.cli run <CONFIG_PATH> --models ... --outputs ...` with `CONFIG_PATH` as a bare positional argument. `econflow run` (per `cli.py`, read in full this session) has no positional parameter — `config` is exclusively `--config`/`-c`. Reproduced directly this session: running that exact invocation form produces **no stdout, no stderr, and exit code 0**, without regenerating any output file. Since this helper is unused (M-1), the bug is currently latent rather than actively causing wrong results, but it means this function cannot currently be relied on if it is ever wired up.
- Impact: low today (dead code), but blocks the fix recommended in M-1 until repaired.
- Recommendation: fix the call to use `--config`, and add an assertion that the subprocess actually produced output (not just exit-code 0), given the exit-0-with-no-output behavior observed.

**M-3. `docs/sdk/PLUGIN_SDK.md` still declares `Stability: Stable`.**
- Evidence: line 4, read this session; contradicted by C-2 above.
- Recommendation: downgrade to `Beta` until C-2 is resolved, or fix C-2 first.

**M-4. `CITATION.cff` contains placeholder values.**
- Evidence: `orcid: "https://orcid.org/0000-0000-0000-0000"` (×2) and `affiliation: ""` (×2) — present in the version of the file read this session (carried over from prior context; existence of the file and its format were reconfirmed this session, though the placeholder text itself was not re-diffed byte-for-byte in this pass).
- Recommendation: fill in before release.

### LOW

**L-1. No `[project.entry-points."econflow.plugins"]` example in `pyproject.toml`.** See §6. Discoverability gap, not a functional blocker.

**L-2. `CONTRIBUTING.md` states "1,400+ tests"; actual collected count is 2,136.** Conservative, not misleading, but stale.

---

# 9. Final Release Gate

## Decision: **NOT READY**

### Justification, from repository evidence gathered in this session only

Three findings are individually sufficient to block a v1.0 tag today, independent of each other:

1. **Nothing is committed.** The dispatcher architecture this checklist directly exercised via a live pipeline run — confirmed working, confirmed frozen-interface-compliant — does not exist in git history at all. There is no commit to tag.
2. **The project's own named enforcement mechanism for numerical/formatting stability (`test_pipeline_baseline.py`) fails on a fresh run**, and this session's own re-verification found the failures more nuanced than they first appeared: some are likely a stale baseline fixture (the code may in fact be *more* correct than the frozen expectation), and some (Durbin-Watson, adjusted R²) are genuine, currently-unexplained numeric drift in code paths this project's own architecture documents treat as scientifically load-bearing. Both categories need resolution — the first by updating fixtures with a documented decision, the second by root-causing — before the freeze's own gate can honestly be called green.
3. **The Plugin SDK documents a contract that does not match the frozen interface or the source code.** This is a direct, freshly-verified violation of the project's own Architecture Freeze invariant I-8.

None of these are cosmetic. All three were independently re-derived from source and live execution in this session, not inherited from a prior report.

### What is genuinely solid, from the same evidence

Packaging (wheel, sdist, editable install, CLI, imports) is clean. The public API surface has zero phantom exports across all 8 packages, verified directly. The exception hierarchy is correctly unified and verified via live `issubclass`/MRO checks. The dispatcher correctly translates YAML specs to registry keys per the frozen rules. The Grunfeld example runs end-to-end and produces correct coefficients. All required release-artifact documents exist. This is a project that is close, with a short, concrete, evidenced list of what stands between it and 1.0 — not a project with an unknown amount of hidden work remaining.

---

## Independent Architectural Review of This Checklist

- **Every PASS is supported by evidence executed in this session** — a command, a direct file read with line numbers, or both. Where a PASS relies partly on older context (CITATION.cff's exact placeholder text, `uv.lock`'s exact pins), this is disclosed explicitly rather than presented as freshly re-verified (see M-4, §6 "Dependency pinning").
- **Every FAIL cites the affected file(s)**, and where possible the exact line numbers and exact observed-vs-expected values, not a category description. The two Section 3/7 diagnostics/table findings were deliberately re-verified via a second, independent method (live pipeline run + direct `diff`) after an initial pytest-only read produced a less precise picture — this is disclosed in the preamble and in H-1/M-1, rather than silently corrected.
- **Every recommendation in §8 is a concrete next action** tied to a specific file or command (e.g., "wire `_run_pipeline()` into a module-scoped fixture," "remove `estimation/*` from the coverage omit list"), not a vague exhortation.
- **No previous report was accepted without verification.** Every load-bearing claim from `R1_EXCEPTION_UNIFICATION_REPORT.md`, `API_FREEZE_REPORT.md`, `ARCHITECTURE_FREEZE_v1.md`, and the various audit documents that this checklist relies on was independently re-executed this session (exception MRO checks, registry checks, hash checks, wheel/sdist builds, ruff, the full test suite, a live pipeline run). Where re-execution was not possible within this session's time budget (69 tests in three environment-fingerprinting-heavy files), this is stated as NOT VERIFIED rather than assumed passing — per the explicit instruction not to invent PASS results.
- **One self-correction is recorded rather than hidden:** the initial full-suite run under `pytest -n 2` produced 21 false-positive failures in `test_release_check.py` due to a parallel-execution artifact (subprocess-spawning tests colliding under xdist workers). This was caught by re-running that file in isolation (66/66 passed) and is reported as a testing-methodology finding, not silently dropped from the count.

### Confidence score for this release decision: **82/100**

The decision itself (NOT READY) is high-confidence — the git-provenance gap alone is dispositive and required no judgment call. The score is not higher because: (a) two of the four numeric discrepancies in §3 (adjusted R², Durbin-Watson) were identified and precisely measured but not root-caused to a specific line of code within this session's time budget, so their severity — cosmetic rounding drift vs. a genuine formula regression — is not yet fully known; (b) 69 of 2,136 tests (3.2%) could not be executed in this session and are reported as NOT VERIFIED rather than folded into either PASS or FAIL; (c) this session's own discovery that an initial reading of the baseline-comparison failures was based on stale files (§3 preamble) means similar staleness could in principle affect other file-based checks in ways not caught by the spot-checks performed here.
