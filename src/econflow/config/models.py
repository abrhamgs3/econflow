"""
econflow.config.models — Pydantic v2 configuration models for all EconFlow YAML files.

Architecture Stabilization Milestone 4.

This module defines fully-documented Pydantic models for every YAML option in
the three EconFlow configuration files:

* :class:`ProjectConfig` — ``config.yaml``  (project, data, sample, variables)
* :class:`ModelsConfig`  — ``models.yaml``  (list of model specifications)
* :class:`OutputsConfig` — ``outputs.yaml`` (table and figure output settings)

Every field carries:

* ``description`` — plain-English explanation of what the option does.
* ``examples``    — one or more concrete example values.
* A default where the option is optional; ``...`` (Ellipsis) where it is
  required.

These models power three downstream consumers:

1. **Validation** — :mod:`econflow.commands.validate` uses Pydantic to parse
   YAML dicts and surface structured ``ValidationError`` messages.
2. **Linting**    — :mod:`econflow.config.linter` receives typed model instances
   and runs semantic checks.
3. **Docs**       — :mod:`econflow.config.docs` introspects :meth:`model_fields`
   to auto-generate the ``CONFIG_REFERENCE.md`` table.
"""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# ===========================================================================
# config.yaml models
# ===========================================================================


class AuthorModel(BaseModel):
    """A project author entry inside ``project.authors``."""

    name: str = Field(
        ...,
        description="Author's full name.",
        examples=["Jane Smith"],
    )
    email: str = Field(
        "",
        description="Author's contact email address.  Optional.",
        examples=["jane@example.com"],
    )


class ProjectModel(BaseModel):
    """Top-level project identification block (``project:`` in config.yaml)."""

    name: str = Field(
        ...,
        description=(
            "Human-readable project name.  Used in provenance stamps, "
            "report headers, and replication package metadata."
        ),
        examples=["getting_started", "my_tfp_study"],
    )
    version: str = Field(
        "0.1.0",
        description=(
            "Semantic-version string for the project.  Bump when you "
            "materially change a specification so archived results remain "
            "traceable to the config that produced them."
        ),
        examples=["0.1.0", "1.2.3"],
    )
    description: str = Field(
        "",
        description="Free-text description of the project and its research question.",
        examples=["Firm investment and fixed effects — Grunfeld panel (1935-1954)"],
    )
    authors: list[AuthorModel] = Field(
        default_factory=list,
        description="List of project authors.  Each entry must have a ``name``.",
        examples=[[{"name": "Jane Smith", "email": "jane@example.com"}]],
    )
    output_dir: str = Field(
        "outputs",
        description=(
            "Root directory for pipeline output artefacts (tables, figures, "
            "certificates).  Relative paths are resolved from the project root."
        ),
        examples=["outputs", "results"],
    )


class DataModel(BaseModel):
    """Data source configuration (``data:`` in config.yaml)."""

    path: str = Field(
        ...,
        description=(
            "Path to the processed panel CSV.  Relative paths are resolved "
            "from config.yaml's parent directory."
        ),
        examples=["data/processed/panel.csv", "../data/grunfeld.csv"],
    )
    entity_col: str = Field(
        ...,
        description=(
            "Name of the cross-sectional identifier column in the CSV "
            "(e.g. country ISO-3 code, firm id).  Used by all panel estimators."
        ),
        examples=["country", "firm", "entity"],
    )
    time_col: str = Field(
        ...,
        description=(
            "Name of the time-period column in the CSV "
            "(e.g. calendar year, quarter).  Must be numeric or parseable."
        ),
        examples=["year", "quarter", "time"],
    )
    required_columns: list[str] = Field(
        default_factory=list,
        description=(
            "Whitelist of columns that must be present in the CSV.  "
            "``econflow validate --data`` checks each column is present. "
            "Typically includes entity_col, time_col, dependent, and all regressors."
        ),
        examples=[["country", "year", "ln_gdp", "ln_capital"]],
    )


