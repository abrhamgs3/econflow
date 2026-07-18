# EconFlow v0.6 RC1 — Sprint 6 Maintainer Review

*Reporting & Publication Engine — Code Review*
*Scope: `src/econflow/outputs/`, `src/econflow/commands/report.py`,
`tests/unit/test_report_*.py`, `tests/unit/test_renderer_*.py`,
`tests/unit/test_table_builders.py`, `tests/unit/test_figure_builders.py`,
`tests/integration/test_outputs_pipeline.py`*

---

## Summary

The Sprint 6 architecture is sound. The content/presentation separation
(`ReportTable` ← builders → renderers) is well-executed, the registry
pattern is consistent with earlier sprints, and the `PublicationBundle`
chainable API is clean. 158 tests pass. Ruff is clean.

Two issues must be fixed before release (one will produce corrupt LaTeX
output for any user with footer notes; one makes the diagnostics table
always render empty). Three more are high enough priority that shipping
them as-is would create technical debt that is harder to fix after a public
API is established.

---

## Critical

### C1 — LaTeX renderer emits `\begin{tablenotes}` inside `table`, not `threeparttable`

**File:** `src/econflow/outputs/renderers/latex_renderer.py:142–148`

The renderer produces:

```latex
\begin{table}[htbp]
  ...
  \begin{tablenotes}   ← INVALID here
    \small
    \item p<0.01: ***
  \end{tablenotes}
\end{table}
```

`\begin{tablenotes}` belongs to the `threeparttable` package and is only
valid inside a `threeparttable` environment, not a `table` environment.
Any document with footer notes will fail to compile with:

```
! LaTeX Error: Environment tablenotes undefined.
```

The renderer's own docstring says "requires `\usepackage{booktabs}`" but
does not mention `threeparttable`. The test suite never compiles the
generated LaTeX, so this was not caught.

**Minimum fix:** Replace `\begin{tablenotes}...\end{tablenotes}` with a
standard multi-column note row appended after `\end{tabular}`:

```latex
  \end{tabular}
  \begin{flushleft}
    \footnotesize
    Note: p<0.01: ***
  \end{flushleft}
  \caption{...}
\end{table}
```

Or wrap the entire table in `threeparttable` and add
`\usepackage{threeparttable}` to the renderer notes — but the simpler
`flushleft` approach adds no new package dependency.

---

### C2 — `DiagnosticResult` has no `estimator_id`, and diagnostic plugins never populate `extra["estimator_id"]` — "Estimator" column is always empty

**Files:** `src/econflow/outputs/diagnostics_report.py:95,130`,
`src/econflow/estimation/result.py:23–81`,
`src/econflow/diagnostics/plugins/breusch_pagan.py`

`build_diagnostics_report()` populates the "Estimator" column from
`r.extra.get("estimator_id", "")`. But no diagnostic plugin sets
`extra["estimator_id"]`. `DiagnosticResult` itself has no `estimator_id`
field. The result is that every row in the Estimator column is blank in
any real usage:

```
| Breusch-Pagan Test |  | 8.41 | 0.015 | Fail |
```

This makes the table useless when diagnostics from multiple estimators are
combined.

This was introduced as a workaround during a Sprint 6 fix when it was
discovered that `DiagnosticResult` lacked the field. The root fix requires
two changes:

1. Add `estimator_id: str = ""` to `DiagnosticResult` in
   `estimation/result.py`.
2. Have `BaseDiagnostic.run()` — or a concrete wrapper — set
   `result.estimator_id` from `estimation_result.estimator_id` before
   returning. The cleanest approach is a `run_with_context()` method on
   `BaseDiagnostic`:

```python
def run_with_context(self, estimation_result, **kwargs):
    dr = self.run(estimation_result, **kwargs)
    if dr.estimator_id == "":
        dr = dataclasses.replace(dr, estimator_id=estimation_result.estimator_id)
    return dr
```

Callers (and `build_diagnostics_report`) should document that
`run_with_context()` is preferred over `run()` when a diagnostics table
is being built.

---

## High

### H1 — `_conclusion()` maps diagnostic levels to "Pass"/"Fail", which reverses the test semantics

**File:** `src/econflow/outputs/diagnostics_report.py:34–42`

```python
if result.level in ("error", "warning"):
    return "Fail"
if result.level == "info":
    return "Pass"
```

The Breusch-Pagan plugin returns `level="warning"` when heteroskedasticity
is detected (H0 rejected), and `level="info"` when it is not. Mapping
`"warning"` → `"Fail"` and `"info"` → `"Pass"` conflates the *level* of
the alert with the *outcome of the null hypothesis test*.

