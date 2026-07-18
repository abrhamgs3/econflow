# Phase 5A Independent Architecture Review

**Date:** 2026-07-10  
**Reviewer:** Independent (post-implementation, fresh read)  
**Scope:** `src/econflow/pipeline_generic.py` Phase 5A changes  
**Status: PASS — all 5 criteria satisfied**

---

## Review Criteria and Findings

### 1. Legacy path untouched ✅ PASS

**Evidence:**

- `_run_model()` (line 119): Completely unchanged. Continues to call
  `sm.add_constant()`, `linearmodels.panel.PooledOLS`, `linearmodels.panel.PanelOLS`,
  and returns a linearmodels result object with `.std_errors`, `.rsquared_within`, etc.

- `_build_comparison_table()` (line 403): Completely unchanged. Continues to use
  `res.std_errors[reg]` (linearmodels attribute), `rsquared_within`, and spec string
  comparison for OLS detection. All field access patterns are identical to Phase 0.

- Formatting functions (Architecture Freeze F-3): Verified unchanged —
  - `_stars()` at line 217 ✓
  - `_fmt_coef()` at line 224 ✓
  - `_fmt_se()` at line 228 ✓
  - `_fmt_r2()` at line 232 ✓
  - `_write_latex()` at line 578 ✓
  - `_write_markdown()` at line 661 ✓
  - `_write_html()` at line 668 ✓

- `_run_diagnostics()` (line 244): Called identically on both paths. No change to
  the function or its call site.

**Verdict:** The legacy path is a byte-for-byte copy of its Phase 0 state.

---

### 2. Dispatcher isolated ✅ PASS

**Evidence:**

- `_USE_DISPATCHER = False` by default (line 67). Standard invocations never enter
  dispatcher code.

- All dispatcher execution is inside `if _USE_DISPATCHER:` blocks (lines 792–841,
  878–887). The `else:` branches are the legacy paths, unchanged.

- All dispatcher imports are lazy (inside the `if` block with `# noqa: PLC0415`):
  - `from econflow.estimation.dispatcher import EstimationDispatcher, PipelineContext`
  - `from econflow.core.exceptions import RegistryError`
  These imports fire only when `_USE_DISPATCHER=True` and produce zero overhead
  on the default path.

- `_build_comparison_table_dispatcher()` (line 474) is a new, additive function that
  does not touch or share code with `_build_comparison_table()` (line 403). The two
  functions are fully independent.

- Invariant I-2 (Architecture Freeze v1) — "exactly one path active at any time" —
  is enforced by the single boolean switch. The mutual exclusion is structural:
  the `if/else` guarantees at most one branch executes per invocation.

**Verdict:** Dispatcher code is fully isolated. A standard run has zero dispatcher
overhead (no imports, no branches taken).

---

### 3. Rollback possible ✅ PASS

**Evidence:** Phase 5A consists of exactly 5 targeted, independent edits:

| Edit | Change | Rollback action |
|------|--------|-----------------|
| 1 | Add `import os` (line 27) | Remove `import os` |
| 2 | Add `_USE_DISPATCHER` flag block (lines 46–67) | Remove block |
| 3 | Add `_build_comparison_table_dispatcher()` (lines 474–569) | Remove function |
| 4 | Replace [3/5] for-loop with `if _USE_DISPATCHER:` block | Revert to simple for-loop |
| 5 | Replace [4/5] single call with `if _USE_DISPATCHER:` block | Revert to single `_build_comparison_table(...)` call |

No legacy code was deleted. Every legacy code path is preserved verbatim.
Reverting all 5 edits restores the pre-Phase 5A state exactly, with no orphaned
references.

**Verdict:** Rollback is a mechanical 5-step revert with no semantic ambiguity.

---

### 4. No API changes ✅ PASS

**Evidence:**

- `run_from_config(config_path, models_path, outputs_path)` — signature unchanged
  (Architecture Freeze F-5). Verified against `inspect.signature()` in test P5A-05.

- No new symbols exported from `pipeline_generic` module. `_USE_DISPATCHER` is
  prefixed `_` and not present in any `__init__.py` re-export.

- `EstimationDispatcher` and `PipelineContext` are not imported at module level in
  `pipeline_generic.py` — they remain registered in `econflow.estimation` only.

- The existing public API — `run_from_config()` — behaves identically to Phase 4
  when invoked without the environment variable.

**Verdict:** Zero API surface change. Existing call sites (CLI, tests, user code)
require no modification.

---

### 5. No user-visible changes ✅ PASS

**Evidence:**

- **CLI**: No changes to `cli.py`. The `econflow run` command behavior is unchanged.

- **YAML**: No new required or optional keys in `config.yaml`, `models.yaml`, or
  `outputs.yaml`. Existing project directories run without modification.

- **Default behavior**: `ECONFLOW_USE_DISPATCHER` defaults to `"0"` → `_USE_DISPATCHER = False`.
  The user must explicitly set the environment variable to activate the dispatcher path.

- **Module docstring**: Does not mention `ECONFLOW_USE_DISPATCHER`. The variable is
  intentionally undiscoverable through normal means (help text, `--help`, docs).

- **Outputs**: When running the default path, all output files (comparison_table.csv,
  diagnostics.csv, run_metadata.json, LaTeX tables) are produced by the same code
  paths as Phase 4. No formatting or content changes.

- **Error surface**: Error types and messages on the legacy path are unchanged.
  New errors (`ModelSpecificationError` wrapping `NotImplementedError`/`RegistryError`)
  are only reachable on the dispatcher path.

**Verdict:** A user who does not set `ECONFLOW_USE_DISPATCHER=1` experiences
zero behavioral change.

---

## Additional Invariants Verified

| Invariant | Status |
|-----------|--------|
| **I-2**: Exactly one path active at any time | ✅ Enforced by `if/else` — mutual exclusion is structural |
| **I-7**: No silent failure swallowing | ✅ `NotImplementedError` → `ModelSpecificationError`; `RegistryError` → `ModelSpecificationError` — both raised, neither swallowed |
| **F-3**: Formatting functions untouched | ✅ All 7 formatting functions confirmed line-by-line unchanged |
| **F-5**: `run_from_config()` signature unchanged | ✅ Confirmed |
| Lazy imports (no circular import risk) | ✅ All dispatcher imports inside `if _USE_DISPATCHER:` |

---

## Phase 5A Summary

Phase 5A introduces a **single internal execution switch** that selects between two
fully isolated code paths at runtime. The legacy path is byte-for-byte identical to
Phase 4. The dispatcher path is additive (new code only, no legacy code touched).

**The migration gate for Phase 5B is:**
- Integration tests pass on both paths (`tests/integration/test_phase5a_dual_path.py`)
- This architecture review passes (it does)
- No regression in existing test suite

**Do NOT begin Phase 5B until integration tests are run and pass locally.**
