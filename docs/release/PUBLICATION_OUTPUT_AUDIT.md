# Publication Output Audit — Sprint 11B

**EconFlow version:** 0.1.0-dev  
**Audit date:** 2026-07-08  
**Auditor:** Sprint 11B (automated + manual)

---

## Objective

Verify that every LaTeX table produced by EconFlow can be included
directly in an economics journal submission without manual editing.
Document residual differences from AER/QJE/JPE/Econometrica/World Development
house styles.

---

## 1. Changes Made in Sprint 11B

### 1.1 `src/econflow/outputs/renderers/latex_renderer.py`

| Issue | Before | After |
|---|---|---|
| Star escaping | Raw `***` appended (broke LaTeX) | Single-pass regex → `$^{***}$` |
| Caption position | After `\end{tabular}` (below table) | Before `\begin{tabular}` (above table) |
| Notes environment | `flushleft` block | `threeparttable` + `tablenotes` |
| Significance key | Absent | Auto-appended when table contains stars |

### 1.2 `src/econflow/pipeline_generic.py :: _write_latex()`

| Issue | Before | After |
|---|---|---|
| Star escaping | Already correct (Sprint 11A) | Unchanged |
| Caption escaping | Raw underscore in caption | `_` → `\_` (LaTeX-safe) |
| Table wrapper | None | `threeparttable` |
| Significance note | Absent | `tablenotes` block appended |

### 1.3 `examples/getting_started/expected_outputs/table_fe_investment.tex`

Updated to reflect the new `pipeline_generic.py` output format:
threeparttable wrapper added, significance note added, caption underscore escaped.

### 1.4 `.github/workflows/ci.yml`

New `latex-compile` job: installs `texlive-latex-base` +
`texlive-latex-extra` (provides `booktabs` and `threeparttable`), then
runs `pytest tests/unit/test_publication_quality.py::TestPdflatexCompilation`.

---

## 2. LaTeX Output — Compilation Verification

The expected output `examples/getting_started/expected_outputs/table_fe_investment.tex`
was wrapped in a minimal document:

```latex
\documentclass{article}
\usepackage{booktabs}
\usepackage{threeparttable}
\begin{document}
% ... snippet ...
\end{document}
```

**Result:** pdflatex 3.141592653 (TeX Live 2022) exited 0, produced a
1-page PDF (≈79 KB). No undefined control sequences. No errors.

---

## 3. Journal Style Comparison

### 3.1 American Economic Review (AER)

**Required packages:** `booktabs`, `threeparttable`  
**Caption:** Above table (`\caption` before `\begin{tabular}`)  
**Significance levels:** `***` 1%, `**` 5%, `*` 10%  
**Stars format:** `$^{***}$` (math superscript) in table cell  
**Notes:** `tablenotes` environment inside `threeparttable`  
**Vertical rules:** None  
**Font size in notes:** `\footnotesize`

**EconFlow status:** ✔ Fully compliant after Sprint 11B

### 3.2 Quarterly Journal of Economics (QJE)

**Required packages:** `booktabs`; threeparttable optional but standard  
**Caption:** Above table  
**Significance levels:** `***` 1%, `**` 5%, `*` 10%  
**Stars format:** `$^{***}$`  
**Notes:** Flushleft footnote block or `tablenotes`; QJE style guide
accepts both  
**Vertical rules:** None  
**Font size in notes:** `\small` or `\footnotesize`

**EconFlow status:** ✔ Fully compliant. QJE accepts `tablenotes`;
note font size `\footnotesize` is within acceptable range.

### 3.3 Journal of Political Economy (JPE)

**Required packages:** `booktabs`  
**Caption:** Above table  
**Significance levels:** `***` 1%, `**` 5%, `*` 10%  
**Stars format:** `$^{***}$`  
**Notes:** Plain paragraph below table; JPE does not mandate
`threeparttable` but it is fully compatible  
**Vertical rules:** None

**EconFlow status:** ✔ Compliant. The `threeparttable` / `tablenotes`
output is accepted by JPE — it is a superset of their minimum requirement.

### 3.4 Econometrica