In a publication table, a reader sees "Fail" for the BP test and
interprets it as "the test failed to run" rather than "H0 was rejected".
Standard econometric notation uses "Reject H0" / "Fail to reject H0".

The `DiagnosticResult.conclusion` field already contains the full
human-readable result. The fix is to use a short form derived from
`conclusion`, or to introduce a dedicated `passed: bool | None` field on
`DiagnosticResult`. The minimal pre-release fix:

```python
def _conclusion(result: DiagnosticResult) -> str:
    if result.level == "skip":
        return "N/A"
    # Use the first clause of the existing conclusion text
    c = result.conclusion
    if c.startswith("Reject H0"):
        return "Reject H0"
    if c.startswith("Fail to reject"):
        return "Fail to reject H0"
    return c[:30] if c else "—"
```

This is brittle (relies on conclusion text format) but avoids a data-model
change before RC1.  The proper fix (adding `passed: bool | None` to
`DiagnosticResult`) should be done in the same sprint as C2.

---

### H2 — `PublicationBundle.write()` does not validate renderer IDs before writing — partial bundles on bad input

**File:** `src/econflow/outputs/bundle.py:192–265`

If an unknown renderer is in `table_formats` (e.g. `"pdf"`), the bundle
creates all directories, writes all preceding tables, then raises
`RegistryError` partway through. The caller receives an exception but the
output directory already exists with partial content. On the next call with
`overwrite=True`, the partial content is silently replaced. With
`overwrite=False`, the caller gets `FileExistsError` instead of the
original `RegistryError`.

**Minimum fix:** Add a validation pass at the start of `write()`:

```python
def write(self) -> dict[str, Any]:
    # Validate all renderer ids before touching the filesystem
    all_formats = {fmt for entry in self._tables for fmt in entry.formats}
    for fmt in all_formats:
        get_renderer(fmt)  # raises RegistryError immediately if unknown
    ...
```

---

### H3 — Duplicate table slugs silently overwrite files

**File:** `src/econflow/outputs/bundle.py:143–147`

Two tables with the same title (or manually assigned the same slug) will
both write to the same file path. The second silently overwrites the first.
The manifest will contain two entries with the same slug and file path,
with only the second table's content on disk:

```python
bundle.add_table(table1, slug="results")   # writes results.csv
bundle.add_table(table2, slug="results")   # silently overwrites results.csv
# manifest has two entries both pointing to tables/results.csv
```

**Minimum fix:** Check for slug collision in `add_table()`:

```python
existing = {e.slug for e in self._tables}
if resolved_slug in existing:
    raise ValueError(
        f"Slug {resolved_slug!r} already used in this bundle. "
        "Pass a unique slug= argument."
    )
```

---

## Medium

### M1 — `FigureBuilder.build()` ABC signature is `(**kwargs)` but all implementations use typed parameters — mypy will flag every subclass

**File:** `src/econflow/outputs/figures/base.py:25`

```python
@abc.abstractmethod
def build(self, **kwargs: Any) -> ReportFigure: ...
```

`CoefficientPlot.build` has the signature
`(self, result, *, title, variables, ...)`. This is an override with an
incompatible signature under strict type checking. mypy reports:

```
Signature of "build" incompatible with supertype "FigureBuilder"
```

For v0.6, add a `# type: ignore[override]` comment to both concrete
`build()` methods, or use `Protocol` instead of inheritance. The longer
fix is to define `build()` with a generic `result` parameter.

---

### M2 — API naming inconsistency: estimator registry exports bare `register` / `unregister`

**File:** `src/econflow/estimation/__init__.py:59`

```python
from econflow.estimation.registry import get_estimator, list_estimators, register, unregister
```

The three registries export:

| Registry   | Decorator         | Lookup           | Listing            | Remove               |
|------------|-------------------|------------------|--------------------|----------------------|
| Estimator  | `register()`      | `get_estimator()`| `list_estimators()`| `unregister()`       |
| Diagnostic | `register_diagnostic()` | `get_diagnostic()` | `list_diagnostics()` | `unregister_diagnostic()` |
| Renderer   | `register_renderer()` | `get_renderer()` | `list_renderers()` | `unregister_renderer()` |

`register()` and `unregister()` are ambiguous. A user who does
`from econflow.estimation import register` and
`from econflow.outputs import register_renderer` in the same file has two
distinct names — but anyone using star imports or autocomplete from
`econflow` directly may be confused.

Pre-release, add aliases in `estimation/__init__.py`:

```python
from econflow.estimation.registry import register as register_estimator
from econflow.estimation.registry import unregister as unregister_estimator
```

