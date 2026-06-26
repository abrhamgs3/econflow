"""
econflow.outputs.tables — LaTeX and CSV table renderer.

Renders econometric results tables in publication-ready LaTeX (``booktabs``
style) and machine-readable CSV formats.

Supported table types
---------------------
* **Regression table** — multi-column coefficient table with SEs, stars,
  and model statistics (N, R², FE indicators).
* **Descriptive statistics** — mean, SD, min, p25, median, p75, max.
* **Diagnostic summary** — Hausman, J-test, CD test statistics in a
  compact panel.

Usage (once implemented)
-------------------------
    from econflow.outputs.tables import TableRenderer
    renderer = TableRenderer("outputs/econflow/tables/")
    renderer.regression_table(results, filename="table2_main.tex")
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from econflow.estimation.base import EstimationResult
from econflow.outputs.base import BaseRenderer


class TableRenderer(BaseRenderer):
    """
    Renders coefficient tables to LaTeX (``.tex``) and CSV (``.csv``).

    Parameters
    ----------
    output_dir:
        Directory where table files are written.
    sig_levels:
        Significance thresholds for star notation (default: 10 %, 5 %, 1 %).
    float_fmt:
        printf-style format string for floating-point values.
    """

    renderer_name = "table"

    def __init__(
        self,
        output_dir: str | Path,
        sig_levels: tuple[float, ...] = (0.1, 0.05, 0.01),
        float_fmt: str = "{:.3f}",
        overwrite: bool = True,
    ) -> None:
        super().__init__(output_dir, overwrite)
        self.sig_levels = sig_levels
        self.float_fmt = float_fmt

    # ------------------------------------------------------------------
    # BaseRenderer interface
    # ------------------------------------------------------------------

    def render(self, data: Any, filename: str, **kwargs: Any) -> Path:
        """
        Dispatch to the appropriate sub-renderer based on *data* type and
        *kwargs*.
        """
        raise NotImplementedError

    # ------------------------------------------------------------------
    # Specialised renderers
    # ------------------------------------------------------------------

    def regression_table(
        self,
        results: dict[str, EstimationResult],
        filename: str,
        variables: list[str] | None = None,
        caption: str = "",
        label: str = "",
    ) -> Path:
        """
        Render a multi-column regression table to LaTeX and CSV.

        Parameters
        ----------
        results:
            Mapping of column header → EstimationResult.
        filename:
            Output file stem (extension added automatically).
        variables:
            Rows to include; ``None`` uses all common regressors.
        caption / label:
            LaTeX caption and ``\\label{}`` string.
        """
        raise NotImplementedError

    def descriptive_stats(
        self,
        df: pd.DataFrame,
        columns: list[str] | None = None,
        filename: str = "descriptive_stats",
    ) -> Path:
        """Render a descriptive statistics table."""
        raise NotImplementedError

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _format_cell(self, estimate: float, se: float, pvalue: float) -> str:
        """Format a single (estimate, SE) cell with significance stars."""
        raise NotImplementedError

    def _booktabs_header(self, columns: list[str]) -> str:
        """Generate a LaTeX booktabs header row."""
        raise NotImplementedError