class SampleModel(BaseModel):
    """Temporal sample bounds (``sample:`` in config.yaml)."""

    start_year: int = Field(
        1990,
        description=(
            "First calendar year included in the estimation sample (inclusive). "
            "Rows with ``time_col < start_year`` are excluded before estimation."
        ),
        examples=[1990, 2000, 2010],
    )
    end_year: int = Field(
        2020,
        description=(
            "Last calendar year included in the estimation sample (inclusive). "
            "Rows with ``time_col > end_year`` are excluded before estimation."
        ),
        examples=[2020, 2022, 2019],
    )
    min_obs_per_entity: int = Field(
        0,
        description=(
            "Drop entities (countries / firms) with fewer than this many "
            "non-missing observations.  Set to 0 to keep all entities."
        ),
        examples=[0, 5, 10],
    )

    @model_validator(mode="after")
    def _check_year_order(self) -> SampleModel:
        if self.start_year >= self.end_year:
            raise ValueError(
                f"sample.start_year ({self.start_year}) must be strictly less than "
                f"sample.end_year ({self.end_year})."
            )
        return self


class VariablesModel(BaseModel):
    """Variable definitions (``variables:`` in config.yaml)."""

    dependent: str = Field(
        ...,
        description=(
            "Name of the outcome (dependent) variable.  Must be a column in "
            "the CSV.  This variable appears on the left-hand side of every "
            "regression model."
        ),
        examples=["invest", "ln_gdp_pc", "tfp_growth"],
    )
    regressors: list[str] = Field(
        ...,
        description=(
            "List of right-hand-side variable names (excluding fixed effects "
            "and time/entity dummies, which are handled automatically).  "
            "All entries must be columns in the CSV."
        ),
        examples=[["value", "capital"], ["ln_ai_index", "ln_capital", "ln_labor"]],
    )
    instruments: list[str] = Field(
        default_factory=list,
        description=(
            "Excluded instruments for IV / 2SLS estimation.  Must be columns "
            "in the CSV.  Leave empty for non-IV models."
        ),
        examples=[[], ["distance_to_equator", "colonial_origin"]],
    )
    controls: list[str] = Field(
        default_factory=list,
        description=(
            "Additional control variables.  Included in all models but not "
            "highlighted in the main coefficient table."
        ),
        examples=[[], ["population", "trade_openness"]],
    )

    @field_validator("regressors")
    @classmethod
    def _regressors_non_empty(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError(
                "variables.regressors must contain at least one variable name."
            )
        return v


class ProjectConfig(BaseModel):
    """
    Root model for ``config.yaml``.

    Required top-level keys: ``project``, ``data``, ``variables``.
    Optional keys: ``sample``.
    """

    model_config = ConfigDict(extra="forbid")

    project: ProjectModel = Field(
        ...,
        description="Project identification metadata.",
    )
    data: DataModel = Field(
        ...,
        description="Data source path and column names.",
    )
    sample: SampleModel = Field(
        default_factory=SampleModel,
        description="Temporal and cross-sectional sample bounds.",
    )
    variables: VariablesModel = Field(
        ...,
        description="Dependent variable, regressor list, and instrument list.",
    )


# ===========================================================================
# models.yaml models
# ===========================================================================

#: Recognised estimator identifiers.  Kept in sync with the live registry.
KNOWN_ESTIMATORS: frozenset[str] = frozenset(
    {"ols", "fe", "twfe", "re", "fd", "iv", "gmm", "quantile",
     # Common aliases used in project YAML files
     "OLS", "FE", "TWFE", "RE", "FD", "IV", "GMM"}
)

#: Regex for valid model IDs (alphanumeric + underscores + hyphens).
_MODEL_ID_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_-]*$")


