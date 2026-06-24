"""
econflow.sensitivity.comparison — Results comparison across specifications.

Aligns :class:`~econflow.estimation.base.EstimationResult` objects from multiple
specifications and produces coefficient tables and visualisations that
highlight robustness (or lack thereof) of the main findings.

Key outputs
-----------
* **Coefficient table** — estimates with SEs, significance stars, and
  specification labels suitable for LaTeX.
* **Coefficient path plot** — point estimates ± 95 % CI across specifications
  for a focal variable.
* **Robustness statistics** — percentage of specifications where the focal
  variable is significant at 5 %, and the median/mean estimate.

Usage (once implemented)
-------------------------
    from econflow.sensitivity.comparison import ResultsComparison
    comp = ResultsComparison(results)
    table = comp.coefficient_table(variables=["aipi"])
    fig = comp.coefficient_path_plot(variable="aipi")
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from econflow.estimation.base import EstimationResult


class ResultsComparison:
    """
    Side-by-side comparison of results from multiple specifications.

    Parameters
    ----------
    results:
        Mapping of specification name → :class:`EstimationResult`.
    """

    def __init__(self, results: dict[str, EstimationResult]) -> None:
        self.results = results

    # ------------------------------------------------------------------
    # Tabular summaries
    # ------------------------------------------------------------------

    def coefficient_table(
        self,
        variables: list[str] | None = None,
        sig_levels: tuple[float, ...] = (0.1, 0.05, 0.01),
    ) -> pd.DataFrame:
        """
        Return a wide-format DataFrame with one row per variable and one
        column-pair per specification (estimate, SE).

        *variables* filters to a subset; ``None`` includes all.
        """
        raise NotImplementedError

    def robustness_summary(self, variable: str) -> dict[str, Any]:
        """
        Compute robustness statistics for *variable* across all specifications.

        Returns a dict with keys:
        ``n_specs``, ``n_significant``, ``pct_significant``,
        ``median_estimate``, ``mean_estimate``, ``min_estimate``,
        ``max_estimate``.
        """
        raise NotImplementedError

    # ------------------------------------------------------------------
    # Plot data helpers
    # ------------------------------------------------------------------

    def coefficient_path_data(self, variable: str) -> pd.DataFrame:
        """
        Return a tidy DataFrame with columns
        ``["spec", "estimate", "ci_lower", "ci_upper"]``
        for *variable* across all specifications.
        """
        raise NotImplementedError
