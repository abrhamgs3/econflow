"""
econflow.processing.ai_index — AI Proxy Index construction.

Constructs a composite AI Proxy Index (AIPI) from multiple underlying
indicators that proxy AI adoption and diffusion across countries and years.

Indicator candidates
--------------------
* Internet penetration (% population) — WB ``IT.NET.USER.ZS``
* ICT goods imports (% total imports) — WB ``TM.VAL.ICTG.ZS.UN``
* R&D expenditure (% GDP) — WB ``GB.XPD.RSDV.GD.ZS``
* High-tech exports (% manufactured exports) — WB ``TX.VAL.TECH.MF.ZS``
* Patent applications (residents) — WB ``IP.PAT.RESD``
* ICT value-added share (% GDP) — OECD ISIC Rev.4

Aggregation methods
-------------------
* **PCA** — First principal component of normalised indicators.
* **Equal-weight** — Arithmetic mean of Z-scored indicators.
* **Factor** — Confirmatory factor model score (future extension).

Usage (once implemented)
-------------------------
    from econflow.processing.ai_index import AIProxyIndexBuilder
    builder = AIProxyIndexBuilder(method="pca", indicators=["IT.NET.USER.ZS", ...])
    panel["aipi"] = builder.fit_transform(panel)
"""

from __future__ import annotations

from typing import Literal

import pandas as pd

AggMethod = Literal["pca", "equal_weight", "factor"]


class AIProxyIndexBuilder:
    """
    Constructs the AI Proxy Index from a set of underlying indicators.

    Parameters
    ----------
    indicators:
        Column names in the input panel to use as AIPI components.
    method:
        Aggregation method.  ``"pca"`` uses the first principal component;
        ``"equal_weight"`` averages Z-scored columns.
    normalise:
        Whether to Z-score each indicator before aggregation.
    """

    def __init__(
        self,
        indicators: list[str],
        method: AggMethod = "pca",
        normalise: bool = True,
    ) -> None:
        self.indicators = indicators
        self.method = method
        self.normalise = normalise
        self._fitted: bool = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def fit(self, df: pd.DataFrame) -> AIProxyIndexBuilder:
        """
        Learn normalisation parameters and PCA loadings from *df*.

        Returns
        -------
        self
            For method chaining.
        """
        raise NotImplementedError

    def transform(self, df: pd.DataFrame) -> pd.Series:
        """
        Apply the fitted index construction to *df*.

        Returns
        -------
        pd.Series
            AIPI scores indexed the same as *df*.

        Raises
        ------
        RuntimeError
            If :meth:`fit` has not been called first.
        """
        raise NotImplementedError

    def fit_transform(self, df: pd.DataFrame) -> pd.Series:
        """Convenience wrapper: ``fit(df).transform(df)``."""
        return self.fit(df).transform(df)

    def loadings(self) -> pd.Series:
        """
        Return component loadings (PCA) or weights (equal-weight).

        Raises
        ------
        RuntimeError
            If :meth:`fit` has not been called.
        """
        raise NotImplementedError

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _zscore(self, df: pd.DataFrame) -> pd.DataFrame:
        """Z-score normalise *indicators* columns in *df*."""
        raise NotImplementedError

    def _pca_score(self, df: pd.DataFrame) -> pd.Series:
        """Extract first principal component scores from *df*."""
        raise NotImplementedError
