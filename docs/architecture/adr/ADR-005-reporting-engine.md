# ADR-005: Reporting Engine

**Status:** Accepted  
**Date:** 2026-06-28  
**Deciders:** Technical Steering Committee  
**Supersedes:** —  
**Superseded by:** —

---

## Context

The bridge between econometric estimation and a published paper is where reproducibility
most commonly fails in practice. A researcher runs a regression, reads coefficients from
a terminal, and types them into a LaTeX table. The typed numbers differ from the computed
numbers by rounding error, transcription error, or copy-paste error. The published
table is not the output of the analysis; it is a manually transformed representation of
that output. The transformation is undocumented, unverifiable, and unreproducible.

EconFlow's mission requires eliminating this manual step. The output of the pipeline
must be the input to the paper, without a human transformation in between. This requires
a reporting engine that can produce publication-standard tables and figures directly from
`EstimationResult` objects.

The design of this engine faced a central tension: a LaTeX table is structured very
differently from a CSV table, which is structured very differently from an HTML table.
If the reporting engine produced LaTeX directly from estimation results, it would need
a separate implementation for each output format. Any change to how coefficients are
formatted (e.g., adding significance stars, changing decimal places) would require
changing code in every format-specific implementation.

The established resolution to this tension in software design is content-presentation
separation: a content layer that describes what the table contains, and a presentation
layer that describes how to render it in a specific format. This is the Model-View
separation at the core of web frameworks, document object models, and typesetting
systems. EconFlow's reporting engine applies this pattern to econometric tables.

A secondary design question was extensibility. Journals have different table formatting
requirements. Some require booktabs LaTeX; others require specific column separators
or footnote conventions. Some researchers want Word output; others want Quarto-compatible
Markdown. The reporting engine needed to support new output formats without requiring
changes to the table builders.

---

## Decision

We adopt **content-presentation separation** as the architectural principle of the
reporting engine, implemented as two independent layers: table builders (content) and
renderers (presentation), connected by a format-agnostic `ReportTable` data structure.

**The `ReportTable` data structure** is the contract between the two layers. It contains:
- `title: str` — the table's caption
- `columns: list[str]` — column headers
- `rows: list[list[str]]` — pre-formatted cell values as strings
- `tablenotes: str | None` — footnote text
- `metadata: dict` — arbitrary key-value pairs for renderer-specific extensions

Critically, `ReportTable.rows` contains **pre-formatted strings**, not numbers. The
formatting decisions (number of decimal places, significance stars, parenthetical
standard errors) are made in the table builder before the `ReportTable` is created.
The renderer receives a `ReportTable` with cells that are already formatted strings;
it adds structure (LaTeX column separators, HTML `<td>` tags, CSV commas) but does
not make any formatting decisions about the content.

This contract has an important consequence: the content of the table is the same
regardless of which renderer is used. The same `ReportTable` rendered to LaTeX and
rendered to CSV must contain identical cell values. The only difference is structural.

**Table builders** are functions (not classes) that accept one or more `EstimationResult`
objects and return a `ReportTable`. They are not registered plugins; they are public
functions in `outputs.tables`. This is intentional: table builders are domain logic
(they know what a "regression comparison table" means) and are not expected to be
extended by third parties in the same way as renderers. The eight table builders are:
`build_regression_table`, `build_summary_stats_table`, `build_balance_table`,
`build_correlation_table`, `build_robustness_table`, `build_sensitivity_table`,
`build_falsification_table`, `build_heterogeneity_table`.

**Renderers** are `BaseRenderer` subclasses registered via `@register_renderer(id)`.
`BaseRenderer.render(table: ReportTable) -> str` is the single abstract method.
The five registered renderers are `csv`, `html`, `json`, `latex`, and `markdown`.
The `latex` renderer produces booktabs-formatted LaTeX using `\toprule`, `\midrule`,
`\bottomrule`, and `\footnotesize` footnote blocks. Renderer IDs are specified in
`outputs.yaml`; the pipeline calls `get_renderer(id).render(table)` without knowing
which renderer is active.

