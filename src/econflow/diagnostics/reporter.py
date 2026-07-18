"""
econflow.diagnostics.reporter — Unified diagnostics reporter.

Aggregates outputs from all diagnostic tests into a single
:class:`DiagnosticReport` that can be:

* Printed as a Rich-formatted table to the terminal.
* Serialised to JSON for provenance archiving.
* Embedded in the LaTeX/PDF output report.

Usage (once implemented)
-------------------------
    from econflow.diagnostics.reporter import DiagnosticReporter
    reporter = DiagnosticReporter(fe_result, re_result, iv_result, gmm_result, panel)
    report = reporter.run_all()
    report.print()
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from econflow.estimation.base import EstimationResult


@dataclass
class DiagnosticReport:
    """
    Container for all diagnostic test results for a single model run.

    Attributes
    ----------
    hausman:
        Result of the Hausman test (if both FE and RE results supplied).
    sargan_hansen:
        Result of the J-test (if IV/GMM result supplied).
    arellano_bond:
        AR(1) and AR(2) test results (if GMM result supplied).
    pesaran_cd:
        Cross-sectional dependence test result.
    extra:
        Any additional diagnostic results.
    """

    hausman: Any | None = None
    sargan_hansen: Any | None = None
    arellano_bond: Any | None = None
    pesaran_cd: Any | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def print(self) -> None:
        """Render the report as a Rich table to stdout."""
        raise NotImplementedError

    def to_dict(self) -> dict[str, Any]:
        """Serialise the report to a plain JSON-serialisable dictionary."""
        raise NotImplementedError

    def to_latex(self) -> str:
        """Render the report as a LaTeX table fragment."""
        raise NotImplementedError


class DiagnosticReporter:
    """
    Orchestrates all diagnostic tests and assembles a :class:`DiagnosticReport`.

    Parameters
    ----------
    panel:
        Wide-format panel DataFrame used for estimation.
    fe_result:
        Fixed-effects estimation result (required for Hausman, CD tests).
    re_result:
        Random-effects result (required for Hausman test).
    iv_result:
        IV estimation result (required for J-test).
    gmm_result:
        GMM estimation result (required for AB serial tests and J-test).
    entity_col / time_col:
        Panel dimension identifiers.
    """

    def __init__(
        self,
        panel: pd.DataFrame,
        fe_result: EstimationResult | None = None,
        re_result: EstimationResult | None = None,
        iv_result: EstimationResult | None = None,
        gmm_result: EstimationResult | None = None,
        entity_col: str = "iso3",
        time_col: str = "year",
    ) -> None:
        self.panel = panel
        self.fe_result = fe_result
        self.re_result = re_result
        self.iv_result = iv_result
        self.gmm_result = gmm_result
        self.entity_col = entity_col
        self.time_col = time_col

    def run_all(self) -> DiagnosticReport:
        """
        Execute all applicable diagnostic tests and return a
        :class:`DiagnosticReport`.
        """
        raise NotImplementedError
