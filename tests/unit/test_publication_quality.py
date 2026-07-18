"""
tests/unit/test_publication_quality.py
=======================================

Sprint 11B -- Publication Quality regression tests.

Guards against regressions in:

  PQ-01  LaTeX significance stars -- must be $^{***}$ math superscripts
  PQ-02  LaTeX output must contain threeparttable structure
  PQ-03  LaTeX output must contain significance note
  PQ-04  Expected .tex output compiles to PDF with pdflatex
  PQ-05  latex_renderer.py star escaping (via LaTeXRenderer.render())
  PQ-06  CSV and Markdown outputs exist and are non-empty (guard unchanged)
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

EXAMPLES_DIR = Path(__file__).parents[2] / "examples" / "getting_started"
EXPECTED_DIR = EXAMPLES_DIR / "expected_outputs"
TEX_FILE = EXPECTED_DIR / "table_fe_investment.tex"


def _pdflatex_available() -> bool:
    return shutil.which("pdflatex") is not None


# ---------------------------------------------------------------------------
# PQ-01 / PQ-02 / PQ-03: Structure of expected .tex output
# ---------------------------------------------------------------------------

class TestExpectedTexStructure:
    """The expected output file must contain the required LaTeX constructs."""

    @pytest.fixture(autouse=True)
    def require_tex(self) -> None:
        if not TEX_FILE.exists():
            pytest.skip(f"Expected output not found: {TEX_FILE}")

    def _text(self) -> str:
        return TEX_FILE.read_text(encoding="utf-8")

    def test_stars_are_math_superscripts(self) -> None:
        """PQ-01: Stars must be in $^{...}$ form, not raw asterisks."""
        text = self._text()
        assert "$^{***}$" in text or "$^{**}$" in text or "$^{*}$" in text
        assert "$^{$" not in text, "Cascaded star substitution detected"

    def test_contains_threeparttable(self) -> None:
        """PQ-02: Table must use threeparttable environment."""
        assert "\\begin{threeparttable}" in self._text()

    def test_contains_significance_note(self) -> None:
        """PQ-03: Significance key must be present."""
        text = self._text()
        assert "p<0.10" in text or "p<0.05" in text or "p<0.01" in text, (
            "Significance note missing from expected output"
        )

    def test_contains_tablenotes(self) -> None:
        """PQ-03b: tablenotes environment should be present."""
        assert "\\begin{tablenotes}" in self._text()

    def test_caption_before_tabular(self) -> None:
        """Caption must appear before \\begin{tabular} (above-table convention)."""
        text = self._text()
        cap_pos = text.find("\\caption")
        tab_pos = text.find("\\begin{tabular}")
        assert cap_pos != -1, "No \\caption found"
        assert tab_pos != -1, "No \\begin{tabular} found"
        assert cap_pos < tab_pos, (
            f"Caption at pos {cap_pos} must be before tabular at pos {tab_pos}"
        )


# ---------------------------------------------------------------------------
# PQ-04: pdflatex compilation
# ---------------------------------------------------------------------------

MINIMAL_PREAMBLE = r"""\documentclass{article}
\usepackage{booktabs}
\usepackage{threeparttable}
\begin{document}
"""

MINIMAL_POSTAMBLE = r"""
\end{document}
"""


@pytest.mark.skipif(
    not _pdflatex_available(),
    reason="pdflatex not found — install texlive-latex-extra to run this test",
)
class TestPdflatexCompilation:
    """Compile the expected .tex snippet with pdflatex."""

    @pytest.fixture(autouse=True)
    def require_tex(self) -> None:
        if not TEX_FILE.exists():
            pytest.skip(f"Expected output not found: {TEX_FILE}")

    def test_compiles_to_pdf(self, tmp_path: Path) -> None:
        """PQ-04: pdflatex must exit 0 and produce a PDF."""
        snippet = TEX_FILE.read_text(encoding="utf-8")
        doc = MINIMAL_PREAMBLE + snippet + MINIMAL_POSTAMBLE
        src = tmp_path / "test_pub.tex"
        src.write_text(doc, encoding="utf-8")

        result = subprocess.run(
            ["pdflatex", "-interaction=nonstopmode", str(src)],
            cwd=str(tmp_path),
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert result.returncode == 0, (
            f"pdflatex failed (exit {result.returncode}):\n"
            + result.stdout[-2000:]
        )
        pdf = tmp_path / "test_pub.pdf"
        assert pdf.exists(), "pdflatex exited 0 but no PDF produced"
        assert pdf.stat().st_size > 1000, "PDF is suspiciously small"

    def test_no_undefined_control_sequences(self, tmp_path: Path) -> None:
        """PQ-04b: pdflatex output must not contain undefined control sequences."""
        snippet = TEX_FILE.read_text(encoding="utf-8")
        doc = MINIMAL_PREAMBLE + snippet + MINIMAL_POSTAMBLE
        src = tmp_path / "test_pub.tex"
        src.write_text(doc, encoding="utf-8")

        result = subprocess.run(
            ["pdflatex", "-interaction=nonstopmode", str(src)],
            cwd=str(tmp_path),
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert "Undefined control sequence" not in result.stdout, (
            "LaTeX undefined control sequence:\n"
            + "\n".join(
                line for line in result.stdout.splitlines()
                if "Undefined" in line or "Error" in line
            )
        )


# ---------------------------------------------------------------------------
# PQ-05: LaTeXRenderer star escaping
# ---------------------------------------------------------------------------

class TestLatexRendererStars:
    """latex_renderer._esc() must produce correct math superscripts."""

    def _esc(self, text: str) -> str:
        from econflow.outputs.renderers.latex_renderer import _esc
        return _esc(text)

    def test_triple_star(self) -> None:
        assert self._esc("0.1145***") == "0.1145$^{***}$"

    def test_double_star(self) -> None:
        assert self._esc("0.0872**") == "0.0872$^{**}$"

    def test_single_star(self) -> None:
        assert self._esc("0.0456*") == "0.0456$^{*}$"

    def test_no_star(self) -> None:
        assert self._esc("0.1234") == "0.1234"

    def test_no_cascade(self) -> None:
        result = self._esc("0.1145***")
        assert "$^{$" not in result, f"Cascade in: {result!r}"

    def test_cell_with_parens(self) -> None:
        assert self._esc("(0.0234)***") == "(0.0234)$^{***}$"

    def test_dollar_special_chars_escaped(self) -> None:
        """Dollar sign in non-star context must be escaped."""
        result = self._esc("$1.00")
        # The $ must be escaped but stars still become $^{...}$
        assert "\\$" in result or "\$" in result

    def test_underscore_escaped(self) -> None:
        result = self._esc("col_name")
        assert "col\\_name" in result or "col\_name" in result


# ---------------------------------------------------------------------------
# PQ-06: Non-LaTeX outputs exist and are plausibly structured
# ---------------------------------------------------------------------------

class TestExpectedOutputsNonLatex:
    """CSV and Markdown outputs (if present) should be non-empty."""

    def test_csv_is_nonempty(self) -> None:
        csv = EXPECTED_DIR / "table_fe_investment.csv"
        if not csv.exists():
            pytest.skip("CSV expected output not found")
        text = csv.read_text(encoding="utf-8")
        assert len(text.strip()) > 10
        assert "," in text, "CSV must contain commas"

    def test_markdown_is_nonempty(self) -> None:
        md = EXPECTED_DIR / "table_fe_investment.md"
        if not md.exists():
            pytest.skip("Markdown expected output not found")
        text = md.read_text(encoding="utf-8")
        assert "|" in text, "Markdown table must contain pipe characters"
