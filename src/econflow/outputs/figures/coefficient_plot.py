"""
econflow.outputs.figures.coefficient_plot — Coefficient plot figure builder.

Produces a :class:`ReportFigure` containing the data required to render a
forest-style coefficient plot: one dot per regressor, horizontal CI bars,
and a vertical zero line.

The figure carries raw numeric data (not rendered graphics) so that any
downstream renderer (matplotlib, plotly, vega, etc.) can draw it.
"""

from __future__ import annotations

from typing import Any

import scipy.stats as stats

from econflow.estimation.result import EstimationResult
from econflow.outputs.figures.base import FigureBuilder
from econflow.outputs.model import ReportFigure


class CoefficientPlot(FigureBuilder):
    """
    Build a coefficient plot for one :class:`EstimationResult`.

    The resulting :class:`ReportFigure` stores::

        data = {
            "variables": [...],          # regressor labels in order
            "coefficients": [...],       # point estimates
            "ci_lower": [...],           # lower confidence bound
            "ci_upper": [...],           # upper confidence bound
            "pvalues": [...],            # p-values (or None)
        }
        config = {
            "confidence_level": 0.95,
            "zero_line": True,
            "sort_by": "coefficient",    # "coefficient" | "label" | "input"
        }
    """

    figure_type = "coefficient_plot"
    name = "Coefficient Plot"

    def build(
        self,
        result: EstimationResult,
        *,
        title: str = "Coefficient Plot",
        variables: list[str] | None = None,
        variable_labels: dict[str, str] | None = None,
        confidence_level: float = 0.95,
        sort_by: str = "input",
        exclude_intercept: bool = True,
        metadata: dict[str, Any] | None = None,
    ) -> ReportFigure:
        """
        Build the coefficient plot figure.

        Parameters
        ----------
        result:
            A single estimation result.
        title:
            Plot title.
        variables:
            Subset of regressors to include, in order.
        variable_labels:
            Mapping of regressor name to display label.
        confidence_level:
            Confidence level for the interval (e.g. 0.95 → 95% CI).
        sort_by:
            ``"input"`` preserves *variables* order; ``"coefficient"`` sorts
            ascending; ``"label"`` sorts alphabetically.
        exclude_intercept:
            Drop the intercept / constant term from the plot.
        metadata:
            Arbitrary key-value pairs stored in the figure.

        Returns
        -------
        ReportFigure
        """
        varlabels = variable_labels or {}
        alpha = 1.0 - confidence_level
        z = float(stats.norm.ppf(1.0 - alpha / 2.0))

        # Build variable list
        if variables is not None:
            selected = [v for v in variables if v in result.params.index]
        else:
            selected = list(result.params.index)

        if exclude_intercept:
            selected = [v for v in selected if v not in ("const", "Intercept", "_const")]

        # Extract arrays
        coefs = [float(result.params[v]) for v in selected]
        sderr = [
            float(result.std_err[v]) if v in result.std_err.index else None
            for v in selected
        ]
        pvals = [
            float(result.pvalues[v]) if v in result.pvalues.index else None
            for v in selected
        ]
        ci_lower = [
            (c - z * se) if se is not None else None
            for c, se in zip(coefs, sderr)
        ]
        ci_upper = [
            (c + z * se) if se is not None else None
            for c, se in zip(coefs, sderr)
        ]
        labels = [varlabels.get(v, v) for v in selected]

        # Sort
        indices = list(range(len(selected)))
        if sort_by == "coefficient":
            indices.sort(key=lambda i: coefs[i])
        elif sort_by == "label":
            indices.sort(key=lambda i: labels[i].lower())
        # "input" → keep as-is

        def _reorder(lst: list) -> list:
            return [lst[i] for i in indices]

        return ReportFigure(
            title=title,
            figure_type=self.figure_type,
            data={
                "variables": _reorder(selected),
                "labels": _reorder(labels),
                "coefficients": _reorder(coefs),
                "ci_lower": _reorder(ci_lower),
                "ci_upper": _reorder(ci_upper),
                "pvalues": _reorder(pvals),
            },
            config={
                "confidence_level": confidence_level,
                "zero_line": True,
                "sort_by": sort_by,
                "exclude_intercept": exclude_intercept,
            },
            metadata=metadata or {},
        )
