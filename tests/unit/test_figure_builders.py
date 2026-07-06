"""
Unit tests for outputs.figures — CoefficientPlot and CIPlot.

CoefficientPlot:
- Returns ReportFigure with correct figure_type
- Correct arrays (variables, coefficients, ci_lower, ci_upper, pvalues)
- CI bounds computed from z-score
- sort_by options
- exclude_intercept filters const
- variable subset selection
- variable_labels mapping

CIPlot:
- Returns ReportFigure
- One entry per result
- Correct focal_variable coefficient extracted
- Missing variable filled with None
- Mismatched spec_labels raises ValueError
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pandas as pd
import pytest
import scipy.stats as stats

from econflow.outputs.figures import CIPlot, CoefficientPlot
from econflow.outputs.model import ReportFigure

# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

def _make_result(params, pvalues, std_err):
    r = MagicMock()
    r.params = pd.Series(params)
    r.pvalues = pd.Series(pvalues)
    r.std_err = pd.Series(std_err)
    return r


@pytest.fixture()
def single_result():
    return _make_result(
        params={"const": 1.0, "x1": 0.543, "x2": -0.234},
        pvalues={"const": 0.001, "x1": 0.005, "x2": 0.06},
        std_err={"const": 0.2, "x1": 0.123, "x2": 0.145},
    )


@pytest.fixture()
def two_results():
    r1 = _make_result(
        params={"x1": 0.543, "x2": -0.234},
        pvalues={"x1": 0.005, "x2": 0.06},
        std_err={"x1": 0.123, "x2": 0.145},
    )
    r2 = _make_result(
        params={"x1": 0.501, "x2": -0.189},
        pvalues={"x1": 0.02, "x2": 0.15},
        std_err={"x1": 0.215, "x2": 0.133},
    )
    return [r1, r2]


# ---------------------------------------------------------------------------
# CoefficientPlot
# ---------------------------------------------------------------------------

class TestCoefficientPlot:
    def test_returns_report_figure(self, single_result):
        fig = CoefficientPlot().build(result=single_result)
        assert isinstance(fig, ReportFigure)

    def test_figure_type(self, single_result):
        fig = CoefficientPlot().build(result=single_result)
        assert fig.figure_type == "coefficient_plot"

    def test_excludes_intercept_by_default(self, single_result):
        fig = CoefficientPlot().build(result=single_result)
        assert "const" not in fig.data["variables"]

    def test_includes_intercept_when_requested(self, single_result):
        fig = CoefficientPlot().build(result=single_result, exclude_intercept=False)
        assert "const" in fig.data["variables"]

    def test_correct_variables(self, single_result):
        fig = CoefficientPlot().build(result=single_result)
        assert set(fig.data["variables"]) == {"x1", "x2"}

    def test_coefficients_match(self, single_result):
        fig = CoefficientPlot().build(result=single_result)
        idx = fig.data["variables"].index("x1")
        assert abs(fig.data["coefficients"][idx] - 0.543) < 1e-9

    def test_ci_lower_less_than_coef(self, single_result):
        fig = CoefficientPlot().build(result=single_result)
        for c, lo in zip(fig.data["coefficients"], fig.data["ci_lower"]):
            if lo is not None:
                assert lo < c

    def test_ci_upper_greater_than_coef(self, single_result):
        fig = CoefficientPlot().build(result=single_result)
        for c, hi in zip(fig.data["coefficients"], fig.data["ci_upper"]):
            if hi is not None:
                assert hi > c

    def test_ci_95_z_value(self, single_result):
        """95% CI: half-width = 1.96 * se."""
        fig = CoefficientPlot().build(result=single_result, confidence_level=0.95)
        z = stats.norm.ppf(0.975)
        idx = fig.data["variables"].index("x1")
        expected_lo = 0.543 - z * 0.123
        assert abs(fig.data["ci_lower"][idx] - expected_lo) < 1e-6

    def test_sort_by_coefficient(self, single_result):
        fig = CoefficientPlot().build(result=single_result, sort_by="coefficient")
        coefs = fig.data["coefficients"]
        assert coefs == sorted(coefs)

    def test_sort_by_label(self, single_result):
        fig = CoefficientPlot().build(result=single_result, sort_by="label")
        labels = [lbl.lower() for lbl in fig.data["labels"]]
        assert labels == sorted(labels)

    def test_variable_subset(self, single_result):
        fig = CoefficientPlot().build(result=single_result, variables=["x1"])
        assert fig.data["variables"] == ["x1"]

    def test_variable_labels(self, single_result):
        fig = CoefficientPlot().build(
            result=single_result,
            variable_labels={"x1": "AI Index", "x2": "Capital"},
        )
        assert "AI Index" in fig.data["labels"]

    def test_confidence_level_in_config(self, single_result):
        fig = CoefficientPlot().build(result=single_result, confidence_level=0.90)
        assert fig.config["confidence_level"] == 0.90

    def test_pvalues_present(self, single_result):
        fig = CoefficientPlot().build(result=single_result)
        assert fig.data["pvalues"] is not None
        assert len(fig.data["pvalues"]) == len(fig.data["variables"])

    def test_metadata_stored(self, single_result):
        fig = CoefficientPlot().build(result=single_result, metadata={"spec": "fe"})
        assert fig.metadata["spec"] == "fe"


# ---------------------------------------------------------------------------
# CIPlot
# ---------------------------------------------------------------------------

class TestCIPlot:
    def test_returns_report_figure(self, two_results):
        fig = CIPlot().build(results=two_results, focal_variable="x1")
        assert isinstance(fig, ReportFigure)

    def test_figure_type(self, two_results):
        fig = CIPlot().build(results=two_results, focal_variable="x1")
        assert fig.figure_type == "ci_plot"

    def test_focal_variable_stored(self, two_results):
        fig = CIPlot().build(results=two_results, focal_variable="x1")
        assert fig.data["focal_variable"] == "x1"

    def test_two_labels(self, two_results):
        fig = CIPlot().build(results=two_results, focal_variable="x1")
        assert len(fig.data["labels"]) == 2

    def test_default_spec_labels(self, two_results):
        fig = CIPlot().build(results=two_results, focal_variable="x1")
        assert fig.data["labels"] == ["(1)", "(2)"]

    def test_custom_spec_labels(self, two_results):
        fig = CIPlot().build(
            results=two_results,
            focal_variable="x1",
            spec_labels=["OLS", "FE"],
        )
        assert fig.data["labels"] == ["OLS", "FE"]

    def test_coefficient_values(self, two_results):
        fig = CIPlot().build(results=two_results, focal_variable="x1")
        assert abs(fig.data["coefficients"][0] - 0.543) < 1e-9
        assert abs(fig.data["coefficients"][1] - 0.501) < 1e-9

    def test_ci_bounds(self, two_results):
        fig = CIPlot().build(results=two_results, focal_variable="x1", confidence_level=0.95)
        z = stats.norm.ppf(0.975)
        expected_lo = 0.543 - z * 0.123
        assert abs(fig.data["ci_lower"][0] - expected_lo) < 1e-6

    def test_missing_variable_is_none(self):
        r1 = _make_result(
            params={"x1": 0.5}, pvalues={"x1": 0.01}, std_err={"x1": 0.1}
        )
        r2 = _make_result(
            params={"x2": 0.3}, pvalues={"x2": 0.05}, std_err={"x2": 0.1}
        )
        fig = CIPlot().build(results=[r1, r2], focal_variable="x1")
        assert fig.data["coefficients"][1] is None
        assert fig.data["ci_lower"][1] is None

    def test_empty_results_raises(self):
        with pytest.raises(ValueError, match="at least one"):
            CIPlot().build(results=[], focal_variable="x1")

    def test_mismatched_labels_raises(self, two_results):
        with pytest.raises(ValueError, match="spec_labels length"):
            CIPlot().build(
                results=two_results,
                focal_variable="x1",
                spec_labels=["Only One"],
            )

    def test_confidence_level_in_config(self, two_results):
        fig = CIPlot().build(results=two_results, focal_variable="x1", confidence_level=0.90)
        assert fig.config["confidence_level"] == 0.90

    def test_zero_line_in_config(self, two_results):
        fig = CIPlot().build(results=two_results, focal_variable="x1")
        assert fig.config["zero_line"] is True