class ModelSpec(BaseModel):
    """
    A single regression model specification (one entry in ``models:`` list).

    Every field that maps directly to an estimator parameter is forwarded to
    :class:`~econflow.estimation.base.BaseEstimator.__init__` via the ``params``
    dict.
    """

    model_config = ConfigDict(extra="allow")   # allow estimator-specific keys

    id: str = Field(
        ...,
        description=(
            "Unique model identifier.  Used as a key in outputs.yaml, in table "
            "column headers, and in provenance stamps.  "
            "Must start with a letter and contain only letters, digits, "
            "underscores, and hyphens."
        ),
        examples=["pooled_ols", "entity_fe", "twfe_robust"],
    )
    label: str = Field(
        "",
        description=(
            "Human-readable display name for the model.  Appears in table "
            "headers and figure legends.  Defaults to the ``id`` if empty."
        ),
        examples=["Pooled OLS", "Entity FE", "Two-Way FE"],
    )
    estimator: str = Field(
        ...,
        description=(
            "Registry key of the estimator to use.  Must match a registered "
            "estimator ID (see ``econflow info`` for the full list).  "
            "Case-insensitive aliases: OLS→ols, FE→fe, TWFE→twfe, RE→re, "
            "FD→fd, IV→iv."
        ),
        examples=["OLS", "FE", "twfe", "iv"],
    )
    dependent: str = Field(
        ...,
        description=(
            "Dependent variable for this model.  Typically matches "
            "``variables.dependent`` in config.yaml, but may differ for "
            "robustness checks with alternative outcome variables."
        ),
        examples=["invest", "ln_gdp_pc"],
    )
    regressors: list[str] = Field(
        ...,
        description=(
            "List of right-hand-side variables for this model.  Should be a "
            "subset of (or equal to) ``variables.regressors`` in config.yaml."
        ),
        examples=[["value", "capital"], ["ln_ai_index", "ln_capital"]],
    )
    entity_effects: bool = Field(
        False,
        description=(
            "Include entity (within) fixed effects.  Required for FE and TWFE "
            "estimators.  Ignored by OLS."
        ),
        examples=[True, False],
    )
    time_effects: bool = Field(
        False,
        description=(
            "Include time-period fixed effects.  Set to ``true`` for TWFE. "
            "Ignored by OLS."
        ),
        examples=[True, False],
    )
    cluster: str = Field(
        "",
        description=(
            "Column to cluster standard errors by.  Typical values: "
            "'entity' (cluster by cross-sectional unit) or a column name.  "
            "Leave empty for heteroskedasticity-robust (HC) standard errors."
        ),
        examples=["entity", "country", ""],
    )
    description: str = Field(
        "",
        description="Free-text annotation for this specification.  Appears in table footnotes.",
        examples=["Baseline pooled OLS — ignores firm heterogeneity."],
    )

    @field_validator("id")
    @classmethod
    def _valid_id(cls, v: str) -> str:
        if not _MODEL_ID_RE.match(v):
            raise ValueError(
                f"Model id {v!r} is invalid.  "
                "Must start with a letter and contain only letters, digits, "
                "underscores, and hyphens (e.g. \'entity_fe\', \'model-1\')."
            )
        return v


class ModelsConfig(BaseModel):
    """Root Pydantic v2 model for ``models.yaml``.

    Validates the ordered list of regression model specifications loaded by
    :func:`~econflow.config.loader.ConfigLoader`.  At least one model is required.

    Attributes
    ----------
    models : list[ModelSpec]
        Ordered list of regression model specifications.  Each entry ``id``
        must be unique within this list.
    """

    model_config = ConfigDict(extra="forbid")

    models: list[ModelSpec] = Field(
        ...,
        min_length=1,
        description=(
            "Ordered list of regression model specifications.  Must contain at "
            "least one entry.  Each entry's ``id`` must be unique within this list."
        ),
        examples=[[
            {"id": "baseline", "estimator": "FE",
             "dependent": "y", "regressors": ["x1", "x2"]},
        ]],
    )

    @field_validator("models")
    @classmethod
    def _no_duplicate_ids(cls, specs: list[ModelSpec]) -> list[ModelSpec]:
        seen: set[str] = set()
        for spec in specs:
            if spec.id in seen:
                raise ValueError(
                    f"Duplicate model id {spec.id!r}.  "
                    "Every entry in the models list must have a unique id."
                )
            seen.add(spec.id)
        return specs


