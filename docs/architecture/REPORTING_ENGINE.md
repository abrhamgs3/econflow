# Reporting & Publication Engine

*Sprint 6 — EconFlow Reporting Engine*

---

## Overview

The Reporting Engine transforms `EstimationResult` and `DiagnosticResult`
objects into publication-ready research outputs.  It follows the same
plugin-based, registry-driven architecture used by the estimation and
diagnostics subsystems.

The core abstraction is a **separation between content and presentation**:

- **Table builders** and **figure builders** are responsible for *what* goes
  into an output — coefficients, standard errors, significance stars,
  summary statistics, diagnostic conclusions.
- **Renderers** are responsible for *how* that content is presented — LaTeX
  environments, HTML tags, CSV delimiters, JSON structure.

This means a single `ReportTable` object can be rendered to any format
without modification, and a new renderer can be added without touching any
table builder.

---

## Package Structure

```
src/econflow/outputs/
├── __init__.py            # Public API — all public symbols re-exported here
├── model.py               # ReportTable, ReportFigure, TableRow dataclasses
├── base.py                # BaseRenderer ABC + RendererError
├── registry.py            # Renderer registry (register_renderer / get_renderer)
├── diagnostics_report.py  # build_diagnostics_report() builder
├── bundle.py              # PublicationBundle — write full directory bundle
├── renderers/
│   ├── __init__.py        # Imports all renderers → triggers @register_renderer()
│   ├── csv_renderer.py    # CSVRenderer
│   ├── json_renderer.py   # JSONRenderer
│   ├── markdown_renderer.py   # MarkdownRenderer (GFM)
│   ├── html_renderer.py   # HTMLRenderer
│   └── latex_renderer.py  # LaTeXRenderer (booktabs)
├── tables/
│   ├── __init__.py        # Re-exports all builder functions
│   ├── regression.py      # build_regression_table() — full implementation
│   ├── summary_stats.py   # build_summary_stats_table() — full implementation
│   ├── balance.py         # build_balance_table() — complete-interface stub
│   ├── correlation.py     # build_correlation_table() — stub
│   ├── robustness.py      # build_robustness_table() — stub
│   ├── sensitivity.py     # build_sensitivity_table() — stub
│   ├── falsification.py   # build_falsification_table() — stub
│   └── heterogeneity.py   # build_heterogeneity_table() — stub
└── figures/
    ├── __init__.py        # Re-exports all figure builder classes
    ├── base.py            # FigureBuilder ABC
    ├── coefficient_plot.py  # CoefficientPlot — full implementation
    ├── ci_plot.py           # CIPlot — full implementation
    ├── residual.py          # ResidualFigure — stub
    ├── distribution.py      # DistributionFigure — stub
    ├── event_study.py       # EventStudyFigure — stub
    └── robustness_comparison.py  # RobustnessComparisonFigure — stub
```

---

## Data Model

### `TableRow`

The atomic unit of a table.  All cell values are **pre-formatted strings**;
renderers are responsible for structural formatting only.

```python
@dataclass
class TableRow:
    label: str                           # Row header (leftmost column)
    cells: dict[str, str]                # column_name → formatted value
    sub_cells: dict[str, str] | None     # e.g. standard errors "(0.123)"
    row_type: str                        # "data" | "separator" | "stats" | "header"
    bold: bool
    italic: bool
```

`sub_cells` are rendered as a second line within the same logical row.
Renderers that do not support sub-rows (CSV) render them as separate rows.
Renderers that support them (LaTeX, HTML) render them visually indented.

### `ReportTable`

```python
@dataclass
class ReportTable:
    title: str
    table_type: str       # "regression" | "summary_stats" | "diagnostics" | ...
    columns: list[str]    # Column header labels
    rows: list[TableRow]
    footer: list[str]     # Lines printed below the table (significance notes, etc.)
    subtitle: str
    notes: str            # Methodological note
    metadata: dict[str, Any]
```

`ReportTable` is fully serialisable via `to_dict()` / `to_json()` /
`from_dict()`.  The `from_dict` / `to_dict` round-trip is lossless — this
is the foundation for golden-output tests and cached intermediate results.

### `ReportFigure`

```python
@dataclass
class ReportFigure:
    title: str
    figure_type: str      # "coefficient_plot" | "ci_plot" | ...
    data: dict[str, Any]  # Raw numeric arrays — renderer-agnostic
    config: dict[str, Any]
    metadata: dict[str, Any]
```

`ReportFigure` carries raw data, not rendered graphics.  A downstream
renderer (matplotlib, plotly, vega-lite) reads `data` and `config` to
produce the actual image.  This keeps the outputs package dependency-free
(no matplotlib in the core).

---

## Renderer Registry

The renderer registry follows the same pattern as the estimator and
diagnostic registries.

### Registration

```python
from econflow.outputs.registry import register_renderer
from econflow.outputs.base import BaseRenderer
from econflow.outputs.model import ReportTable

@register_renderer("my_format", label="My Format", file_extension=".myf")
class MyRenderer(BaseRenderer):
    renderer_id = "my_format"
    file_extension = ".myf"

    def render(self, table: ReportTable, **kwargs) -> str:
        ...
```