**`PublicationBundle`** orchestrates the writing of all tables and figures to an output
directory. It accepts a list of `(table, renderer_ids)` pairs, calls the appropriate
renderer for each, and writes the results to files with deterministic names. It
validates all renderer IDs at construction time and raises `RendererError` on unknown IDs
before any rendering begins, preventing partial output directories.

**Figure builders** follow the same pattern as table builders: functions that accept
estimation results and return `ReportFigure` objects. Unlike table builders, figure
builders are currently partially implemented (two of seven are functional at v0.7).
The `ReportFigure` data structure holds the figure alongside its caption and metadata.
Figure rendering is format-agnostic at the data layer; the rendering step is format-
specific (PNG, SVG, PDF) and handled separately.

---

## Alternatives Considered

### Alternative 1: Format-Specific Builders

`build_latex_regression_table()`, `build_csv_regression_table()`, etc. Each format
has its own builder functions that produce format-specific strings directly.

**Why not chosen:** Any change to regression table content (e.g., adding a new
diagnostic row, changing significance star conventions) would require modifying every
format-specific builder. With five formats and eight table types, this means forty
functions, each of which must be changed in lockstep. The content-presentation
separation reduces this to eight table builder changes and zero renderer changes.

### Alternative 2: Pandas `DataFrame` as the Intermediate Representation

Table builders produce pandas DataFrames. Renderers call `df.to_latex()`,
`df.to_csv()`, `df.to_html()`, etc.

**Why not chosen:** Pandas' built-in formatters do not produce publication-standard
LaTeX (no booktabs, no tablenotes, no footnote blocks). `df.to_latex()` produces
output that requires manual post-processing before it can be submitted to a journal.
More fundamentally, using a DataFrame as the intermediate representation means that
the rendering logic is partly in the DataFrame's format methods (which cannot be
customized without monkey-patching) and partly in post-processing code. The
`ReportTable` representation gives the renderer complete control over output structure.

### Alternative 3: Jinja2 Templates

Each output format is a Jinja2 template. Table builders produce a context dictionary;
renderers are template invocations.

**Why not chosen:** Jinja2 templates are appropriate when the structure of the output
is highly variable and the template author needs full control over whitespace and
layout. For tables, the structure is highly regular: header row, data rows, optional
footer. Jinja2 adds a template file dependency (which must be distributed with the
package) and a template engine dependency for a use case that is adequately served by
string formatting. Template rendering would also make the renderer plugin interface
more complex: a renderer that is a Jinja2 template is not straightforwardly a
`BaseRenderer` subclass.

### Alternative 4: LaTeX as the Single Output Format

The reporting engine produces LaTeX only. Conversion to other formats (PDF, HTML,
Word) is delegated to LaTeX-based converters (Pandoc, `latexmk`).

**Why not chosen:** This would make the reporting engine unavailable on systems without
a LaTeX installation, which includes many institutional computing environments and
virtually all Windows research machines. It would also make CSV output (needed for
replication package data files) impossible without an external tool. LaTeX is one
of the five output formats; it is not the universal output format.

---

## Trade-offs

**Accepted costs:**

- Pre-formatting cells as strings before building the `ReportTable` means that a
  downstream process cannot re-format the numbers (e.g., switch from three decimal
  places to two without rebuilding the table). This is intentional: the formatted
  string is the content of the table, not a number to be formatted later.

- The `ReportTable` model does not support merged cells, multi-level headers, or
  conditional formatting. These are intentional limitations: they keep the
  content-presentation contract simple. Tables with these requirements must be
  handled by format-specific post-processing outside EconFlow.

- Figure builders are functions rather than registered plugins. This means that
  a third-party figure type cannot be added by the same mechanism as a renderer.
  This is accepted for v1.0; a figure builder registry may be added in a future
  sprint if the need arises.

**Realized benefits:**