# ===========================================================================
# outputs.yaml models
# ===========================================================================


class ComparisonTableModel(BaseModel):
    """Settings for the main regression comparison table."""

    model_config = ConfigDict(extra="allow")

    filename: str = Field(
        ...,
        description=(
            "Output filename stem (without extension).  The renderer appends "
            "the appropriate extension (.csv, .tex, .md, etc.)."
        ),
        examples=["table_main_results", "table_fe_investment"],
    )
    models: list[str] = Field(
        default_factory=list,
        description=(
            "Ordered list of model IDs to include as columns.  Each ID must "
            "exist in models.yaml.  Leave empty to include all models."
        ),
        examples=[["pooled_ols", "entity_fe", "twfe"]],
    )
    stars: bool = Field(
        True,
        description=(
            "Append statistical-significance stars to coefficient estimates "
            "(*** p<0.01, ** p<0.05, * p<0.1)."
        ),
        examples=[True, False],
    )
    se_type: Literal["robust", "clustered", "classical"] = Field(
        "robust",
        description=(
            "Standard error type shown in parentheses below each coefficient.  "
            "``robust``: heteroskedasticity-robust HC SEs.  "
            "``clustered``: cluster-robust SEs (cluster column set per model).  "
            "``classical``: OLS standard errors (not recommended for panels)."
        ),
        examples=["robust", "clustered"],
    )


class TablesModel(BaseModel):
    """Table output settings (``outputs.tables:`` in outputs.yaml)."""

    model_config = ConfigDict(extra="allow")

    dir: str = Field(
        "outputs/tables",
        description="Directory (relative to project root) where table files are written.",
        examples=["outputs/tables", "results/tables"],
    )
    formats: list[str] = Field(
        default_factory=lambda: ["csv", "latex"],
        description=(
            "List of output formats to produce for every table.  "
            "Supported: ``csv``, ``latex``, ``markdown``, ``html``, ``json``."
        ),
        examples=[["csv", "latex"], ["csv", "markdown"]],
    )
    comparison_table: ComparisonTableModel = Field(
        ...,
        description="Main coefficient comparison table settings.",
    )


class FiguresModel(BaseModel):
    """Figure output settings (``outputs.figures:`` in outputs.yaml)."""

    model_config = ConfigDict(extra="allow")

    dir: str = Field(
        "outputs/figures",
        description="Directory where figure files are written.",
        examples=["outputs/figures"],
    )
    enabled: bool = Field(
        True,
        description=(
            "Master switch for figure generation.  "
            "Set to ``false`` to skip all figures (useful for fast runs)."
        ),
        examples=[True, False],
    )


class OutputsBlock(BaseModel):
    """The ``outputs:`` mapping block in ``outputs.yaml``.

    Controls where EconFlow writes tables, figures, and provenance artefacts.

    Attributes
    ----------
    base_dir : str
        Root directory for all output artefacts.  Subdirectories
        ``tables/`` and ``figures/`` are created relative to this path.
    tables : TablesModel
        Table output settings (directory, formats).
    """

    model_config = ConfigDict(extra="allow")

    base_dir: str = Field(
        ...,
        description=(
            "Root directory for all output artefacts.  Subdirectories "
            "(tables/, figures/) are created relative to this path."
        ),
        examples=["outputs", "../results"],
    )
    tables: TablesModel = Field(
        ...,
        description="Table generation settings.",
    )
    figures: FiguresModel = Field(
        default_factory=FiguresModel,
        description="Figure generation settings.",
    )


class OutputsConfig(BaseModel):
    """Root Pydantic v2 model for ``outputs.yaml``.

    Validates the outputs configuration loaded by
    :func:`~econflow.config.loader.ConfigLoader`.

    Attributes
    ----------
    outputs : OutputsBlock
        All output configuration lives under this top-level key.
    """

    model_config = ConfigDict(extra="forbid")

    outputs: OutputsBlock = Field(
        ...,
        description="All output configuration lives under this top-level key.",
    )
