# EconFlow Plugin SDK

**Version:** 1.0 (Sprint 9)  
**Stability:** Stable  
**Date:** 2026-06-28  
**Audience:** Plugin authors — researchers and engineers extending EconFlow with custom
estimators, data connectors, diagnostics, integrity checks, renderers, figure builders,
and configuration extensions.

---

> **Scope of this document.** This document describes the public, stable plugin
> interfaces that EconFlow commits to maintaining across all v1.x releases. A plugin
> written against this document will not require modification to work on any EconFlow
> version between 1.0 and 2.0, subject to the compatibility guarantees in §12.
>
> This document does not describe EconFlow's internal implementation. Do not import
> from paths not listed in this document — they are not part of the public API and
> may change in any release without notice.

---

## Table of Contents

1. [Quick Start](#1-quick-start)
2. [Estimator Plugins](#2-estimator-plugins)
3. [Connector Plugins](#3-connector-plugins)
4. [Diagnostic Plugins](#4-diagnostic-plugins)
5. [Integrity Check Plugins](#5-integrity-check-plugins)
6. [Renderer Plugins](#6-renderer-plugins)
7. [Figure Builder Plugins](#7-figure-builder-plugins)
8. [Configuration Extensions](#8-configuration-extensions)
9. [Developer Guide](#9-developer-guide)
10. [Validation Rules](#10-validation-rules)
11. [Version Compatibility Policy](#11-version-compatibility-policy)
12. [Plugin Lifecycle](#12-plugin-lifecycle)
13. [Backward Compatibility Guarantees](#13-backward-compatibility-guarantees)

---

## 1. Quick Start

Install EconFlow as a dependency of your plugin package:

```toml
# pyproject.toml of your plugin package
[project]
name = "econflow-myplugin"
version = "0.1.0"
dependencies = ["econflow>=1.0,<2.0"]
```

Write a plugin module:

```python
# my_estimator.py
from econflow.estimation import BaseEstimator, EstimationResult
from econflow.estimation import register_estimator

@register_estimator("my_ols")
class MyOLS(BaseEstimator):
    """Minimal working estimator plugin."""

    def validate(self, data):
        self._require_columns(data, self.params["entity_col"],
                              self.params["time_col"],
                              self.params["dependent"])

    def fit(self, data):
        # ... your implementation ...
        return EstimationResult(
            params=..., std_err=..., pvalues=...,
            nobs=len(data), rsq=0.0,
            estimator_id="my_ols",
        )

    def diagnostics(self, result):
        return []  # no diagnostics; return empty list
```

Make it available in a pipeline by importing the module before calling
`econflow run` programmatically, or by declaring an entry point in your
`pyproject.toml` (see §9.3):

```toml
[project.entry-points."econflow.plugins"]
my_ols = "my_plugin_package.my_estimator"
```

### Plugin type summary

| Plugin type | Base class | Register decorator | Section |
|---|---|---|---|
| Estimator | `BaseEstimator` | `@register_estimator(id)` | §2 |
| Connector | `AbstractConnector` | `@register_connector(id)` | §3 |
| Diagnostic | `BaseDiagnostic` | `@register_diagnostic(id)` | §4 |
| Integrity check | `BaseIntegrityCheck` | `@register_integrity_check(id)` | §5 |
| Renderer | `BaseRenderer` | `@register_renderer(id)` | §6 |
| Figure builder | `BaseFigureBuilder` | `@register_figure_builder(id)` | §7 |
| Config extension | `BaseConfigExtension` | `@register_config_extension(id)` | §8 |

---

## 2. Estimator Plugins

Estimator plugins add new econometric methods to EconFlow. Once registered, an
estimator is available in `models.yaml` by its ID and is invoked automatically
by the pipeline and the `econflow run` command.

### 2.1 Imports

```python
from econflow.estimation import (
    BaseEstimator,
    EstimationResult,
    DiagnosticResult,
    EstimatorError,
    register_estimator,
    get_estimator,
    list_estimators,
)
```

### 2.2 Contract: `BaseEstimator`

```python
import abc
import pandas as pd
from econflow.estimation import EstimationResult, DiagnosticResult

class BaseEstimator(abc.ABC):
    """
    Abstract base class for all EconFlow econometric estimators.

    Subclass this, implement the three abstract methods, and decorate
    the class with ``@register_estimator(estimator_id)``.

    Parameters
    ----------
    params : dict, optional
        Estimator configuration. Common keys:

        ``entity_col`` (str)
            Column name identifying the cross-sectional unit.
            Default: ``"entity"``.

        ``time_col`` (str)
            Column name identifying the time period.
            Default: ``"time"``.

        ``dependent`` (str)
            Column name of the dependent (outcome) variable.

        ``controls`` (list[str])
            Column names of control variables.

        ``cluster_col`` (str, optional)
            Column name for clustered standard errors.

        ``weight_col`` (str, optional)
            Column name for observation weights.

    All additional estimator-specific parameters are passed through
    ``params`` as well.  The estimator is responsible for validating
    its own parameters in ``validate()``.
    """

    def __init__(self, params: dict | None = None) -> None: ...

    # ------------------------------------------------------------------
    # Abstract methods — must be implemented by every estimator plugin
    # ------------------------------------------------------------------

    @abc.abstractmethod
    def validate(self, data: pd.DataFrame) -> None:
        """
        Validate that ``data`` is suitable for estimation.

        This method is called before ``fit()``. It must raise
        ``EstimatorError`` if estimation cannot proceed. It must not
        modify ``data``.

        Typical checks:
        - Required columns are present
        - Sufficient observations (nobs > k parameters)
        - No infinite or all-NaN columns
        - Panel is balanced enough for the chosen estimator

        Parameters
        ----------
        data : pd.DataFrame
            The full, pre-filtered panel dataset.

        Raises
        ------
        EstimatorError
            If the data or parameters are unsuitable. The message must
            identify the specific problem and, where possible, suggest
            a remedy.

        Returns
        -------
        None
            Must return None. Any return value is ignored.

        Notes
        -----
        Do not call ``fit()`` from inside ``validate()``.
        Do not raise ``ValueError`` or ``TypeError`` — wrap them in
        ``EstimatorError`` so the CLI can display a clean message.
        """

    @abc.abstractmethod
    def fit(self, data: pd.DataFrame) -> EstimationResult:
        """
        Estimate the model and return a structured result.

        This method is called after ``validate()`` has returned without
        error. It must not call ``validate()`` again.

        Parameters
        ----------
        data : pd.DataFrame
            The full, pre-filtered panel dataset. Same object passed to
            ``validate()``. Do not modify it.

        Returns
        -------
        EstimationResult
            Must contain at minimum:
            - ``params``: pd.Series of coefficient estimates, indexed
              by variable name.
            - ``std_err``: pd.Series of standard errors, same index.
            - ``pvalues``: pd.Series of p-values, same index.
            - ``nobs``: int, number of observations used.
            - ``rsq``: float or None.
            - ``estimator_id``: str matching the registered ID.

        Raises
        ------
        EstimatorError
            On convergence failure, singular matrices, or any condition
            that prevents producing a valid result.

        Notes
        -----
        ``params``, ``std_err``, and ``pvalues`` must have identical
        indices. The index values are the variable names that will appear
        in regression tables.

        Do not attach diagnostics to the result here; return them from
        ``diagnostics()`` instead.
        """

    @abc.abstractmethod
    def diagnostics(self, result: EstimationResult) -> list[DiagnosticResult]:
        """
        Run post-estimation diagnostics and return their results.

        This method is called automatically by ``run()`` after ``fit()``.
        Diagnostics that are integral to the estimator (e.g., first-stage
        F-statistic for IV, Sargan test for GMM) should be computed here.
        General diagnostics (Hausman test, Breusch-Pagan) are registered
        separately and run by the diagnostic registry; do not duplicate them.

        Parameters
        ----------
        result : EstimationResult
            The result returned by ``fit()``.

        Returns
        -------
        list[DiagnosticResult]
            May be empty. Each result's ``estimator_id`` field is set
            automatically by ``run()``; you do not need to set it.

        Notes
        -----
        This method must not raise an exception. If a diagnostic cannot
        be computed, return a ``DiagnosticResult`` with ``level="warn"``
        and an explanatory message rather than raising.
        """

    # ------------------------------------------------------------------
    # Concrete methods — available to all estimators, do not override
    # unless documented here
    # ------------------------------------------------------------------

    def run(self, data: pd.DataFrame) -> EstimationResult:
        """
        Execute the full estimation lifecycle: validate → fit → diagnostics.

        Called by the pipeline. Do not override this method.
        """
        ...

    def predict(
        self,
        data: pd.DataFrame,
        result: EstimationResult | None = None,
    ) -> pd.Series:
        """
        Generate fitted values or out-of-sample predictions.

        Optional. The default implementation raises ``NotImplementedError``.
        Override only if your estimator supports prediction.

        Parameters
        ----------
        data : pd.DataFrame
            Data to predict on. May be the training data or new data.
        result : EstimationResult, optional
            If None, ``run()`` is called first. Pass a result to avoid
            re-estimation.

        Returns
        -------
        pd.Series
            Predicted values, indexed identically to ``data``.
        """
        ...

    # ------------------------------------------------------------------
    # Protected helpers — available to subclasses
    # ------------------------------------------------------------------

    def _require_params(self, *keys: str) -> None:
        """
        Assert that all ``keys`` are present in ``self.params``.
        Raises ``EstimatorError`` if any are missing.
        """
        ...

    def _require_columns(self, data: pd.DataFrame, *cols: str) -> None:
        """
        Assert that all ``cols`` are present in ``data``.
        Raises ``EstimatorError`` if any are missing.
        """
        ...

    def _to_panel(
        self,
        data: pd.DataFrame,
        entity_col: str | None = None,
        time_col: str | None = None,
    ) -> pd.DataFrame:
        """
        Set a MultiIndex of (entity, time) on ``data`` for use with
        linearmodels. Returns a new DataFrame; does not modify ``data``.
        """
        ...

    def _provenance_stamp(self) -> dict:
        """
        Return a dict of estimator identity information for embedding
        in ``EstimationResult.provenance``.
        """
        ...
```

### 2.3 `EstimationResult` — the return contract

```python
from dataclasses import dataclass, field
from typing import Any
import pandas as pd
from econflow.estimation import DiagnosticResult

@dataclass
class EstimationResult:
    # Required fields — must be set by every estimator
    params: pd.Series          # coefficient estimates
    std_err: pd.Series         # standard errors (same index as params)
    pvalues: pd.Series         # p-values (same index as params)
    nobs: int                  # number of observations used
    rsq: float | None          # R-squared; None if not meaningful
    estimator_id: str          # matches the registered ID

    # Strongly recommended
    f_statistic: float | None = None
    f_pvalue: float | None = None
    entity_col: str = "entity"
    time_col: str = "time"
    entities: list[str] = field(default_factory=list)
    time_periods: list = field(default_factory=list)

    # Set automatically by run() — do not set manually
    diagnostic_results: list[DiagnosticResult] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    provenance: dict[str, Any] = field(default_factory=dict)

    # Escape hatch for estimator-specific metadata
    extra: dict[str, Any] = field(default_factory=dict)
```

**Invariants that every estimator must satisfy:**

- `params.index == std_err.index == pvalues.index` (identical, in identical order)
- `len(params) >= 1`
- `nobs >= 1`
- `estimator_id` equals the ID passed to `@register_estimator()`
- No element of `params`, `std_err`, or `pvalues` is `NaN` or `inf` without a
  corresponding entry in `warnings` explaining why

### 2.4 Registration

```python
from econflow.estimation import register_estimator

@register_estimator(
    "driscoll_kraay",
    label="Driscoll-Kraay Standard Errors",
    status="implemented",   # or "stub"
    notes="Suitable for panels with cross-sectional dependence.",
)
class DriscollKraayEstimator(BaseEstimator):
    ...
```

**Registration parameters:**

| Parameter | Type | Required | Description |
|---|---|---|---|
| `estimator_id` | str | Yes | Unique identifier. Used in `models.yaml` and `list_estimators()`. Must be a valid Python identifier containing only `[a-z0-9_]`. |
| `label` | str | No | Human-readable name shown in `econflow info`. Defaults to the class name. |
| `status` | str | No | `"implemented"` (default) or `"stub"`. Stubs appear in the registry but raise `NotImplementedError` on `fit()`. |
| `notes` | str | No | Free-text notes shown in `econflow info`. |

**Rules:**
- Registering a duplicate ID raises `RegistryError` immediately at import time.
- IDs are case-sensitive. `"OLS"` and `"ols"` are different IDs.
- IDs may not start with `_` or contain spaces or hyphens.

### 2.5 Complete working example

```python
"""
econflow_driscoll_kraay.py

Driscoll-Kraay (1998) standard errors for panel data.

Installation:
    pip install econflow-driscoll-kraay  # hypothetical package

Usage in models.yaml:
    models:
      - id: dk_fe
        estimator: driscoll_kraay
        params:
          entity_col: country
          time_col: year
          dependent: log_gdp
          controls: [log_trade, log_fdi]
          bandwidth: 3
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import scipy.linalg

from econflow.estimation import (
    BaseEstimator,
    DiagnosticResult,
    EstimationResult,
    EstimatorError,
    register_estimator,
)


@register_estimator(
    "driscoll_kraay",
    label="Driscoll-Kraay Standard Errors",
    notes="Non-parametric covariance estimator robust to cross-sectional "
          "dependence and heteroscedasticity.",
)
class DriscollKraayEstimator(BaseEstimator):
    """
    Pooled OLS with Driscoll-Kraay standard errors.

    References
    ----------
    Driscoll, J.C., & Kraay, A.C. (1998). Consistent covariance matrix
    estimation with spatially dependent panel data. Review of Economics
    and Statistics, 80(4), 549-560.
    """

    def validate(self, data: pd.DataFrame) -> None:
        entity_col = self.params.get("entity_col", "entity")
        time_col = self.params.get("time_col", "time")
        dependent = self.params.get("dependent")

        if not dependent:
            raise EstimatorError(
                "driscoll_kraay",
                "Parameter 'dependent' is required but was not supplied.",
            )

        self._require_columns(data, entity_col, time_col, dependent)

        controls = self.params.get("controls", [])
        if controls:
            self._require_columns(data, *controls)

        if data[dependent].isna().all():
            raise EstimatorError(
                "driscoll_kraay",
                f"Dependent variable '{dependent}' is all NaN.",
            )

        bandwidth = self.params.get("bandwidth", 3)
        if not isinstance(bandwidth, int) or bandwidth < 0:
            raise EstimatorError(
                "driscoll_kraay",
                f"Parameter 'bandwidth' must be a non-negative integer; "
                f"got {bandwidth!r}.",
            )

    def fit(self, data: pd.DataFrame) -> EstimationResult:
        entity_col = self.params.get("entity_col", "entity")
        time_col = self.params.get("time_col", "time")
        dependent = self.params.get("dependent")
        controls = self.params.get("controls", [])
        bandwidth = self.params.get("bandwidth", 3)

        regressors = controls if controls else []
        df = data[[entity_col, time_col, dependent] + regressors].dropna()

        T = df[time_col].nunique()
        X = pd.get_dummies(df[regressors], drop_first=True) if regressors else pd.DataFrame(index=df.index)
        X.insert(0, "_const", 1.0)
        y = df[dependent].values
        X_arr = X.values.astype(float)

        # OLS coefficients
        try:
            beta = np.linalg.lstsq(X_arr, y, rcond=None)[0]
        except np.linalg.LinAlgError as exc:
            raise EstimatorError("driscoll_kraay", f"OLS failed: {exc}") from exc

        resid = y - X_arr @ beta
        n, k = X_arr.shape

        # Driscoll-Kraay covariance
        S = self._dk_covariance(df, time_col, X_arr, resid, bandwidth, T)
        XtX_inv = np.linalg.pinv(X_arr.T @ X_arr)
        vcov = XtX_inv @ S @ XtX_inv
        se = np.sqrt(np.diag(vcov))
        t_stats = beta / se
        from scipy.stats import t as t_dist
        pvals = 2 * t_dist.sf(np.abs(t_stats), df=T - 1)

        index = X.columns.tolist()
        rsq = float(1 - np.var(resid) / np.var(y)) if np.var(y) > 0 else None

        return EstimationResult(
            params=pd.Series(beta, index=index),
            std_err=pd.Series(se, index=index),
            pvalues=pd.Series(pvals, index=index),
            nobs=int(n),
            rsq=rsq,
            estimator_id="driscoll_kraay",
            entity_col=entity_col,
            time_col=time_col,
            entities=df[entity_col].unique().tolist(),
            time_periods=sorted(df[time_col].unique().tolist()),
        )

    def diagnostics(self, result: EstimationResult) -> list[DiagnosticResult]:
        # No estimator-specific diagnostics for this estimator.
        # General diagnostics (Hausman, BP) are run by the registry.
        return []

    # ------------------------------------------------------------------
    # Private implementation helpers
    # ------------------------------------------------------------------

    def _dk_covariance(self, df, time_col, X, resid, bandwidth, T):
        """Compute Driscoll-Kraay sandwich covariance matrix."""
        times = sorted(df[time_col].unique())
        scores_by_t = {}
        for t in times:
            mask = df[time_col] == t
            Xt = X[mask]
            et = resid[mask]
            scores_by_t[t] = Xt.T @ et  # shape (k,)

        k = X.shape[1]
        S = np.zeros((k, k))
        for lag in range(bandwidth + 1):
            weight = 1.0 - lag / (bandwidth + 1)
            Gamma = np.zeros((k, k))
            for i, t in enumerate(times):
                if i + lag < len(times):
                    t_lag = times[i + lag]
                    Gamma += np.outer(scores_by_t[t], scores_by_t[t_lag])
            Gamma /= T
            S += weight * (Gamma + Gamma.T) if lag > 0 else weight * Gamma

        return S
```

### 2.6 Testing an estimator plugin

```python
# tests/test_driscoll_kraay.py
import numpy as np
import pandas as pd
import pytest

# Importing the module triggers registration
import econflow_driscoll_kraay  # noqa: F401

from econflow.estimation import get_estimator, EstimationResult


@pytest.fixture
def panel_data():
    """Minimal 10-country, 5-year balanced panel."""
    rng = np.random.default_rng(42)
    entities = [f"C{i:02d}" for i in range(10)]
    years = list(range(2000, 2005))
    rows = [
        {"country": c, "year": y,
         "log_gdp": rng.normal(10, 1),
         "log_trade": rng.normal(3, 0.5)}
        for c in entities for y in years
    ]
    return pd.DataFrame(rows)


def test_registration():
    """Connector must appear in the registry after import."""
    from econflow.estimation import list_estimators
    assert "driscoll_kraay" in [e["id"] for e in list_estimators()]


def test_returns_estimation_result(panel_data):
    """fit() must return EstimationResult with correct fields."""
    cls = get_estimator("driscoll_kraay")
    est = cls(params={
        "entity_col": "country",
        "time_col": "year",
        "dependent": "log_gdp",
        "controls": ["log_trade"],
        "bandwidth": 2,
    })
    result = est.run(panel_data)
    assert isinstance(result, EstimationResult)
    assert result.estimator_id == "driscoll_kraay"
    assert len(result.params) >= 1
    assert result.params.index.equals(result.std_err.index)
    assert result.params.index.equals(result.pvalues.index)
    assert result.nobs == len(panel_data)
    assert all(np.isfinite(result.params.values))
    assert all(np.isfinite(result.std_err.values))
    assert all(v >= 0 for v in result.pvalues.values)


def test_validate_raises_on_missing_column(panel_data):
    """validate() must raise EstimatorError for missing columns."""
    from econflow.estimation import EstimatorError
    cls = get_estimator("driscoll_kraay")
    est = cls(params={
        "entity_col": "country", "time_col": "year",
        "dependent": "nonexistent_column",
    })
    with pytest.raises(EstimatorError):
        est.run(panel_data)


def test_validate_raises_on_invalid_bandwidth(panel_data):
    """validate() must reject non-integer bandwidth."""
    from econflow.estimation import EstimatorError
    cls = get_estimator("driscoll_kraay")
    est = cls(params={
        "entity_col": "country", "time_col": "year",
        "dependent": "log_gdp", "bandwidth": "three",
    })
    with pytest.raises(EstimatorError):
        est.run(panel_data)
```

---

## 3. Connector Plugins

Connector plugins add new data sources to EconFlow. Once registered, a connector
is available to `econflow fetch --connector <id>` and to `DatasetManifest`.

### 3.1 Imports

```python
from econflow.ingestion import (
    AbstractConnector,
    ConnectorError,
    CacheManager,
    CacheCorruptionError,
    DatasetMetadata,
    DatasetManifest,
    ManifestEntry,
    DataValidator,
    DataValidationConfig,
    DataValidationReport,
    ValidationIssue,
    register_connector,
    get_connector,
    list_connectors,
)
```

### 3.2 Contract: `AbstractConnector`

```python
import abc
from pathlib import Path
from typing import Any
from econflow.ingestion import DatasetMetadata, DataValidationReport

class AbstractConnector(abc.ABC):
    """
    Abstract base class for all EconFlow data-source connectors.

    Subclass this, implement the five abstract methods, and decorate
    the class with ``@register_connector(connector_id)``.

    Class attributes
    ----------------
    _CITATION : str
        Human-readable citation for this data source, used by
        ``citation()`` and written to ``DatasetManifest``.
        Required if the data source has a citable reference.

    _VERSION : str
        Version string for this connector's implementation.
        Defaults to ``"unknown"``.

    Parameters
    ----------
    params : dict
        Connector configuration. Common keys vary by connector.
        Credentials (API keys, tokens) must be passed via params
        or environment variables — never hardcoded.

    cache_dir : str or Path, optional
        Directory for the local cache. Defaults to
        ``~/.econflow/cache``.
    """

    _CITATION: str = ""
    _VERSION: str = "unknown"

    def __init__(
        self,
        params: dict[str, Any] | None = None,
        cache_dir: str | Path | None = None,
    ) -> None: ...

    # ------------------------------------------------------------------
    # Abstract methods — must be implemented
    # ------------------------------------------------------------------

    @abc.abstractmethod
    def connect(self) -> None:
        """
        Verify that the data source is reachable and credentials are valid.

        This method performs a lightweight liveness check: a HEAD request,
        a metadata ping, or a credential validation call. It does not
        download any data.

        Raises
        ------
        ConnectorError
            If the source is unreachable, credentials are missing or
            invalid, or any required precondition is not met.

        Returns
        -------
        None

        Notes
        -----
        ``connect()`` must handle the case where ``params`` contains no
        credentials gracefully — raise ``ConnectorError`` with a message
        explaining which environment variable or parameter to set.

        ``connect()`` must be idempotent. Calling it multiple times must
        produce the same outcome as calling it once.
        """

    @abc.abstractmethod
    def download(self, *, force: bool = False) -> Path:
        """
        Acquire the dataset and return the path to the local CSV file.

        If ``force=False`` and ``self.cache_key()`` is already in the
        cache, this method must return the cached path without making
        any network request. This is the mechanism for offline operation.

        If ``force=True`` or the cache is empty, download the data,
        convert it to CSV (see Notes), write it to the cache via
        ``self._cache``, and return the path.

        Parameters
        ----------
        force : bool
            If True, bypass the cache and re-download unconditionally.

        Returns
        -------
        Path
            Absolute path to the CSV file in the local cache. The file
            must exist and be readable at the returned path.

        Raises
        ------
        ConnectorError
            On network failure, malformed response, or any condition that
            prevents producing a valid CSV file.

        Notes
        -----
        **Output format.** The connector must write a CSV file with:
        - A header row with column names.
        - At minimum: one entity identifier column and one time column,
          plus the data columns the connector is designed to provide.
        - UTF-8 encoding.
        - Unix line endings (``\n``).
        - No BOM.

        Column names for the entity and time columns must match the
        ``entity_col`` and ``time_col`` parameters passed to the
        constructor. If not passed, default to ``"entity"`` and
        ``"time"``.

        The connector must not write directly to the returned path.
        Use ``self._cache.store(key, tmp_path, metadata)`` to write
        to the cache atomically.
        """

    @abc.abstractmethod
    def validate(self, path: Path) -> DataValidationReport:
        """
        Run structural validation on the downloaded CSV file.

        Called automatically by ``fetch()`` after ``download()``.

        Parameters
        ----------
        path : Path
            Path to the CSV file to validate. Guaranteed to exist.

        Returns
        -------
        DataValidationReport
            Structured validation output. Do not raise on validation
            failures — record them as issues in the report.

        Notes
        -----
        Use ``DataValidator`` for standard checks (duplicate rows,
        missing identifiers, missing time periods). Add connector-
        specific checks by appending ``ValidationIssue`` objects to
        ``report.issues``.

        Example:

            from econflow.ingestion import DataValidator, DataValidationConfig
            config = DataValidationConfig(
                entity_col=self.params.get("entity_col", "entity"),
                time_col=self.params.get("time_col", "time"),
            )
            validator = DataValidator(config)
            return validator.validate(path)
        """

    @abc.abstractmethod
    def metadata(self) -> DatasetMetadata:
        """
        Return a metadata record describing the downloaded dataset.

        Must be called after ``download()``. May re-read the cached CSV
        to compute row and column counts.

        Returns
        -------
        DatasetMetadata
            Fields:

            ``connector_id`` (str)
                The registered connector ID.

            ``source`` (str)
                Human-readable source name (e.g., ``"World Bank API v2"``).

            ``download_date`` (str)
                ISO-8601 UTC timestamp of the download.

            ``url`` (str)
                URL from which the data was fetched, or ``""`` if not
                applicable.

            ``version`` (str)
                Data version string, or ``"unknown"``.

            ``citation`` (str)
                The citation for this data source.

            ``row_count`` (int)
                Number of data rows (excluding header).

            ``col_count`` (int)
                Number of columns.

            ``columns`` (list[str])
                Column names.

            ``params`` (dict)
                The parameters used for this download (must not include
                credentials — see §3.3 on security).
        """

    @abc.abstractmethod
    def cache_key(self) -> str:
        """
        Return a stable, deterministic string identifying this dataset.

        The cache key is the SHA-256 hex digest of a JSON payload
        constructed from the connector ID and all parameters that affect
        the downloaded data. Parameters that do not affect the data
        (credentials, output formatting) must be excluded.

        Returns
        -------
        str
            A 64-character hex string.

        Notes
        -----
        **Security requirement.** API keys, tokens, and passwords must
        not be included in the cache key payload. The same query with
        different API keys must map to the same cache key.

        **Stability requirement.** The key must be identical for the
        same connector and the same parameters on any machine, at any
        time, across all v1.x versions of EconFlow. A change to the
        cache key algorithm invalidates all existing user caches and
        constitutes a breaking change requiring a major version bump.

        Use ``self._make_cache_key(extra)`` to produce a consistent
        key from a dict of parameters (see §3.5).
        """

    # ------------------------------------------------------------------
    # Concrete methods — may be overridden
    # ------------------------------------------------------------------

    def citation(self) -> str:
        """
        Return the human-readable citation for this data source.

        Default implementation returns ``self._CITATION``.
        Override if the citation is not a static string.
        """
        ...

    def version(self) -> str:
        """
        Return the version string for this data source.

        Default implementation returns ``self._VERSION``.
        Override if the version can be detected dynamically.
        """
        ...

    def fetch(
        self, *, force: bool = False
    ) -> tuple[Path, DatasetMetadata]:
        """
        High-level convenience: connect → download → validate → metadata.

        Returns ``(path, metadata)``. Override only if the default
        sequence does not fit your connector's requirements.
        """
        ...

    # ------------------------------------------------------------------
    # Protected helper — use this to build cache keys
    # ------------------------------------------------------------------

    def _make_cache_key(self, extra: dict[str, Any] | None = None) -> str:
        """
        Produce a cache key from the connector ID and ``extra`` dict.

        Exclude credentials from ``extra``. The key is a SHA-256 hex
        digest of the JSON-serialized ``{"connector_id": ..., **extra}``
        payload, with keys sorted for determinism.

        Parameters
        ----------
        extra : dict, optional
            Parameters that affect the downloaded data. Do not include
            API keys, tokens, or passwords.

        Returns
        -------
        str
            64-character hex string.
        """
        ...
```

### 3.3 Security requirements for connectors

These requirements are non-negotiable. A connector that violates them will be
rejected by the TSC.

1. **No credentials in the cache key.** The `cache_key()` payload must not include
   API keys, passwords, or tokens.

2. **No credentials in metadata.** `DatasetMetadata.params` must not include API keys,
   passwords, or tokens.

3. **No credentials in provenance records.** `ManifestEntry.params` must not include
   credentials.

4. **Credentials via environment variables.** Connectors that require credentials
   must read them from environment variables as the preferred mechanism, with `params`
   as an alternative. The environment variable name must be documented in the class
   docstring.

5. **No credentials in logs.** Connectors must not log credential values. Log only
   the presence or absence of a credential (e.g., `"FRED_API_KEY: present"`).

### 3.4 Complete working example

```python
"""
econflow_imf_weo.py

IMF World Economic Outlook connector for EconFlow.

Environment variables:
    (none required — IMF WEO data is publicly accessible)

Usage:
    econflow fetch --connector imf_weo \\
        --param indicators=NGDP_RPCH,LUR \\
        --param year_start=2000 \\
        --param year_end=2023
"""

from __future__ import annotations

import csv
import io
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

from econflow.ingestion import (
    AbstractConnector,
    ConnectorError,
    DataValidator,
    DataValidationConfig,
    DataValidationReport,
    DatasetMetadata,
    register_connector,
)

_CITATION = (
    "International Monetary Fund (2024). World Economic Outlook Database "
    "(April 2024 edition). Washington, D.C.: IMF. "
    "https://www.imf.org/en/Publications/WEO"
)

_WEO_BASE = "https://www.imf.org/external/datamapper/api/v1"


@register_connector(
    "imf_weo",
    label="IMF World Economic Outlook",
    notes="Requires indicators list. See https://www.imf.org/external/datamapper/",
)
class IMFWEOConnector(AbstractConnector):
    """
    Downloads time-series data from the IMF World Economic Outlook API.

    Parameters
    ----------
    indicators : list[str]
        WEO indicator codes, e.g. ``["NGDP_RPCH", "LUR"]``.

    year_start : int, optional
        First year (inclusive). Default: 1980.

    year_end : int, optional
        Last year (inclusive). Default: current year.

    entity_col : str, optional
        Name of the entity (country) column. Default: ``"entity"``.

    time_col : str, optional
        Name of the time (year) column. Default: ``"time"``.
    """

    _CITATION = _CITATION
    _VERSION = "datamapper-v1"

    def connect(self) -> None:
        indicators = self.params.get("indicators", [])
        if not indicators:
            raise ConnectorError(
                "imf_weo",
                "Parameter 'indicators' is required and must be a non-empty list. "
                "Example: indicators=['NGDP_RPCH', 'LUR']",
            )
        # Ping the indicators endpoint to confirm API is reachable
        url = f"{_WEO_BASE}/indicators"
        try:
            resp = requests.get(url, timeout=10)
        except requests.RequestException as exc:
            raise ConnectorError(
                "imf_weo",
                f"Cannot reach IMF DataMapper API ({url}): {exc}",
            ) from exc
        if resp.status_code != 200:
            raise ConnectorError(
                "imf_weo",
                f"IMF DataMapper API returned HTTP {resp.status_code}.",
            )

    def download(self, *, force: bool = False) -> Path:
        key = self.cache_key()
        if not force and self._cache.is_cached(key):
            path, _ = self._cache.retrieve(key)
            return path

        indicators = self.params.get("indicators", [])
        year_start = self.params.get("year_start", 1980)
        year_end = self.params.get("year_end", datetime.now().year)
        entity_col = self.params.get("entity_col", "entity")
        time_col = self.params.get("time_col", "time")

        rows: list[dict] = []
        for indicator in indicators:
            url = f"{_WEO_BASE}/{indicator}"
            try:
                resp = requests.get(url, timeout=30)
                resp.raise_for_status()
            except requests.RequestException as exc:
                raise ConnectorError(
                    "imf_weo",
                    f"Failed to fetch indicator '{indicator}': {exc}",
                ) from exc

            payload = resp.json()
            values = payload.get("values", {}).get(indicator, {})
            for country_code, year_map in values.items():
                for year_str, value in year_map.items():
                    year = int(year_str)
                    if year_start <= year <= year_end:
                        rows.append({
                            entity_col: country_code,
                            time_col: year,
                            "indicator": indicator,
                            "value": value,
                        })

        if not rows:
            raise ConnectorError(
                "imf_weo",
                f"No data returned for indicators {indicators!r} "
                f"between {year_start} and {year_end}.",
            )

        # Write to a temporary file then store in cache
        import tempfile, os
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, newline=""
        ) as tmp:
            tmp_path = Path(tmp.name)
            fieldnames = [entity_col, time_col, "indicator", "value"]
            writer = csv.DictWriter(tmp, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

        try:
            meta = DatasetMetadata(
                connector_id="imf_weo",
                source="IMF World Economic Outlook DataMapper API v1",
                download_date=datetime.now(timezone.utc).isoformat(),
                url=_WEO_BASE,
                version=self._VERSION,
                citation=self._CITATION,
                row_count=len(rows),
                col_count=4,
                columns=fieldnames,
                params={
                    "indicators": indicators,
                    "year_start": year_start,
                    "year_end": year_end,
                },
            )
            path = self._cache.store(key, tmp_path, meta)
        finally:
            if tmp_path.exists():
                os.unlink(tmp_path)

        return path

    def validate(self, path: Path) -> DataValidationReport:
        config = DataValidationConfig(
            entity_col=self.params.get("entity_col", "entity"),
            time_col=self.params.get("time_col", "time"),
            check_duplicates=True,
            check_missing_identifiers=True,
        )
        return DataValidator(config).validate(path)

    def metadata(self) -> DatasetMetadata:
        key = self.cache_key()
        _, meta = self._cache.retrieve(key)
        return meta

    def cache_key(self) -> str:
        indicators = sorted(self.params.get("indicators", []))
        return self._make_cache_key({
            "indicators": indicators,
            "year_start": self.params.get("year_start", 1980),
            "year_end": self.params.get("year_end", None),
        })
        # Note: no credentials included — IMF WEO requires none.
```

### 3.5 Testing a connector plugin

```python
# tests/test_imf_weo.py
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import econflow_imf_weo  # noqa: F401 — triggers registration

from econflow.ingestion import get_connector, DataValidationReport


MOCK_PAYLOAD = {
    "values": {
        "NGDP_RPCH": {
            "USA": {"2020": -3.4, "2021": 5.7},
            "GBR": {"2020": -9.3, "2021": 7.5},
        }
    }
}


@pytest.fixture
def connector(tmp_path):
    cls = get_connector("imf_weo")
    return cls(
        params={
            "indicators": ["NGDP_RPCH"],
            "year_start": 2020,
            "year_end": 2021,
        },
        cache_dir=tmp_path,
    )


def test_registration():
    from econflow.ingestion import list_connectors
    ids = [c["id"] for c in list_connectors()]
    assert "imf_weo" in ids


def test_cache_key_excludes_no_credentials(connector):
    """Cache key must be a 64-character hex string."""
    key = connector.cache_key()
    assert isinstance(key, str)
    assert len(key) == 64


def test_cache_key_is_stable(connector, tmp_path):
    """Same params on different instances must produce the same key."""
    cls = get_connector("imf_weo")
    connector2 = cls(
        params={"indicators": ["NGDP_RPCH"], "year_start": 2020, "year_end": 2021},
        cache_dir=tmp_path,
    )
    assert connector.cache_key() == connector2.cache_key()


@patch("requests.get")
def test_download_produces_csv(mock_get, connector, tmp_path):
    """download() must produce a readable CSV at the returned path."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = MOCK_PAYLOAD
    mock_resp.raise_for_status = MagicMock()
    mock_get.return_value = mock_resp

    path = connector.download()
    assert path.exists()
    assert path.suffix == ".csv"

    import csv
    with open(path, newline="") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 4  # 2 countries × 2 years
    assert "entity" in rows[0]
    assert "time" in rows[0]


@patch("requests.get")
def test_validate_returns_report(mock_get, connector, tmp_path):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = MOCK_PAYLOAD
    mock_resp.raise_for_status = MagicMock()
    mock_get.return_value = mock_resp

    path = connector.download()
    report = connector.validate(path)
    assert isinstance(report, DataValidationReport)


def test_connect_raises_without_indicators(tmp_path):
    """connect() must raise ConnectorError if indicators is empty."""
    from econflow.ingestion import ConnectorError
    cls = get_connector("imf_weo")
    conn = cls(params={}, cache_dir=tmp_path)
    with pytest.raises(ConnectorError):
        conn.connect()
```

---

## 4. Diagnostic Plugins

Diagnostic plugins add post-estimation statistical tests. Once registered, a
diagnostic can be run by `econflow.diagnostics.get_diagnostic(id).run(result)`.
The pipeline runs all registered diagnostics that declare support for the estimator
used.

### 4.1 Imports

```python
from econflow.diagnostics import (
    BaseDiagnostic,
    DiagnosticError,
    register_diagnostic,
    get_diagnostic,
    list_diagnostics,
)
from econflow.estimation import DiagnosticResult, EstimationResult
```

### 4.2 Contract: `BaseDiagnostic`

```python
import abc
from econflow.estimation import DiagnosticResult, EstimationResult

class BaseDiagnostic(abc.ABC):
    """
    Abstract base class for all EconFlow post-estimation diagnostics.

    Class attributes
    ----------------
    diagnostic_id : str
        Matches the registered ID. Set automatically by the decorator.

    name : str
        Human-readable name, e.g. ``"Hausman Specification Test"``.

    description : str
        One-sentence description of what the test checks.

    supported_estimators : list[str] | None
        List of estimator IDs this diagnostic supports, or ``None``
        to support all estimators. Override ``supports()`` for complex
        logic.
    """

    diagnostic_id: str = ""
    name: str = ""
    description: str = ""
    supported_estimators: list[str] | None = None

    @abc.abstractmethod
    def run(
        self,
        result: EstimationResult,
        data: "pd.DataFrame | None" = None,
    ) -> DiagnosticResult:
        """
        Run the diagnostic and return a structured result.

        Parameters
        ----------
        result : EstimationResult
            The estimation result to diagnose.

        data : pd.DataFrame, optional
            The original panel dataset. Required by some diagnostics
            (e.g., those that re-estimate auxiliary regressions).
            Optional for diagnostics that work from the result alone.

        Returns
        -------
        DiagnosticResult
            Fields:

            ``check`` (str)
                Name of the test.

            ``statistic`` (float or None)
                Test statistic value.

            ``pvalue`` (float or None)
                p-value or None if not applicable.

            ``conclusion`` (str)
                Human-readable conclusion, e.g.
                ``"Reject H0: evidence of endogeneity (p=0.012)"``.

            ``level`` (str)
                ``"info"``, ``"warn"``, or ``"error"``.

            ``extra`` (dict)
                Additional output (degrees of freedom, critical values, etc.).

        Notes
        -----
        This method must not raise an exception under normal conditions.
        If the test cannot be computed (insufficient data, inapplicable
        estimator), return ``self._not_applicable(reason)`` rather than
        raising. Raise ``DiagnosticError`` only for programming errors
        (e.g., malformed EstimationResult).
        """

    # ------------------------------------------------------------------
    # Concrete methods
    # ------------------------------------------------------------------

    def supports(self, estimator_id: str) -> bool:
        """
        Return True if this diagnostic supports the given estimator.

        Default: returns True if ``supported_estimators`` is None,
        or if ``estimator_id`` is in ``supported_estimators``.
        Override for complex logic.
        """
        ...

    def run_with_context(
        self,
        result: EstimationResult,
        data: "pd.DataFrame | None" = None,
    ) -> DiagnosticResult:
        """
        Check ``supports()`` before calling ``run()``. Stamps
        ``estimator_id`` on the returned result. Intended for use by
        the pipeline. Do not call ``run()`` directly from the pipeline.
        """
        ...

    def _not_applicable(self, reason: str = "") -> DiagnosticResult:
        """Return a DiagnosticResult with level="info" and status="skip"."""
        ...
```

### 4.3 `DiagnosticResult` — the return contract

```python
@dataclass
class DiagnosticResult:
    check: str               # name of the diagnostic
    statistic: float | None = None
    pvalue: float | None = None
    conclusion: str = ""     # human-readable conclusion
    level: str = "info"      # "info" | "warn" | "error"
    estimator_id: str = ""   # set automatically by run_with_context()
    extra: dict = field(default_factory=dict)
```

### 4.4 Complete working example

```python
"""
econflow_spatial_correlation.py

Moran's I test for spatial autocorrelation in panel residuals.

Usage in models.yaml:
    diagnostics:
      - spatial_moran
"""

from __future__ import annotations

import numpy as np

from econflow.diagnostics import BaseDiagnostic, register_diagnostic
from econflow.estimation import DiagnosticResult, EstimationResult


@register_diagnostic(
    "spatial_moran",
    label="Moran's I Spatial Autocorrelation Test",
)
class MoransITest(BaseDiagnostic):
    """
    Tests for spatial autocorrelation in panel residuals using Moran's I.

    Requires a spatial weights matrix in ``result.extra["spatial_weights"]``.
    """

    diagnostic_id = "spatial_moran"
    name = "Moran's I Test"
    description = "Tests for spatial autocorrelation in OLS residuals."
    supported_estimators = ["ols", "driscoll_kraay"]

    def run(
        self,
        result: EstimationResult,
        data=None,
    ) -> DiagnosticResult:
        W = result.extra.get("spatial_weights")
        if W is None:
            return self._not_applicable(
                "No spatial weights matrix in result.extra['spatial_weights']. "
                "Pass W when calling the estimator."
            )

        # Reconstruct residuals from params and data — simplified
        if data is None:
            return self._not_applicable(
                "Original panel data required for Moran's I; "
                "pass data= to run_with_context()."
            )

        dependent = result.extra.get("dependent", "y")
        controls = result.extra.get("controls", [])
        y = data[dependent].values
        X = np.column_stack([np.ones(len(y))] +
                            [data[c].values for c in controls])
        e = y - X @ result.params.values

        # Moran's I statistic
        n = len(e)
        W_arr = np.array(W)
        S0 = W_arr.sum()
        e_mean = e.mean()
        numerator = (e - e_mean) @ W_arr @ (e - e_mean)
        denominator = ((e - e_mean) ** 2).sum()
        I = (n / S0) * (numerator / denominator)

        # Asymptotic z-score
        E_I = -1 / (n - 1)
        Var_I = (n**2 * (W_arr**2 + W_arr.T**2).sum() / (2 * S0**2)
                 - E_I**2)
        z = (I - E_I) / np.sqrt(max(Var_I, 1e-12))
        from scipy.stats import norm
        pvalue = float(2 * norm.sf(abs(z)))

        conclusion = (
            f"Reject H0: evidence of spatial autocorrelation (I={I:.4f}, p={pvalue:.4f})"
            if pvalue < 0.05
            else f"Fail to reject H0: no significant spatial autocorrelation "
                 f"(I={I:.4f}, p={pvalue:.4f})"
        )

        return DiagnosticResult(
            check=self.name,
            statistic=float(I),
            pvalue=pvalue,
            conclusion=conclusion,
            level="warn" if pvalue < 0.05 else "info",
            extra={"z_score": float(z), "E_I": float(E_I)},
        )
```

---

## 5. Integrity Check Plugins

Integrity check plugins add automated statistical quality gates to the certification
workflow. They run automatically during `econflow certify` and their results are
embedded in `ReproducibilityCertificate`.

### 5.1 Imports

```python
from econflow.integrity import (
    BaseIntegrityCheck,
    IntegrityCheckResult,
    register_integrity_check,
    get_integrity_check,
    list_checks,
)
from econflow.estimation import EstimationResult
```

### 5.2 Contract: `BaseIntegrityCheck`

```python
import abc
from econflow.integrity import IntegrityCheckResult
from econflow.estimation import EstimationResult

class BaseIntegrityCheck(abc.ABC):
    """
    Abstract base class for all EconFlow integrity checks.

    Integrity checks examine an EstimationResult for statistical
    anomalies consistent with selective reporting, data fabrication,
    or numerical error. They are advisory: a "fail" result does not
    halt the pipeline or prevent certification; it is recorded and
    disclosed.

    Class attributes
    ----------------
    check_id : str
        Matches the registered ID.

    name : str
        Human-readable name.

    description : str
        One-sentence description of what is checked.

    supported_estimators : list[str] | None
        As in BaseDiagnostic.
    """

    check_id: str = ""
    name: str = ""
    description: str = ""
    supported_estimators: list[str] | None = None

    @abc.abstractmethod
    def run(self, result: EstimationResult) -> IntegrityCheckResult:
        """
        Examine the result and return a structured integrity assessment.

        Parameters
        ----------
        result : EstimationResult

        Returns
        -------
        IntegrityCheckResult
            Fields:

            ``check_id`` (str)
                Matches the registered ID.

            ``status`` (str)
                One of ``"pass"``, ``"warn"``, ``"fail"``, ``"skip"``.

            ``message`` (str)
                Human-readable explanation of the finding, including:
                (a) what was checked, (b) what was found, (c) what the
                researcher should do if the status is not "pass".

            ``extra`` (dict)
                Supporting data (thresholds used, statistics computed, etc.).

        Severity contract:

        ``pass``
            The check ran and found no anomaly.

        ``warn``
            A condition merits attention but is not statistically
            implausible. Common examples: large but finite coefficients,
            p-value distribution is right-skewed but not pathologically so.

        ``fail``
            A condition is statistically implausible under normal research
            conditions. Examples: all p-values identical, all coefficients
            non-finite, sample size below the absolute minimum.

        ``skip``
            The check is not applicable to this estimator or result.
            Do not use "skip" to avoid running a difficult check.

        Notes
        -----
        This method must not raise an exception under any circumstances.
        Catch all exceptions internally and return a "skip" result with
        the exception message if necessary.

        This method must not modify ``result``.
        """

    # ------------------------------------------------------------------
    # Protected helpers
    # ------------------------------------------------------------------

    def supports(self, estimator_id: str) -> bool: ...

    def _pass(self, message: str = "", **extra) -> IntegrityCheckResult: ...
    def _warn(self, message: str, **extra) -> IntegrityCheckResult: ...
    def _fail(self, message: str, **extra) -> IntegrityCheckResult: ...
    def _not_applicable(self, reason: str = "") -> IntegrityCheckResult: ...
```

### 5.3 Complete working example

```python
"""
econflow_multiple_testing.py

Integrity check for unadjusted multiple comparisons.

Flags results where many hypotheses are tested without correction for
familywise error rate, which inflates the probability of Type I error.
"""

from __future__ import annotations

import numpy as np

from econflow.integrity import BaseIntegrityCheck, register_integrity_check
from econflow.estimation import EstimationResult


@register_integrity_check(
    "multiple_testing",
    label="Multiple Comparisons Check",
)
class MultipleTestingCheck(BaseIntegrityCheck):
    """
    Flags results with many significant p-values without Bonferroni or
    Benjamini-Hochberg correction.

    Parameters
    ----------
    alpha : float
        Nominal significance level. Default: 0.05.

    threshold_n : int
        Minimum number of tests before the check activates. Default: 5.
        Fewer than this many coefficients and the check returns "skip".
    """

    check_id = "multiple_testing"
    name = "Multiple Comparisons"
    description = (
        "Flags results with many nominally significant coefficients "
        "that may warrant familywise error correction."
    )

    def __init__(self, alpha: float = 0.05, threshold_n: int = 5) -> None:
        self.alpha = alpha
        self.threshold_n = threshold_n

    def run(self, result: EstimationResult) -> "IntegrityCheckResult":
        try:
            pvalues = result.pvalues.dropna().values
        except Exception as exc:
            return self._not_applicable(f"Could not read p-values: {exc}")

        n_tests = len(pvalues)
        if n_tests < self.threshold_n:
            return self._not_applicable(
                f"Only {n_tests} coefficients; multiple testing check "
                f"requires at least {self.threshold_n}."
            )

        n_significant = int((pvalues < self.alpha).sum())
        bonferroni_alpha = self.alpha / n_tests
        n_bonferroni = int((pvalues < bonferroni_alpha).sum())

        if n_bonferroni == n_significant:
            return self._pass(
                f"{n_significant}/{n_tests} coefficients significant at "
                f"α={self.alpha}; all survive Bonferroni correction.",
                n_tests=n_tests,
                n_significant=n_significant,
                bonferroni_alpha=bonferroni_alpha,
            )

        lost_significance = n_significant - n_bonferroni
        rate = n_significant / n_tests

        if rate > 0.8 and lost_significance > 2:
            return self._warn(
                f"{n_significant}/{n_tests} coefficients are nominally "
                f"significant at α={self.alpha}, but only {n_bonferroni} "
                f"survive Bonferroni correction (α={bonferroni_alpha:.4f}). "
                f"Consider reporting Bonferroni- or BH-adjusted p-values.",
                n_tests=n_tests,
                n_significant=n_significant,
                n_bonferroni=n_bonferroni,
                bonferroni_alpha=bonferroni_alpha,
            )

        return self._pass(
            f"{n_significant}/{n_tests} nominally significant; "
            f"{n_bonferroni} survive Bonferroni correction.",
            n_tests=n_tests,
            n_significant=n_significant,
            n_bonferroni=n_bonferroni,
        )
```

---

## 6. Renderer Plugins

Renderer plugins add new output formats to EconFlow's reporting engine. Once
registered, a renderer ID may be specified in `outputs.yaml` and used by
`PublicationBundle`.

### 6.1 Imports

```python
from econflow.outputs import (
    BaseRenderer,
    ReportTable,
    ReportFigure,
    RendererError,
    register_renderer,
    get_renderer,
    list_renderers,
)
```

### 6.2 Contract: `BaseRenderer`

```python
import abc
from pathlib import Path
from econflow.outputs import ReportTable

class BaseRenderer(abc.ABC):
    """
    Abstract base class for all EconFlow table renderers.

    Subclass this, implement ``render()``, and decorate with
    ``@register_renderer(renderer_id)``.

    The fundamental contract of a renderer is:
    - It receives a ``ReportTable`` whose cells are already-formatted
      strings. It must not reformat numbers.
    - It adds structure (tags, delimiters, markup) around those strings.
    - Two renderers of different types receiving the same ``ReportTable``
      must produce output containing the same cell values.
    """

    @abc.abstractmethod
    def render(self, table: ReportTable, **kwargs) -> str:
        """
        Render a ReportTable to a string in this renderer's format.

        Parameters
        ----------
        table : ReportTable
            The table to render. Cell values in ``table.rows`` are
            pre-formatted strings. Do not parse or reformat them.

        **kwargs
            Renderer-specific options. Must all be optional with defaults.
            Document every kwarg in the class docstring.

        Returns
        -------
        str
            The rendered table as a string. Must be non-empty if the
            table has at least one row.

        Raises
        ------
        RendererError
            On any failure that prevents producing valid output.

        Notes
        -----
        Do not write to files from this method. Use ``render_to_file()``
        for file output (the default implementation calls ``render()``).

        The output must be valid in the target format. A LaTeX renderer
        must produce compilable LaTeX. An HTML renderer must produce
        valid HTML5. A CSV renderer must produce RFC 4180-compliant CSV.
        """

    def render_to_file(
        self,
        table: ReportTable,
        path: str | Path,
        **kwargs,
    ) -> Path:
        """
        Render the table and write the result to ``path``.

        Default implementation calls ``render()`` and writes the string.
        Override if binary output or streaming is needed.

        Returns
        -------
        Path
            The path to the written file.
        """
        ...
```

### 6.3 Complete working example

```python
"""
econflow_quarto_renderer.py

Quarto-compatible markdown renderer for EconFlow.

Produces markdown tables with Quarto cross-reference labels and
tbl-cap attributes for use in .qmd documents.

Usage in outputs.yaml:
    renderers:
      - quarto_md
"""

from __future__ import annotations

from econflow.outputs import BaseRenderer, RendererError, ReportTable, register_renderer


@register_renderer("quarto_md", label="Quarto Markdown")
class QuartoMarkdownRenderer(BaseRenderer):
    """
    Renders ReportTable objects as Quarto-compatible markdown.

    Quarto-specific features:
    - Wraps table in a ::: {#tbl-<slug>} div for cross-referencing.
    - Adds a tbl-cap attribute from ``table.title``.
    - Appends ``table.notes`` as a paragraph below the table.

    Parameters
    ----------
    slug_prefix : str
        Prefix for the table label. Default: ``"tbl"``.
        The full label is ``#tbl-<table.table_type>``.
    """

    def render(self, table: ReportTable, *, slug_prefix: str = "tbl") -> str:
        if not table.columns:
            raise RendererError("quarto_md", "Table has no columns.")

        slug = f"{slug_prefix}-{table.table_type}".replace("_", "-")
        lines: list[str] = []

        # Quarto div with caption
        lines.append(f"::: {{#{slug}}}")
        lines.append("")

        # Markdown table header
        header = "| " + " | ".join(table.columns) + " |"
        separator = "| " + " | ".join("---" for _ in table.columns) + " |"
        lines.append(header)
        lines.append(separator)

        # Data rows
        for row in table.rows:
            cells = [row.cells.get(col, "") for col in table.columns]
            prefix = "**" if row.bold else ""
            suffix = "**" if row.bold else ""
            cell_str = " | ".join(f"{prefix}{c}{suffix}" for c in cells)
            lines.append(f"| {cell_str} |")

        lines.append("")

        # Caption and notes
        lines.append(f": {table.title} {{#tbl-cap}}")
        if table.notes:
            lines.append("")
            lines.append(f"*Note:* {table.notes}")

        lines.append("")
        lines.append(":::")

        return "\n".join(lines)
```

---

## 7. Figure Builder Plugins

Figure builder plugins add new chart types to EconFlow's reporting engine.
Once registered, a figure builder is available by ID in `outputs.yaml`.

### 7.1 Imports

```python
from econflow.outputs import (
    BaseFigureBuilder,
    ReportFigure,
    register_figure_builder,
    get_figure_builder,
    list_figure_builders,
)
from econflow.estimation import EstimationResult
```

### 7.2 Contract: `BaseFigureBuilder`

```python
import abc
from econflow.outputs import ReportFigure
from econflow.estimation import EstimationResult

class BaseFigureBuilder(abc.ABC):
    """
    Abstract base class for all EconFlow figure builders.

    Subclass this, implement ``build()``, and decorate with
    ``@register_figure_builder(figure_id)``.

    The figure builder produces a ``ReportFigure`` data object.
    The actual rendering to PNG, SVG, or PDF is performed by a
    separate figure renderer (not part of this contract).
    """

    @abc.abstractmethod
    def build(
        self,
        result: EstimationResult,
        **kwargs,
    ) -> ReportFigure:
        """
        Produce a figure from an estimation result.

        Parameters
        ----------
        result : EstimationResult
            The estimation result to visualize.

        **kwargs
            Figure-specific options (e.g., ``confidence_level=0.95``).

        Returns
        -------
        ReportFigure
            Fields:

            ``title`` (str)
                Figure caption.

            ``figure_type`` (str)
                Matches the registered figure ID.

            ``data`` (dict)
                All data needed to render the figure. Must be JSON-
                serializable so the figure can be re-rendered without
                re-estimation.

            ``config`` (dict)
                Rendering configuration (colors, fonts, axis labels).

            ``metadata`` (dict)
                Provenance (estimator_id, nobs, confidence level, etc.).
        """

    def supports(self, estimator_id: str) -> bool:
        """Return True if this builder supports the given estimator."""
        return True
```

### 7.3 Complete working example

```python
"""
econflow_binscatter.py

Binned scatter plot figure builder for EconFlow.

Produces a non-parametric binned scatter (binscatter) of the outcome
variable against the treatment variable, with optional regression line.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from econflow.outputs import BaseFigureBuilder, ReportFigure, register_figure_builder
from econflow.estimation import EstimationResult


@register_figure_builder("binscatter", label="Binned Scatter Plot")
class BinscatterBuilder(BaseFigureBuilder):
    """
    Produces a binned scatter plot of outcome vs. treatment variable.

    Parameters
    ----------
    n_bins : int
        Number of equal-frequency bins. Default: 20.

    add_linear_fit : bool
        Whether to overlay an OLS regression line. Default: True.

    confidence_level : float
        Confidence level for the regression CI band. Default: 0.95.
    """

    def build(
        self,
        result: EstimationResult,
        *,
        n_bins: int = 20,
        add_linear_fit: bool = True,
        confidence_level: float = 0.95,
        x_label: str = "Treatment",
        y_label: str = "Outcome",
    ) -> ReportFigure:
        # Extract x and y from result.extra (set by the estimator)
        x = result.extra.get("treatment_values")
        y = result.extra.get("outcome_values")

        if x is None or y is None:
            return ReportFigure(
                title="Binned Scatter (data unavailable)",
                figure_type="binscatter",
                data={},
                metadata={"error": "treatment_values or outcome_values not in result.extra"},
            )

        x = np.asarray(x, dtype=float)
        y = np.asarray(y, dtype=float)
        mask = np.isfinite(x) & np.isfinite(y)
        x, y = x[mask], y[mask]

        # Bin by quantiles of x
        bins = pd.qcut(x, q=n_bins, duplicates="drop")
        bin_x = [x[bins == b].mean() for b in bins.cat.categories]
        bin_y = [y[bins == b].mean() for b in bins.cat.categories]

        # Optional linear fit
        fit_data = {}
        if add_linear_fit:
            coeffs = np.polyfit(x, y, 1)
            x_range = np.linspace(x.min(), x.max(), 100)
            y_fit = np.polyval(coeffs, x_range)
            fit_data = {
                "x_fit": x_range.tolist(),
                "y_fit": y_fit.tolist(),
                "slope": float(coeffs[0]),
                "intercept": float(coeffs[1]),
            }

        return ReportFigure(
            title=f"Binned Scatter: {y_label} vs. {x_label}",
            figure_type="binscatter",
            data={
                "bin_x": bin_x,
                "bin_y": bin_y,
                "n_bins": len(bin_x),
                **fit_data,
            },
            config={
                "x_label": x_label,
                "y_label": y_label,
                "confidence_level": confidence_level,
            },
            metadata={
                "estimator_id": result.estimator_id,
                "nobs": result.nobs,
                "n_bins_requested": n_bins,
            },
        )
```

---

## 8. Configuration Extensions

Configuration extensions allow plugins to add validated configuration sections to
EconFlow's project configuration files. A registered extension adds a named key to
`config.yaml` that is validated by Pydantic alongside the core configuration.

### 8.1 Imports

```python
from econflow.core import (
    BaseConfigExtension,
    register_config_extension,
    get_config_extension,
    list_config_extensions,
)
```

### 8.2 Contract: `BaseConfigExtension`

```python
import abc
from pydantic import BaseModel

class BaseConfigExtension(abc.ABC):
    """
    Abstract base class for configuration extensions.

    A configuration extension adds a validated Pydantic model for a
    named section of config.yaml. When the pipeline calls
    ``load_config()``, it validates each registered extension's section
    against the extension's schema.

    Class attributes
    ----------------
    extension_id : str
        The key in config.yaml under which this extension's configuration
        lives. Example: if ``extension_id = "spatial"``, the extension
        expects a ``spatial:`` key in config.yaml.

    schema : type[BaseModel]
        The Pydantic model that validates this extension's section.
    """

    extension_id: str = ""
    schema: type[BaseModel] | None = None

    @abc.abstractmethod
    def get_schema(self) -> type[BaseModel]:
        """
        Return the Pydantic model for this extension's config section.

        The model must have defaults for all optional fields.
        It must not define fields that conflict with EconFlow core fields.
        """

    def on_load(self, config: BaseModel) -> None:
        """
        Called after config.yaml is validated.

        Use to perform cross-field validation or to initialize resources
        that depend on configuration values.

        Parameters
        ----------
        config : BaseModel
            The validated extension configuration object.
        """
```

### 8.3 Complete working example

```python
"""
econflow_spatial_config.py

Spatial analysis configuration extension for EconFlow.

Adds a 'spatial' section to config.yaml:

    spatial:
      weights_file: data/weights/contig.gal
      weights_type: queen
      row_normalize: true
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from econflow.core import BaseConfigExtension, register_config_extension


class SpatialConfig(BaseModel):
    """Spatial weights configuration."""

    weights_file: Path = Field(
        ...,
        description="Path to spatial weights file (.gal, .gwt, or .csv).",
    )
    weights_type: Literal["queen", "rook", "knn", "distance"] = Field(
        "queen",
        description="Type of spatial weights matrix.",
    )
    row_normalize: bool = Field(
        True,
        description="Row-normalize the weights matrix.",
    )
    k_neighbors: int = Field(
        5,
        description="Number of neighbors (only used if weights_type='knn').",
        ge=1,
    )

    @field_validator("weights_file")
    @classmethod
    def weights_file_must_exist(cls, v: Path) -> Path:
        if not v.exists():
            raise ValueError(
                f"Spatial weights file not found: {v}. "
                "Provide an absolute path or a path relative to the project root."
            )
        return v


@register_config_extension("spatial")
class SpatialConfigExtension(BaseConfigExtension):
    """
    Adds spatial weights configuration to config.yaml.

    Example config.yaml section:

        spatial:
          weights_file: data/weights/contig.gal
          weights_type: queen
          row_normalize: true
    """

    extension_id = "spatial"
    schema = SpatialConfig

    def get_schema(self) -> type[SpatialConfig]:
        return SpatialConfig

    def on_load(self, config: SpatialConfig) -> None:
        # Warn if knn type is requested but k is at the default
        if config.weights_type == "knn" and config.k_neighbors == 5:
            import warnings
            warnings.warn(
                "Spatial weights type is 'knn' with default k=5. "
                "Consider specifying k_neighbors explicitly.",
                stacklevel=3,
            )
```

---

## 9. Developer Guide

### 9.1 Environment setup

```bash
# Create a virtual environment for plugin development
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# Install EconFlow as a dependency
pip install "econflow>=1.0,<2.0"

# Install development tools
pip install pytest pytest-cov ruff mypy
```

### 9.2 Plugin package structure

```
my_econflow_plugin/
├── pyproject.toml
├── README.md
├── src/
│   └── my_econflow_plugin/
│       ├── __init__.py          # imports the plugin module to trigger registration
│       └── my_estimator.py      # plugin implementation
└── tests/
    └── test_my_estimator.py
```

Minimal `pyproject.toml`:

```toml
[project]
name = "econflow-my-estimator"
version = "0.1.0"
description = "My custom estimator plugin for EconFlow"
requires-python = ">=3.10"
dependencies = ["econflow>=1.0,<2.0"]

[project.entry-points."econflow.plugins"]
my_estimator = "my_econflow_plugin.my_estimator"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

The entry point line `my_estimator = "my_econflow_plugin.my_estimator"` causes
EconFlow to import `my_econflow_plugin.my_estimator` at startup, triggering the
`@register_*()` decorator and making the plugin available without explicit imports.

### 9.3 Local plugin (no package)

For a plugin you want to use in a single project without creating a package:

```python
# scripts/my_estimator.py
from econflow.estimation import BaseEstimator, register_estimator
...

# pipeline script or conftest.py
import scripts.my_estimator  # triggers registration
```

Or, add to `config/config.yaml`:

```yaml
plugins:
  - scripts.my_estimator
```

EconFlow will import the listed modules before running the pipeline.

### 9.4 Type annotations

All plugin method signatures must use the exact type annotations specified in this
document. EconFlow's CI validates plugin conformance using `mypy --strict`. Your
plugin should pass:

```bash
mypy --strict src/my_econflow_plugin/
```

### 9.5 Linting

EconFlow plugins are expected to pass `ruff check` with at minimum rule sets
`E`, `F`, `I`:

```bash
ruff check src/ tests/
```

### 9.6 Required tests

Every plugin must include tests for:

| Test | Required for |
|---|---|
| Registration appears in the registry after import | All plugin types |
| Primary method returns the correct result type | All plugin types |
| Primary method returns a result with valid required fields | All plugin types |
| Error conditions raise the correct exception type | All plugin types |
| Cache key is a 64-character hex string (connectors) | Connectors |
| Cache key is identical for same params on two instances (connectors) | Connectors |
| Credentials are absent from cache key payload (connectors) | Connectors |
| `validate()` raises before `fit()` on invalid input (estimators) | Estimators |
| `run()` does not raise on valid input (estimators) | Estimators |
| `render()` returns a non-empty string for a one-row table (renderers) | Renderers |
| `run()` returns `skip` on inapplicable result (diagnostics, integrity) | Diagnostics, Integrity |

### 9.7 Continuous integration template

```yaml
# .github/workflows/plugin-ci.yml
name: Plugin CI
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.10", "3.11", "3.12", "3.13"]

    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
      - run: pip install "econflow>=1.0,<2.0" pytest ruff mypy
      - run: pip install -e .
      - run: ruff check src/ tests/
      - run: mypy --strict src/
      - run: pytest --tb=short -q
```

---

## 10. Validation Rules

A plugin that violates any of the following rules is non-conformant and will be
rejected by the EconFlow registry. Violations that are detectable at import time
raise `RegistryError` immediately. Others are caught at runtime.

### 10.1 Universal rules (all plugin types)

| Rule | What happens on violation |
|---|---|
| Must subclass the correct base class | `RegistryError` at import |
| ID must contain only `[a-z0-9_]` | `RegistryError` at import |
| ID must not start with `_` or a digit | `RegistryError` at import |
| ID must be unique within the registry | `RegistryError` at import |
| All abstract methods must be implemented | `TypeError` at instantiation |
| Methods must return the declared type | Runtime `TypeError` |
| Methods must not mutate their input arguments | Undefined behavior |

### 10.2 Estimator-specific rules

| Rule | Enforcement |
|---|---|
| `params`, `std_err`, `pvalues` must have identical index | Runtime assertion in `run()` |
| `estimator_id` in result must match registered ID | Runtime assertion in `run()` |
| `validate()` must raise `EstimatorError`, not `ValueError` or `TypeError` | Code review |
| `diagnostics()` must not raise an exception | Code review |
| `fit()` must not call `validate()` | Code review |

### 10.3 Connector-specific rules

| Rule | Enforcement |
|---|---|
| `download()` must not modify a cached file | Runtime hash check on next retrieve |
| `cache_key()` must not include credentials | Security review |
| `cache_key()` must return a 64-character hex string | Runtime assertion |
| `download()` must return a path to a file that exists | Runtime assertion |
| Output file must be UTF-8 CSV with a header row | Runtime assertion in `validate()` |
| `metadata().params` must not include credentials | Security review |

### 10.4 Diagnostic and integrity check rules

| Rule | Enforcement |
|---|---|
| `run()` must not raise an exception | Code review; CI must test error paths |
| `run()` must not modify `result` | Code review |
| Status must be one of `pass`, `warn`, `fail`, `skip` | Runtime assertion |
| `skip` must not be used to avoid running a check | Code review |

### 10.5 Renderer rules

| Rule | Enforcement |
|---|---|
| `render()` must not write to files | Code review |
| `render()` must not reformat cell values | Code review |
| Output must be valid in the declared format | Code review + format validation test |
| `render()` must return a non-empty string for non-empty tables | Runtime assertion |

---

## 11. Version Compatibility Policy

### 11.1 EconFlow version pinning

All plugins should pin to a minor-version range:

```toml
dependencies = ["econflow>=1.0,<2.0"]
```

This is correct because:
- EconFlow follows Semantic Versioning 2.0.0.
- Plugin interfaces are frozen within all v1.x releases (see §13).
- Breaking changes to plugin interfaces only occur in major version bumps
  (1.x → 2.0).
- New plugin types, new optional methods, and new optional parameters may be
  added in minor releases without breaking existing plugins.

Do not pin to a patch version (`econflow==1.0.3`). Patch releases fix bugs;
pinning prevents researchers from receiving security and correctness fixes.

Do not pin across a major version (`econflow>=1.0,<3.0`). Major versions may
change plugin interfaces.

### 11.2 EconFlow's compatibility commitment to plugins

EconFlow commits to the following between any two v1.x releases:

**Will not change without deprecation:**
- The name of any abstract method on any plugin base class
- The signature (parameter names, types, defaults) of any abstract method
- The return type of any abstract method
- The name and import path of any registration decorator
- The name and import path of `get_<type>()`, `list_<type>s()` functions
- The name and import path of the base classes themselves
- The fields and types of `EstimationResult`, `DiagnosticResult`,
  `IntegrityCheckResult`, `ReportTable`, `ReportFigure`, `DatasetMetadata`,
  `DataValidationReport`

**May change in any minor release (non-breaking):**
- Adding new optional parameters with defaults to any method
- Adding new optional fields with defaults to any dataclass
- Adding new concrete (non-abstract) methods to any base class
- Adding new plugin types
- Improving error messages

**May change in any patch release (bug fixes):**
- Behavior that is documented as incorrect
- Security vulnerabilities
- Performance of concrete methods

### 11.3 Plugin version policy

Plugin authors are responsible for maintaining compatibility with the EconFlow
version range they declare. When EconFlow releases a new minor version:

1. EconFlow publishes a `CHANGELOG_API.md` entry listing all API surface changes.
2. Plugins that use only the stable interfaces described in this document require
   no changes.
3. Plugins that use internal (`_private`) names may require updates.

When EconFlow releases a new major version:
1. A migration guide is published at least 90 days before the major release.
2. Interface changes that affect plugin authors are listed with before/after examples.
3. A compatibility shim is provided where feasible, lasting at least one major version.

### 11.4 Deprecation lifecycle for plugin interfaces

If a method or field must change for correctness:

1. **Minor release N:** The old form is retained. It emits `DeprecationWarning` when
   accessed. The new form is introduced alongside.
2. **Minor release N+2 or later:** The old form is removed. The CHANGELOG entry
   references the deprecation announcement.

Plugin authors have at least two minor releases to update. The `DeprecationWarning`
includes the target removal version.

---

## 12. Plugin Lifecycle

### 12.1 Registration

Plugins register themselves at import time via the `@register_*()` decorator.
Registration is idempotent within a Python process: importing the same module
twice does not register the plugin twice (Python's import system caches modules).

The registration order within a Python process is determined by the order of
imports. Built-in plugins are registered first (by `econflow.*.__init__.py`
imports). Third-party plugins registered via entry points are registered
after all built-ins. Local plugins registered by explicit import are registered
last.

Registration raises `RegistryError` immediately if an ID conflict is detected.
This is intentional: ID conflicts are programming errors and must not be silent.

### 12.2 Discovery

EconFlow discovers plugins in the following order:

1. **Built-in plugins** — imported by `econflow.*.__init__.py` files. Always available.
2. **Entry point plugins** — packages declaring an `econflow.plugins` entry point.
   Discovered and imported by EconFlow at startup.
3. **Explicitly imported plugins** — modules imported by the researcher's pipeline
   code or `config.yaml` `plugins:` list. Registered when the import executes.

### 12.3 Runtime

During a pipeline run, plugins are retrieved from the registry by their IDs as
declared in `models.yaml`, `outputs.yaml`, or `config.yaml`. The registry is
read-only during a run; no registration or unregistration occurs.

The `unregister_*()` functions exist for use in test fixtures only. They must
not be called during a pipeline run.

### 12.4 Unregistration (tests only)

```python
# In a pytest fixture — restore registry state after each test
import pytest
from econflow.estimation import register_estimator, _unregister_estimator

@pytest.fixture(autouse=True)
def clean_registry():
    """Ensure test estimators do not persist between tests."""
    yield
    _unregister_estimator("test_estimator")  # underscore: internal
```

Do not use `unregister_*()` in production code.

### 12.5 Deprecating a plugin

When a plugin author wants to deprecate their plugin (e.g., because a better
alternative exists):

1. Change the `status` parameter in the registration decorator to `"deprecated"`:

```python
@register_estimator(
    "my_old_estimator",
    status="deprecated",
    notes="Deprecated in my-plugin v0.3.0. Use 'my_new_estimator' instead.",
)
class MyOldEstimator(BaseEstimator):
    def fit(self, data):
        import warnings
        warnings.warn(
            "my_old_estimator is deprecated. Use my_new_estimator instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return super().fit(data)
```

2. Keep the plugin registered and functional for at least two minor releases of
   your plugin package.

3. Remove the registration in a subsequent major release.

---

## 13. Backward Compatibility Guarantees

This section states precisely what EconFlow guarantees to plugin authors across
all v1.x releases. These guarantees are binding on the EconFlow TSC.

### 13.1 Frozen: plugin base class interfaces

The following abstract method signatures will not change in any v1.x release:

```python
# BaseEstimator
def validate(self, data: pd.DataFrame) -> None: ...
def fit(self, data: pd.DataFrame) -> EstimationResult: ...
def diagnostics(self, result: EstimationResult) -> list[DiagnosticResult]: ...

# AbstractConnector
def connect(self) -> None: ...
def download(self, *, force: bool = False) -> Path: ...
def validate(self, path: Path) -> DataValidationReport: ...
def metadata(self) -> DatasetMetadata: ...
def cache_key(self) -> str: ...

# BaseDiagnostic
def run(self, result: EstimationResult, data=None) -> DiagnosticResult: ...

# BaseIntegrityCheck
def run(self, result: EstimationResult) -> IntegrityCheckResult: ...

# BaseRenderer
def render(self, table: ReportTable, **kwargs) -> str: ...

# BaseFigureBuilder
def build(self, result: EstimationResult, **kwargs) -> ReportFigure: ...
```

### 13.2 Frozen: registration decorator signatures

```python
register_estimator(estimator_id, *, label="", status="implemented", notes="")
register_connector(connector_id, *, label="", status="implemented", notes="")
register_diagnostic(diagnostic_id, *, label="")
register_integrity_check(check_id, *, label="")
register_renderer(renderer_id, *, label="")
register_figure_builder(figure_id, *, label="")
register_config_extension(extension_id)
```

### 13.3 Frozen: result type fields

The following fields of `EstimationResult` will not be removed or renamed:

`params`, `std_err`, `pvalues`, `nobs`, `rsq`, `estimator_id`,
`f_statistic`, `f_pvalue`, `entity_col`, `time_col`, `entities`,
`time_periods`, `diagnostic_results`, `warnings`, `provenance`, `extra`.

The following fields of `DiagnosticResult` will not be removed or renamed:

`check`, `statistic`, `pvalue`, `conclusion`, `level`, `estimator_id`, `extra`.

The following fields of `IntegrityCheckResult` will not be removed or renamed:

`check_id`, `status`, `message`, `extra`.

The following fields of `ReportTable` will not be removed or renamed:

`title`, `table_type`, `columns`, `rows`, `footer`, `subtitle`, `notes`, `metadata`.

The following fields of `DatasetMetadata` will not be removed or renamed:

`connector_id`, `source`, `download_date`, `url`, `version`, `citation`,
`row_count`, `col_count`, `columns`, `params`.

### 13.4 Frozen: import paths

The following import paths are stable for all v1.x:

```python
from econflow.estimation import BaseEstimator, EstimationResult, DiagnosticResult
from econflow.estimation import register_estimator, get_estimator, list_estimators
from econflow.diagnostics import BaseDiagnostic, DiagnosticError
from econflow.diagnostics import register_diagnostic, get_diagnostic, list_diagnostics
from econflow.ingestion import AbstractConnector, ConnectorError
from econflow.ingestion import CacheManager, DatasetMetadata, DatasetManifest
from econflow.ingestion import DataValidator, DataValidationConfig, DataValidationReport
from econflow.ingestion import register_connector, get_connector, list_connectors
from econflow.outputs import BaseRenderer, ReportTable, ReportFigure, TableRow
from econflow.outputs import RendererError, PublicationBundle
from econflow.outputs import register_renderer, get_renderer, list_renderers
from econflow.integrity import BaseIntegrityCheck, IntegrityCheckResult
from econflow.integrity import ReproducibilityCertificate, detect_drift
from econflow.integrity import register_integrity_check, get_integrity_check, list_checks
from econflow import EconFlowError
```

### 13.5 Not guaranteed: internal names

Any name beginning with `_` (e.g., `_make_cache_key`, `_require_columns`,
`_REGISTRY`) is internal and may change in any release, including patch releases.
Any importable name not listed in §13.4 is internal.

### 13.6 Not guaranteed: behavior of stubs

Plugin types registered with `status="stub"` (e.g., `SystemGMM`, `WooldridgeTest`
at v0.7) may have their implementations changed in any release. Do not depend on
stub behavior.

### 13.7 Compatibility verification

Before releasing a new version of your plugin, verify compatibility:

```bash
# Install the latest EconFlow minor release
pip install "econflow>=1.0,<2.0" --upgrade

# Re-run your test suite
pytest --tb=short

# Check for deprecation warnings
python -W error::DeprecationWarning -m pytest
```

A plugin that passes its test suite with `-W error::DeprecationWarning` and zero
failures is verified compatible with the installed EconFlow version.

---

## Appendix A: Exception Reference

| Exception | Import path | When to raise |
|---|---|---|
| `EconFlowError` | `econflow` | Do not raise directly; use sub-classes. |
| `EstimatorError` | `econflow.estimation` | Estimator validation or computation failure. |
| `ConnectorError` | `econflow.ingestion` | Connection failure, download failure, invalid parameters. |
| `CacheCorruptionError` | `econflow.ingestion` | Hash mismatch on cache retrieve. |
| `DiagnosticError` | `econflow.diagnostics` | Programming error in diagnostic (malformed result). |
| `RendererError` | `econflow.outputs` | Renderer cannot produce valid output. |
| `RegistryError` | `econflow` | Duplicate plugin ID, unknown plugin ID. |
| `ConfigurationError` | `econflow` | Invalid configuration values. |

All EconFlow exceptions accept `(context: str, message: str)` as positional arguments
where `context` is the plugin ID and `message` is the human-readable error description.

---

## Appendix B: Checklist for submitting a plugin

Before publishing your plugin, confirm each of the following:

**Correctness**
- [ ] All abstract methods are implemented.
- [ ] Primary method returns the correct type with all required fields set.
- [ ] `validate()` raises the correct exception type before `fit()` on bad input.
- [ ] `diagnostics()` / `run()` does not raise on valid input.

**Security (connectors only)**
- [ ] `cache_key()` excludes all credentials.
- [ ] `metadata().params` excludes all credentials.
- [ ] Credentials are read from environment variables, not hardcoded.

**Testing**
- [ ] All required tests from §9.6 are present.
- [ ] Tests pass on Python 3.10, 3.11, 3.12, and 3.13.
- [ ] Tests pass with `-W error::DeprecationWarning`.
- [ ] Tests do not require network access by default (use mocks).

**Packaging**
- [ ] `pyproject.toml` pins `econflow>=1.0,<2.0`.
- [ ] Entry point declared under `econflow.plugins`.
- [ ] `__init__.py` imports the plugin module to trigger registration.

**Documentation**
- [ ] Class docstring describes the plugin's purpose, parameters, and examples.
- [ ] All constructor parameters are documented.
- [ ] `_CITATION` is set (connectors only).
- [ ] Environment variable names are documented (connectors that require credentials).

---

*EconFlow Technical Steering Committee — 2026-06-28*  
*This document is the authoritative contract for EconFlow plugin authors.*  
*File any discrepancies between this document and the implementation as a bug.*
