"""
econflow.outputs.figures — Coefficient plot and diagnostic figure renderer.

Produces publication-quality figures using ``matplotlib`` / ``seaborn``:

* **Coefficient path plot** — point estimates + 95 % CI across specifications.
* **Quantile coefficient plot** — β(τ) path across quantiles with CI band.
* **Residual diagnostics** — Q-Q plot, residual-vs-fitted scatter.
* **Heatmap** — Data coverage or missing-value heatmap.
* **Time-series overlay** — AIPI and TFP growth over time for selected countries.

All figures are saved as both ``.pdf`` (for LaTeX) and ``.png`` (for
preview / web).

Usage (once implemented)
-------------------------
    from econflow.outputs.figures import FigureRenderer
    renderer = FigureRenderer("outputs/econflow/figures/", dpi=300)
    renderer.coefficient_path_plot(comparison, variable="aipi", filename="fig3")
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from econflow.outputs.base import BaseRenderer
from econflow.sensitivity.comparison import ResultsComparison


class FigureRenderer(BaseRenderer):
    """
    Renders research figures to PDF and PNG.

    Parameters
    ----------
    output_dir:
        Directory where figure files are written.
    dpi:
        Resolution for raster (PNG) output.
    style:
        Matplotlib style string or path (default: ``"seaborn-v0_8-paper"``).
    """

    renderer_name = "figure"

    def __init__(
        self,
        output_dir: str | Path,
        dpi: int = 300,
        style: str = "seaborn-v0_8-paper",
        overwrite: bool = True,
    ) -> None:
        super().__init__(output_dir, overwrite)
        self.dpi = dpi
        self.style = style

    # ------------------------------------------------------------------
    # BaseRenderer interface
    # ------------------------------------------------------------------

    def render(self, data: Any, filename: str, **kwargs: Any) -> Path:
        """Dispatch to sub-renderer based on *data* type."""
        raise NotImplementedError

    # ------------------------------------------------------------------
    # Specialised figure methods
    # ------------------------------------------------------------------

    def coefficient_path_plot(
        self,
        comparison: ResultsComparison,
        variable: str,
        filename: str,
        title: str = "",
    ) -> list[Path]:
        """
        Coefficient path plot: point estimates ± CI across specifications.

        Returns paths to the saved PDF and PNG files.
        """
        raise NotImplementedError

    def quantile_coefficient_plot(
        self,
        quantile_data: pd.DataFrame,
        variable: str,
        filename: str,
        title: str = "",
    ) -> list[Path]:
        """
        Plot β(τ) path across quantiles with shaded 95 % CI band.

        *quantile_data* is the output of
        :meth:`~econflow.estimation.quantile.PanelQuantile.coefficient_plot_data`.
        """
        raise NotImplementedError

    def coverage_heatmap(
        self,
        coverage_df: pd.DataFrame,
        filename: str,
        title: str = "Data coverage",
    ) -> list[Path]:
        """Render a country × year missing-value heatmap."""
        raise NotImplementedError

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _save(self, fig: Any, stem: Path) -> list[Path]:
        """Save *fig* to PDF and PNG at *stem* and return both paths."""
        raise NotImplementedError