- Adding a new output format (e.g., Quarto, DOCX) requires writing one `BaseRenderer`
  subclass. All eight table types and both figure types become available in the new
  format immediately, without modifying any table builder.

- The regression table builder is the single source of truth for how EconFlow formats
  coefficients, standard errors, and significance stars. Any change to formatting
  convention is made once and propagates to all output formats.

- `PublicationBundle.write()` produces a deterministic directory structure. Two
  identical runs produce byte-identical output directories, enabling the
  `ReproducibilityCertificate` to hash output files and detect any change.

---

## Consequences

**Immediate consequences:**

1. Table builders must not perform format-specific operations. No table builder may
   produce LaTeX markup, HTML tags, or CSV delimiters. All cells must be plain strings.

2. Renderers must not make content decisions. No renderer may add significance stars,
   change decimal places, or omit rows based on their values. Renderers add structure;
   they do not alter content.

3. The `ReportTable.metadata` field is the escape hatch for renderer-specific
   extensions. A renderer that needs additional information (e.g., column alignment
   hints for LaTeX) reads it from `metadata`. Table builders that know their output
   may be rendered to a specific format may set `metadata` fields, but must not
   require any specific renderer.

4. All registered renderer IDs must be declared in `outputs.yaml`. Renderer IDs that
   appear in `outputs.yaml` but are not registered raise `RendererError` at
   `PublicationBundle` construction time, before any rendering begins.

**Architectural constraints imposed:**

- The `render(table: ReportTable) -> str` signature is frozen. No renderer may accept
  additional arguments. Renderer-specific configuration is communicated through
  `ReportTable.metadata` or through the renderer's `__init__()` parameters.

- Renderer IDs must be stable across EconFlow versions. A configuration file that
  specifies `renderer: latex` must continue to work after any EconFlow update. Adding
  a new renderer ID is not a breaking change; removing one is.

---

## Future Implications

**ADR-005-F1 (Planned):** Five figure builder implementations. `DistributionPlot`,
`EventStudyPlot`, `ResidualPlot`, `HeteroscedasticityPlot`, and `PanelTrendsPlot`
are stubs at v0.7. All five must be implemented before v1.0 (see V1_RELEASE_CRITERIA §6.2).
Event study plots should be prioritized given their prevalence in difference-in-differences
research.

**ADR-005-F2 (Under consideration):** LaTeX compile verification. A `validate` step
in `PublicationBundle.write()` that invokes `pdflatex` (when available) on the generated
LaTeX and confirms zero errors. This catches formatting errors before the researcher
discovers them during submission.

**ADR-005-F3 (Under consideration):** DOCX renderer. A `BaseRenderer` subclass that
produces `.docx` output using `python-docx`. This is the most frequently requested
format among researchers who submit to journals that require Word manuscripts.

**ADR-005-F4 (Contingent):** Figure builder registry. If third-party figure types
become a common need, a `@register_figure_builder(id)` decorator will be added, making
figure builders pluggable by the same mechanism as renderers.

---

## Cross References

- `src/econflow/outputs/model.py` — `ReportTable`, `ReportFigure` data structures
- `src/econflow/outputs/base.py` — `BaseRenderer` abstract class
- `src/econflow/outputs/registry.py` — renderer registry
- `src/econflow/outputs/renderers/` — five renderer implementations
- `src/econflow/outputs/tables/` — eight table builder implementations
- `src/econflow/outputs/figures/` — figure builder implementations
- `src/econflow/outputs/bundle.py` — `PublicationBundle`
- `docs/architecture/REPORTING_ENGINE.md` — reporting engine architecture document
- `docs/architecture/MILESTONE_v0.7.md` §1.6 — reporting capability assessment
- `docs/roadmap/V1_RELEASE_CRITERIA.md` §6 — reporting engine release criteria
- ADR-001 — Plugin Registry (renderer registration mechanism)
- ADR-002 — Configuration-First Design (renderer IDs specified in `outputs.yaml`)