Decoration at class-definition time registers the renderer.  Importing the
module that contains the decorated class is sufficient to register it —
there is no explicit registration call required.

### Retrieval

```python
from econflow.outputs import get_renderer, list_renderers

cls = get_renderer("latex")       # Returns the LaTeXRenderer class
renderers = list_renderers()      # Returns list[dict] of registry metadata
```

### Error handling

`get_renderer()` raises `RegistryError` (from `econflow.core.exceptions`)
for unknown renderer ids.  `register_renderer()` raises `RegistryError` on
duplicate registration.

---

## Built-in Renderers

| ID         | Class             | Extension | Output                          |
|------------|-------------------|-----------|---------------------------------|
| `csv`      | `CSVRenderer`     | `.csv`    | RFC 4180 CSV                    |
| `json`     | `JSONRenderer`    | `.json`   | JSON serialisation of `to_dict` |
| `markdown` | `MarkdownRenderer`| `.md`     | GFM pipe table with `<br>` for sub-cells |
| `html`     | `HTMLRenderer`    | `.html`   | `<table>` with caption/thead/tbody/tfoot |
| `latex`    | `LaTeXRenderer`   | `.tex`    | booktabs with `_escape_latex()` preserving significance stars |

All renderers implement:

```python
class BaseRenderer(ABC):
    @abstractmethod
    def render(self, table: ReportTable, **kwargs) -> str: ...

    def render_to_file(self, table: ReportTable, path: Path, *, encoding="utf-8", **kwargs) -> Path:
        """Write rendered content to a file.  Creates parent dirs automatically."""
```

---

## Table Builders

### Fully Implemented

#### `build_regression_table`

Converts one or more `EstimationResult` objects into a regression table:

```python
table = build_regression_table(
    results,                        # list[EstimationResult]
    title="Regression Results",
    column_labels=["(1)", "(2)"],   # defaults to (1), (2), ...
    variable_order=["x1", "x2"],   # explicit row ordering
    variable_labels={"x1": "AI Index"},
    coef_fmt="{:.3f}",
    se_fmt="({:.3f})",
    star_thresholds={0.01: "***", 0.05: "**", 0.10: "*"},
    include_nobs=True,
    include_rsquared=True,
    include_fstatistic=False,
    include_estimator=True,
    include_entity_fe=True,
    include_time_fe=True,
)
```

Footer rows (N, R², Estimator, Entity FE, Time FE) are rendered as
`row_type="stats"` rows below a separator.  Significance stars are appended
directly to the coefficient string — renderers must not escape them.

#### `build_summary_stats_table`

```python
table = build_summary_stats_table(
    df,                             # pd.DataFrame
    variables=["y", "x1", "x2"],   # subset; defaults to all numeric
    variable_labels={"y": "Output"},
    percentiles=(0.25, 0.50, 0.75),
    include_nobs=True,
    include_mean=True,
    include_std=True,
    include_min=True,
    include_max=True,
)
```

Non-numeric columns are always excluded.

### Complete-Interface Stubs

The following builders have full, documented interfaces but raise
`NotImplementedError` in the current release.  They are scheduled for
implementation in a future sprint.

| Function                    | Purpose                                     |
|-----------------------------|---------------------------------------------|
| `build_balance_table`       | Covariate balance: treatment vs control means + p-values |
| `build_correlation_table`   | Pairwise Pearson/Spearman/Kendall matrix    |
| `build_robustness_table`    | Focal coefficient across multiple specs     |
| `build_sensitivity_table`   | Estimate as a parameter is varied over a grid |
| `build_falsification_table` | Main estimate vs placebo results            |
| `build_heterogeneity_table` | Sub-group estimates                         |

Each stub's module docstring contains the full intended interface.

---

## Figure Builders

### Fully Implemented

#### `CoefficientPlot`

Forest-style plot of one estimator's coefficients with confidence intervals:

```python
fig = CoefficientPlot().build(
    result,                          # EstimationResult
    title="Coefficient Plot",
    variables=["x1", "x2"],         # subset
    variable_labels={"x1": "AI Index"},
    confidence_level=0.95,
    sort_by="input",                 # "input" | "coefficient" | "label"
    exclude_intercept=True,
)
```

`fig.data` contains `variables`, `labels`, `coefficients`, `ci_lower`,
`ci_upper`, `pvalues` — all as plain Python lists.

#### `CIPlot`

Confidence-interval comparison across specifications for a single focal variable:

```python
fig = CIPlot().build(
    results,                         # list[EstimationResult]
    focal_variable="x1",
    spec_labels=["OLS", "FE", "TWFE"],
    confidence_level=0.95,
)
```

### Stubs

`ResidualFigure`, `DistributionFigure`, `EventStudyFigure`,
`RobustnessComparisonFigure` all extend `FigureBuilder` and raise
`NotImplementedError` in the current release.

---

## Diagnostics Report

```python
from econflow.outputs import build_diagnostics_report

diag_table = build_diagnostics_report(
    results,                    # list[DiagnosticResult]
    group_by_estimator=True,    # inserts separator between estimator groups
    title="Diagnostic Test Results",
)
```

