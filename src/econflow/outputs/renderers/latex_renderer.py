"""
econflow.outputs.renderers.latex_renderer — LaTeX (booktabs) table renderer.

Produces publication-quality LaTeX tables using the ``booktabs`` package
(``\toprule``, ``\midrule``, ``\bottomrule``).  Column alignment is
right-aligned for numeric columns and left-aligned for the row-label column.
"""

from __future__ import annotations

import re
from typing import Any

from econflow.outputs.base import BaseRenderer
from econflow.outputs.model import ReportTable
from econflow.outputs.registry import register_renderer

# Significance-note LaTeX fragment appended automatically when any cell
# contains significance stars.
_SIG_NOTE = r"$^{*}p<0.10$, $^{**}p<0.05$, $^{***}p<0.01$"

# Map star-count → math-mode superscript (single-pass replacement)
_STAR_MAP: dict[int, str] = {3: "$^{***}$", 2: "$^{**}$", 1: "$^{*}$"}


def _escape_latex(text: str) -> str:
    """Escape special LaTeX characters in *text*."""
    replacements = [
        ("\\", r"\textbackslash{}"),
        ("&",  r"\&"),
        ("%",  r"\%"),
        ("$",  r"\$"),
        ("#",  r"\#"),
        ("_",  r"\_"),
        ("{",  r"\{"),
        ("}",  r"\}"),
        ("~",  r"\textasciitilde{}"),
        ("^",  r"\textasciicircum{}"),
    ]
    for old, new in replacements:
        text = text.replace(old, new)
    return text


def _esc(text: str) -> str:
    """Escape *text* for LaTeX, converting significance stars to math superscripts.

    Uses a single-pass regex so that ``***`` is rendered as ``$^{***}$``
    without cascading through the ``**`` and ``*`` patterns.  Non-star
    portions are passed through :func:`_escape_latex` so that special
    characters are properly escaped.
    """
    # Unicode/symbol substitutions first (before star splitting)
    text = text.replace("R² within", "$R^2$ within").replace("—", "---")

    # Split on star-runs; escape non-star portions, replace star-runs with
    # the appropriate math superscript.
    parts: list[str] = []
    last = 0
    for m in re.finditer(r"\*+", text):
        parts.append(_escape_latex(text[last : m.start()]))
        parts.append(_STAR_MAP[min(len(m.group()), 3)])
        last = m.end()
    parts.append(_escape_latex(text[last:]))
    return "".join(parts)


def _table_has_stars(table: ReportTable) -> bool:
    """Return ``True`` if any data cell in *table* contains significance stars."""
    for row in table.rows:
        for v in row.cells.values():
            if "*" in v:
                return True
        if row.sub_cells:
            for v in row.sub_cells.values():
                if "*" in v:
                    return True
    return False


