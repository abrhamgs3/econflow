"""
econflow.outputs.figures.ci_plot — Confidence interval comparison plot (full).

Plots the same focal coefficient from multiple :class:`EstimationResult`
objects side-by-side, showing how the estimate and its uncertainty vary
across specifications.
"""

from __future__ import annotations

from typing import Any

import scipy.stats as stats

from econflow.estimation.result import EstimationResult
from econflow.outputs.figures.base import FigureBuilder
from econflow.outputs.model import ReportFigure


class CIPlot(FigureBuilder):
    """
    Build a confidence-interval comparison plot.

    Data layout::

        data = {
            "labels": [...],         # one label per specification
            "coefficients": [...],   # point estimate per specification
            "ci_lower": [...],       # lower CI bound
            "ci_upper": [...],       # upper CI bound
            "pvalues": [...],        # p-value (or None) per specification
            "focal_variable": str,   # regressor being compared
        }
        config = {
            "confidence_level": 0.95,
            "zero_line": True,
        }
    """

    figure_type = "ci_plot"
    name = "CI Comparison Plot"

    def build(
        self,
        results: list[EstimationResult],
        focal_variable: str,
        *,
        title: str = "Confidence Interval Comparison",
        spec_labels: list[str] | None = None,
        confidence_level: float = 0.95,
        metadata: dict[str, Any] | None = None,
    ) -> ReportFigure:
        """
        Build the CI comparison figure.

        Parameters
        ----------
        results:
            Ordered list of estimation results.
        focal_variable:
            The regressor whose coefficient is compared across specs.
        title:
            Plot title.
        spec_labels:
            Labels for each specification.  Defaults to ``["(1)", "(2)", ...]``.
        confidence_level:
            Confidence level for the interval.
        metadata:
            Arbitrary key-value pairs.

        Returns
        -------
        ReportFigure
        """
        if not results:
            raise ValueError("results must contain at least one EstimationResult")

        alpha = 1.0 - confidence_level
        z = float(stats.norm.ppf(1.0 - alpha / 2.0))
        labels = spec_labels or [f"({i + 1})" for i in range(len(results))]
        if len(labels) != len(results):
            raise ValueError("spec_labels length must match results length")

        coefs, ci_lo, ci_hi, pvals = [], [], [], []
        for r in results:
            if focal_variable in r.params.index:
                c = float(r.params[focal_variable])
                se = (
                    float(r.std_err[focal_variable])
                    if focal_variable in r.std_err.index
                    else None
                )
                pv = (
                    float(r.pvalues[focal_variable])
                    if focal_variable in r.pvalues.index
                    else None
                )
                coefs.append(c)
                ci_lo.append((c - z * se) if se is not None else None)
                ci_hi.append((c + z * se) if se is not None else None)
                pvals.append(pv)
            else:
                coefs.append(None)
                ci_lo.append(None)
                ci_hi.append(None)
                pvals.append(None)

        return ReportFigure(
            title=title,
            figure_type=self.figure_type,
            data={
                "labels": labels,
                "coefficients": coefs,
                "ci_lower": ci_lo,
                "ci_upper": ci_hi,
                "pvalues": pvals,
                "focal_variable": focal_variable,
            },
            config={
                "confidence_level": confidence_level,
                "zero_line": True,
            },
            metadata=metadata or {},
        )
