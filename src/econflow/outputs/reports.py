"""
econflow.outputs.reports — PDF report compiler stub.

Assembles a complete research-report PDF from rendered tables, figures, and
project metadata.  The compilation approach (Jinja2 + latexmk, Pandoc, or
direct LaTeX write) is an implementation detail deferred to the first
concrete implementation.

This stub exposes only the public interface contract:
:meth:`PDFReportCompiler.compile`.  Internal helpers, template engine
selection, and LaTeX engine configuration are intentionally omitted here
and belong in the implementation, not the interface.

Usage (once implemented)
-------------------------
    from econflow.outputs.reports import PDFReportCompiler
    compiler = PDFReportCompiler(config, output_dir="outputs/econflow")
    pdf_path = compiler.compile(results, diagnostics)
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from econflow.core.config import Settings
from econflow.outputs.base import BaseRenderer


class PDFReportCompiler(BaseRenderer):
    """
    Compiles a full PDF research report from estimation results and diagnostics.

    Parameters
    ----------
    settings:
        Project :class:`~econflow.core.config.Settings` supplying
        title, author, and abstract metadata.
    output_dir:
        Directory where the compiled PDF is written.
    """

    renderer_name = "pdf_report"

    def __init__(
        self,
        settings: Settings,
        output_dir: str | Path,
        overwrite: bool = True,
    ) -> None:
        super().__init__(output_dir, overwrite)
        self.settings = settings

    # ------------------------------------------------------------------
    # BaseRenderer interface
    # ------------------------------------------------------------------

    def render(self, data: Any, filename: str, **kwargs: Any) -> Path:
        """Delegate to :meth:`compile`."""
        raise NotImplementedError

    # ------------------------------------------------------------------
    # Public compilation API
    # ------------------------------------------------------------------

    def compile(self, results: dict, diagnostics: Any) -> Path:
        """
        Render all artefacts and produce a standalone PDF.

        Parameters
        ----------
        results:
            Mapping of specification name → EstimationResult.
        diagnostics:
            :class:`~econflow.diagnostics.reporter.DiagnosticReport` instance.

        Returns
        -------
        Path
            Absolute path to the compiled ``.pdf`` file.
        """
        raise NotImplementedError