And export both the old and new names (for backward compat in this
pre-1.0 state). Update `estimation/registry.py` to rename the functions to
`register_estimator` and `unregister_estimator`, keeping `register` as a
deprecated alias, before v1.0.

---

### M3 — `RendererError` not exported from `outputs/__init__.py`

**File:** `src/econflow/outputs/__init__.py`

Users who want to catch renderer failures with `except RendererError` must
import from `econflow.outputs.base`, breaking the convention that
`econflow.outputs` is the single import point. Same pattern as
`RegistryError` (imported from `econflow.core.exceptions`).

**Fix:** Add to `outputs/__init__.py`:

```python
from econflow.outputs.base import RendererError
```

And add `"RendererError"` to `__all__`.

---

### M4 — `ReportTable.from_dict()` uses `TableRow(**r)` with no field validation

**File:** `src/econflow/outputs/model.py:141`

```python
rows = [TableRow(**r) for r in data.get("rows", [])]
```

If the serialised dict contains extra keys (e.g. from a future
`TableRow` version with new fields loaded into an older installation),
this raises `TypeError: unexpected keyword argument`. If it contains
missing keys, it raises `TypeError: missing required argument`.

**Minimum fix:**

```python
rows = [
    TableRow(
        label=r.get("label", ""),
        cells=r.get("cells", {}),
        sub_cells=r.get("sub_cells"),
        row_type=r.get("row_type", "data"),
        bold=r.get("bold", False),
        italic=r.get("italic", False),
    )
    for r in data.get("rows", [])
]
```

This is forward-compatible and backward-compatible.

---

## Low

### L1 — `PublicationBundle.write()` always creates `figures/` and `diagnostics/` even when empty

**File:** `src/econflow/outputs/bundle.py:203–210`

```python
tables_dir.mkdir(parents=True, exist_ok=True)
figures_dir.mkdir(parents=True, exist_ok=True)
diag_dir.mkdir(parents=True, exist_ok=True)
```

An empty bundle produces three empty directories and a manifest. This is
harmless but confusing to users inspecting the output. Create directories
lazily (only when content will be written into them).

---

### L2 — LaTeX renderer's `\begin{tablenotes}` note says "requires `\usepackage{booktabs}`" but not `threeparttable`

*(Covered under C1 — flagged again here because the docstring note itself
needs updating regardless of which fix approach is chosen.)*

---

### L3 — No test verifies that rendered LaTeX compiles without errors

The LaTeX test suite verifies string-level content (`\toprule` present,
`&` delimiters, etc.) but does not attempt compilation. The C1 bug
survived 18 tests. For RC1, add at least one compile-check test using
`subprocess` + `pdflatex --halt-on-error` when LaTeX is available
(mark with `@pytest.mark.skipif`).

---

### L4 — `_slugify()` drops non-ASCII characters entirely

**File:** `src/econflow/outputs/bundle.py:44–50`

```python
text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
```

"Résultats de régression" becomes "rsultats_de_rgression". International
users lose meaningful slug content. For RC1, document this behaviour in the
function docstring. Full unicode slug support can wait until after v1.0.

---

### L5 — `outputs/figures/` has no figure builder registry

Estimators, diagnostics, and renderers all use a registry that supports
`list_*()`, `get_*()`, and `register_*()`; figure builders do not.
`list_figure_builders()` cannot be implemented without it. This is
acceptable for v0.6 (two full implementations), but should be added in the
next sprint before the figure API stabilises.

---

## Recommended Pre-Release Actions

In priority order:

| # | Severity | File(s) | Change |
|---|----------|---------|--------|
| 1 | Critical | `renderers/latex_renderer.py` | Replace `tablenotes` with `flushleft` footnote block |
| 2 | Critical | `estimation/result.py`, `diagnostics/base.py`, `outputs/diagnostics_report.py` | Add `estimator_id` to `DiagnosticResult`; populate in `BaseDiagnostic` |
| 3 | High | `outputs/diagnostics_report.py` | Fix `_conclusion()` to emit "Reject H0" / "Fail to reject H0" |
| 4 | High | `outputs/bundle.py` | Validate renderer IDs before any file writes |
| 5 | High | `outputs/bundle.py` | Raise `ValueError` on duplicate slug in `add_table()` |
| 6 | Medium | `outputs/__init__.py` | Export `RendererError` |
| 7 | Medium | `outputs/model.py` | Explicit field mapping in `from_dict()` |

Items M2 (registry naming) and L5 (figure registry) are acknowledged debt
but can safely ship as-is for v0.6 given that the public API is still
pre-1.0 and all downstream callers are internal.

---

*Review conducted against commit state: 674 tests passing, ruff clean.*