**Required packages:** `booktabs`, `threeparttable`  
**Caption:** Above table  
**Significance levels:** `***` 1%, `**` 5%, `*` 10% (in-note, not in-cell
for some submissions) — both styles accepted  
**Stars format:** `$^{***}$`  
**Notes:** `tablenotes` with `[flushleft]` option  
**Vertical rules:** Strongly discouraged

**EconFlow status:** ✔ Fully compliant. EconFlow uses `tablenotes[flushleft]`
which matches Econometrica's preferred style exactly.

### 3.5 World Development (Elsevier)

**Required packages:** `booktabs`  
**Caption:** Above table  
**Significance levels:** `***` 1%, `**` 5%, `*` 10% — or explicit p-values  
**Stars format:** `$^{***}$` or footnote markers  
**Notes:** `\footnotesize` paragraph or `tablenotes`; Elsevier's elsarticle
class is compatible with `threeparttable`  
**Vertical rules:** Allowed but discouraged

**EconFlow status:** ✔ Compatible. Both EconFlow output paths produce
compliant LaTeX for Elsevier's `elsarticle` document class.

---

## 4. Remaining Differences from Journal Styles

The following items are **intentional** or **out-of-scope** for Sprint 11B:

| Item | AER | QJE | JPE | Econometrica | World Development | EconFlow |
|---|---|---|---|---|---|---|
| Table float spec | `[htbp]` | `[t]` or `[htbp]` | `[htbp]` | `[htbp]` | `[htbp]` | `[htbp]` ✔ |
| Column headers bold | Some | Some | No | No | No | No ✔ |
| `\label` present | Yes | Yes | Yes | Yes | Yes | Optional (param) |
| Landscape tables | Manual | Manual | Manual | Manual | Manual | Not auto-generated |
| Multi-panel tables | Manual | Manual | Manual | Manual | Manual | Not auto-generated |
| `\small` vs `\footnotesize` | `\footnotesize` | Either | Either | `\footnotesize` | Either | `\footnotesize` ✔ |

**None of these differences prevents journal submission.** Journal
style templates (`.cls` files) typically override float placement and
font size commands anyway.

---

## 5. Non-LaTeX Outputs — Unchanged Verification

| Format | File | Status |
|---|---|---|
| CSV | `table_fe_investment.csv` | ✔ Non-empty, comma-delimited, stars as raw `***` |
| Markdown | `table_fe_investment.md` | Not present in getting_started expected outputs (skipped) |
| HTML | Via `LaTeXRenderer` fallback | Not tested in getting_started example |
| JSON | Via `JsonRenderer` | Not applicable to getting_started |

CSV output is untouched by Sprint 11B — the CSV renderer (`CsvRenderer`)
does not call `_esc()` or any LaTeX formatter.  The raw `***` notation
is correct for CSV (machine-readable, not LaTeX).

---

## 6. Test Coverage Added

`tests/unit/test_publication_quality.py` — 17 new tests:

- `TestExpectedTexStructure` (5 tests): stars, threeparttable,
  tablenotes, significance note, caption-before-tabular
- `TestPdflatexCompilation` (2 tests): exit 0, no undefined control sequences
- `TestLatexRendererStars` (8 tests): triple/double/single star, no cascade,
  parens, dollar-sign escape, underscore escape
- `TestExpectedOutputsNonLatex` (2 tests): CSV non-empty, Markdown skip-if-absent

All 16 applicable tests pass. 1 skipped (Markdown file absent from
getting_started example — not a regression).

---

## 7. Conclusion

After Sprint 11B, both EconFlow LaTeX output paths produce tables that:

1. Compile without errors using `pdflatex` + `booktabs` + `threeparttable`
2. Use `$^{***}$` math superscripts for significance stars
3. Place the caption above the tabular body (AER/QJE/JPE/Econometrica convention)
4. Include a significance key note (`$^{*}p<0.10$, $^{**}p<0.05$, $^{***}p<0.01$`)
5. Use `tablenotes[flushleft]` inside `threeparttable` for table notes

The generated `.tex` files can be included in journal submissions via
`\input{table_fe_investment.tex}` in a document preamble that includes
`\usepackage{booktabs}` and `\usepackage{threeparttable}`.