@register_renderer(
    "latex",
    label="LaTeX (booktabs + threeparttable)",
    file_extension=".tex",
    notes=(
        "Publication-quality LaTeX using booktabs and threeparttable; requires "
        r"\usepackage{booktabs} and \usepackage{threeparttable}. "
        "Significance stars are rendered as math superscripts ($^{***}$)."
    ),
)
class LaTeXRenderer(BaseRenderer):
    """
    Render a :class:`ReportTable` as a ``booktabs`` LaTeX table.

    The output is a complete ``table`` environment with the caption placed
    *above* the tabular body (standard journal convention).  When notes or a
    significance key are present the tabular is wrapped in a
    ``threeparttable`` environment so that note width is constrained to the
    table width.

    Significance stars (``*``, ``**``, ``***``) are rendered as math
    superscripts (``$^{*}$``, ``$^{**}$``, ``$^{***}$``) via a single-pass
    regex that avoids cascading substitutions.

    Parameters (passed via **kwargs to render())
    -------------------------------------------
    label:
        LaTeX label for cross-referencing (e.g. ``"tab:main"``).
    placement:
        Table placement specifier (default ``"htbp"``).
    font_size:
        LaTeX font-size command (default ``""`` — inherits from document).
    center:
        Whether to emit ``\\centering`` (default ``True``).
    add_significance_note:
        Automatically append a significance key when the table contains
        stars (default ``True``).
    use_threeparttable:
        Wrap in ``threeparttable`` when notes are present (default ``True``).
    """

    renderer_id = "latex"
    name = "LaTeX (booktabs + threeparttable)"
    file_extension = ".tex"

    def render(
        self,
        table: ReportTable,
        *,
        label: str = "",
        placement: str = "htbp",
        font_size: str = "",
        center: bool = True,
        add_significance_note: bool = True,
        use_threeparttable: bool = True,
        **kwargs: Any,
    ) -> str:
        n_cols = len(table.columns)
        col_spec = "l" + "r" * n_cols  # left label col + right numeric cols

        # Collect note lines (footer, notes, auto-significance)
        note_lines: list[str] = []
        for note in table.footer:
            note_lines.append(_escape_latex(note))
        if table.notes:
            note_lines.append(r"\textit{Note:} " + _escape_latex(table.notes))
        if add_significance_note and _table_has_stars(table):
            note_lines.append(_SIG_NOTE)

        has_notes = bool(note_lines)
        wrap = use_threeparttable and has_notes

        lines: list[str] = []
        lines.append(f"\\begin{{table}}[{placement}]")
        if center:
            lines.append("  \\centering")
        if font_size:
            lines.append(f"  {font_size}")

        # Caption ABOVE the tabular (AER/QJE/JPE/Econometrica convention)
        caption_text = _escape_latex(table.title)
        if table.subtitle:
            caption_text += f": {_escape_latex(table.subtitle)}"
        lines.append(f"  \\caption{{{caption_text}}}")
        if label:
            lines.append(f"  \\label{{{label}}}")

        if wrap:
            lines.append("  \\begin{threeparttable}")

        ind = "    " if wrap else "  "
        lines.append(f"{ind}\\begin{{tabular}}{{{col_spec}}}")
        lines.append(f"{ind}  \\toprule")

        # Column headers
        header_cells = [""] + [_esc(c) for c in table.columns]
        lines.append(f"{ind}  " + " & ".join(header_cells) + " \\\\")
        lines.append(f"{ind}  \\midrule")

        for row in table.rows:
            if row.row_type == "separator":
                lines.append(f"{ind}  \\midrule")
                continue

            row_label = _esc(row.label)
            if row.bold:
                row_label = f"\\textbf{{{row_label}}}"
            if row.italic:
                row_label = f"\\textit{{{row_label}}}"

            cells = [row_label] + [
                _esc(row.cells.get(col, "")) for col in table.columns
            ]
            suffix = " \\\\" if not row.sub_cells else " \\\\ [-0.5ex]"
            lines.append(f"{ind}  " + " & ".join(cells) + suffix)

            if row.sub_cells:
                sub_cells = [""] + [
                    _esc(row.sub_cells.get(col, "")) for col in table.columns
                ]
                lines.append(f"{ind}  " + " & ".join(sub_cells) + " \\\\")

        lines.append(f"{ind}  \\bottomrule")
        lines.append(f"{ind}\\end{{tabular}}")

        if wrap:
            lines.append("    \\begin{tablenotes}[flushleft]")
            lines.append("      \\footnotesize")
            for note in note_lines:
                lines.append(f"      \\item {note}")
            lines.append("    \\end{tablenotes}")
            lines.append("  \\end{threeparttable}")
        elif has_notes:
            # Fallback: use_threeparttable=False but notes exist
            lines.append("  \\begin{flushleft}")
            lines.append("    \\footnotesize")
            for note in note_lines:
                lines.append(f"    {note} \\\\")
            lines.append("  \\end{flushleft}")

        lines.append("\\end{table}")
        return "\n".join(lines) + "\n"