The resulting `ReportTable` has columns: `Estimator`, `Statistic`,
`p-value`, `Conclusion`.  The `Conclusion` column maps `DiagnosticResult.level`
to "Pass" / "Fail" / "N/A".

Estimator grouping is keyed on `DiagnosticResult.extra["estimator_id"]`
when present; results without this key are grouped together.

---

## Publication Bundle

`PublicationBundle` is the top-level orchestrator.  It collects tables and
figures and writes them to a structured directory:

```
<output_dir>/
    tables/
        <slug>.csv
        <slug>.tex
        <slug>.md
        <slug>.html
    figures/
        <slug>.json
    diagnostics/
        diagnostics.md
        diagnostics.tex
    manifest.json
```

```python
from econflow.outputs import PublicationBundle, build_regression_table, CoefficientPlot

bundle = (
    PublicationBundle("outputs/paper", table_formats=["csv", "latex"])
    .add_table(build_regression_table(results), slug="regression")
    .add_figure(CoefficientPlot().build(results[0]), slug="coef_plot")
    .set_diagnostics(build_diagnostics_report(diag_results))
)
manifest = bundle.write()
```

`bundle.write()` returns a manifest dict and also writes `manifest.json`.
The manifest records: bundle creation timestamp, all table slugs and their
file paths per format, all figure slugs and their JSON paths, and the
diagnostics file paths.

### `econflow report` CLI

```
econflow report [OUTPUT_DIR] [--formats csv,latex,markdown,html] [--no-overwrite]
```

Reads saved estimation results from `outputs/results/` (populated by
`econflow run`) and writes a `PublicationBundle` to `OUTPUT_DIR`
(default: `outputs/econflow/`).

Full deserialization of `EstimationResult` objects from disk is deferred to
the Reproducibility Framework sprint.  The command currently creates the
directory structure and manifest; table and figure population requires
running `econflow run` first.

---

## Design Decisions

### Pre-formatted strings in cells

`TableRow.cells` and `TableRow.sub_cells` contain pre-formatted strings
(`"0.543***"`, `"(0.123)"`).  Renderers handle structural formatting only
(LaTeX environments, HTML tags, CSV delimiters) — they never reformat
numeric values.

This decoupling means:

1. The same formatting precision is guaranteed across all output formats.
2. Adding a new renderer requires no knowledge of econometric conventions.
3. Significance stars are concatenated to coefficient strings by the builder
   and must be preserved verbatim by renderers (the LaTeX renderer escapes
   other special characters but never escapes `*`).

### Renderer as class, not function

Renderers are classes rather than functions so that stateful renderers
(e.g. one that accumulates a running list of tables for a multi-table
document) can be implemented without changing the interface.  The
`render_to_file` method is provided as a concrete implementation on
`BaseRenderer`, not on each subclass.

### Figures as raw data, not images

`ReportFigure` carries numeric arrays and configuration, not rendered
graphics.  This keeps the outputs package free of heavy visualization
dependencies (matplotlib, plotly) in the core.  A separate `econflow-viz`
plugin can implement figure rendering for any backend.

### Bundle as final assembly step

`PublicationBundle` is intentionally thin — it does not know how to build
tables or figures; it only knows how to write them.  The caller is
responsible for constructing `ReportTable` and `ReportFigure` objects and
passing them to `add_table` / `add_figure`.  This separation makes the
bundle composable and testable independently of any estimator logic.

---

## Testing

Sprint 6 added 158 tests across five test modules:

| Module                                      | Tests | Scope                              |
|---------------------------------------------|-------|------------------------------------|
| `tests/unit/test_report_model.py`           |  53   | `ReportTable`, `ReportFigure`, `TableRow` |
| `tests/unit/test_renderer_registry.py`      |  18   | Registry CRUD + RegistryError      |
| `tests/unit/test_renderers.py`              |  42   | All 5 renderers: format, content, file I/O |
| `tests/unit/test_table_builders.py`         |  46   | regression + summary_stats builders |
| `tests/unit/test_figure_builders.py`        |  31   | CoefficientPlot + CIPlot           |
| `tests/integration/test_outputs_pipeline.py`| 35    | End-to-end: estimator → table → renderer → file |

All 158 tests pass.  `ruff check src/ tests/` reports no errors.

---

## Future Work

The following items are deferred to later sprints:

- **Balance, correlation, robustness, sensitivity, falsification,
  heterogeneity** table builders: full implementation.
- **ResidualFigure, DistributionFigure, EventStudyFigure,
  RobustnessComparisonFigure**: full implementation.
- **EstimationResult serialisation**: required for `econflow report` to
  populate tables from saved results without re-running the pipeline.
- **Figure rendering plugin** (`econflow-viz`): converts `ReportFigure`
  data arrays to matplotlib/plotly images.
- **Multi-table LaTeX document**: a `DocumentBuilder` that wraps multiple
  `ReportTable` objects in a single `.tex` file with `\input{}` references.
- **Golden-output tests**: snapshot comparison for rendered output files,
  enabling regression detection when formatter logic changes.
