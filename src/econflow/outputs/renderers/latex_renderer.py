"""
econflow.outputs.renderers.latex_renderer — LaTeX (booktabs) table renderer.

Produces publication-quality LaTeX tables using the ``booktabs`` package
(``\\toprule``, ``\\midrule``, ``\\bottomrule``).  Column alignment is
right-aligned for numeric columns and left-aligned for the row-label column.
"""

from __future__ import annotations

from typing import Any

from econflow.outputs.base import BaseRenderer
from econflow.outputs.model import ReportTable
from econflow.outputs.registry import register_renderer


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
    """Escape for LaTeX but preserve significance stars (which use **)."""
    stars = ""
    stripped = text.rstrip("*")
    stars = text[len(stripped):]
    return _escape_latex(stripped) + stars


@register_renderer(
    "latex",
    label="LaTeX (booktabs)",
    file_extension=".tex",
    notes=(
        "Publication-quality LaTeX using booktabs; requires \\usepackage{booktabs}. "
        "Footer notes use a plain flushleft block — no extra packages needed."
    ),
)
class LaTeXRenderer(BaseRenderer):
    """
    Render a :class:`ReportTable` as a ``booktabs`` LaTeX table.

    The output is a complete ``table`` environment with a ``tabular``
    body.  Labels and notes are escaped but significance stars (``*``)
    are preserved verbatim.

    Footer notes are rendered inside a ``flushleft`` environment placed
    after the ``tabular`` body — no additional packages are required.

    Parameters (passed via **kwargs to render())
    -------------------------------------------
    label:
        LaTeX label for cross-referencing (e.g. ``"tab:main"``).
    placement:
        Table placement specifier (default ``"htbp"``).
    font_size:
        LaTeX font-size command (default ``""`` — inherits from document).
    center:
        Whether to wrap in ``\\centering`` (default ``True``).
    """

    renderer_id = "latex"
    name = "LaTeX (booktabs)"
    file_extension = ".tex"

    def render(
        self,
        table: ReportTable,
        *,
        label: str = "",
        placement: str = "htbp",
        font_size: str = "",
        center: bool = True,
        **kwargs: Any,
    ) -> str:
        n_cols = len(table.columns)
        col_spec = "l" + "r" * n_cols  # left label col + right numeric cols

        lines: list[str] = []
        lines.append(f"\\begin{{table}}[{placement}]")
        if center:
            lines.append("  \\centering")
        if font_size:
            lines.append(f"  {font_size}")

        lines.append(f"  \\begin{{tabular}}{{{col_spec}}}")
        lines.append("    \\toprule")

        # Column headers
        header_cells = [""] + [_esc(c) for c in table.columns]
        lines.append("    " + " & ".join(header_cells) + " \\\\")
        lines.append("    \\midrule")

        for row in table.rows:
            if row.row_type == "separator":
                lines.append("    \\midrule")
                continue

            # Primary row
            label_text = _esc(row.label)
            if row.bold:
                label_text = f"\\textbf{{{label_text}}}"
            if row.italic:
                label_text = f"\\textit{{{label_text}}}"

            cells = [label_text] + [
                _esc(row.cells.get(col, "")) for col in table.columns
            ]
            suffix = " \\\\" if not row.sub_cells else " \\\\ [-0.5ex]"
            lines.append("    " + " & ".join(cells) + suffix)

            # Sub-row (e.g. standard errors)
            if row.sub_cells:
                sub_cells = [""] + [
                    _esc(row.sub_cells.get(col, "")) for col in table.columns
                ]
                lines.append("    " + " & ".join(sub_cells) + " \\\\")

        lines.append("    \\bottomrule")
        lines.append("  \\end{tabular}")

        # Caption
        caption = _escape_latex(table.title)
        if table.subtitle:
            caption += f": {_escape_latex(table.subtitle)}"
        lines.append(f"  \\caption{{{caption}}}")

        if label:
            lines.append(f"  \\label{{{label}}}")

        # Notes — plain flushleft block; no threeparttable package required.
        if table.footer or table.notes:
            lines.append("  \\begin{flushleft}")
            lines.append("    \\footnotesize")
            for note in table.footer:
                lines.append(f"    {_escape_latex(note)} \\\\")
            if table.notes:
                note_text = _escape_latex(table.notes)
                lines.append(f"    \\textit{{Note:}} {note_text} \\\\")
            lines.append("  \\end{flushleft}")

        lines.append("\\end{table}")
        return "\n".join(lines) + "\n"
