"""
econflow.core.config — Pydantic-based configuration loader.

Responsibilities
----------------
* Parse and validate ``config.yaml`` files located in project directories.
* Expose a typed ``Settings`` object consumed by all other sub-systems.
* Support environment-variable overrides via Pydantic's ``model_config``.

Usage (once implemented)
-------------------------
    from econflow.core.config import load_config
    cfg = load_config("examples/ai_productivity_paper/config/config.yaml")
    print(cfg.project.name)
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Nested config models
# ---------------------------------------------------------------------------


class AuthorConfig(BaseModel):
    """A single project author."""

    name: str = Field(..., description="Author full name.")
    email: str = Field("", description="Author contact email.")


class ProjectMeta(BaseModel):
    """Top-level project identification block."""

    name: str = Field(..., description="Human-readable project name.")
    version: str = Field("0.1.0", description="Semver project version string.")
    description: str = Field("", description="Optional project description.")
    authors: list[AuthorConfig] = Field(
        default_factory=list,
        description="List of project authors.",
    )
    output_dir: Path = Field(
        Path("outputs"),
        description="Root directory for pipeline outputs.",
    )


class DataSourceConfig(BaseModel):
    """Configuration for a single external data source."""

    enabled: bool = Field(True, description="Whether this source is active.")
    base_url: str = Field("", description="Root URL of the data API or download endpoint.")
    indicators: list[str] = Field(
        default_factory=list, description="Variable codes to fetch."
    )
    extra: dict[str, Any] = Field(
        default_factory=dict, description="Source-specific options."
    )


class SampleConfig(BaseModel):
    """Temporal and cross-sectional sample bounds."""

    countries: str | list[str] = Field("all", description="ISO-3 codes or 'all'.")
    year_start: int = Field(2000, description="First year (inclusive).")
    year_end: int = Field(2022, description="Last year (inclusive).")
    min_obs_per_country: int = Field(
        0,
        description="Drop countries with fewer than this many observations. 0 = no filter.",
    )


class DataConfig(BaseModel):
    """Aggregated data configuration block."""

    sources: dict[str, DataSourceConfig] = Field(default_factory=dict)
    sample: SampleConfig = Field(default_factory=SampleConfig)
    cache_dir: Path = Field(
        Path(".cache/downloads"),
        description="Raw-data cache directory.",
    )


class VariablesConfig(BaseModel):
    """Variable definitions used across processing steps."""

    ai_proxy: list[str] = Field(
        default_factory=list, description="AI-proxy indicator codes."
    )
    ai_index_method: Literal["pca", "equal_weight"] = Field(
        "pca",
        description="Method for constructing the composite AI Proxy Index.",
    )
    outcome: str = Field("tfp_growth", description="Dependent variable name.")
    controls: list[str] = Field(
        default_factory=list, description="Control variable names."
    )
    instruments: list[str] = Field(
        default_factory=list, description="IV instrument names."
    )


class Settings(BaseModel):
    """
    Root settings object for an EconFlow project.

    Populated by :func:`load_config` from a project-level ``config.yaml``.
    """

    project: ProjectMeta
    data: DataConfig = Field(default_factory=DataConfig)
    variables: VariablesConfig = Field(default_factory=VariablesConfig)

    model_config = ConfigDict(
        env_prefix="ECONFLOW_",
        env_nested_delimiter="__",
    )


# ---------------------------------------------------------------------------
# Loader (stub — implementation TBD)
# ---------------------------------------------------------------------------


def load_config(path: str | Path) -> Settings:
    """
    Parse *path* (a YAML file) and return a validated :class:`Settings` object.

    Parameters
    ----------
    path:
        Filesystem path to the project ``config.yaml``.

    Returns
    -------
    Settings
        Fully validated settings instance.

    Raises
    ------
    econflow.core.exceptions.ConfigurationError
        If the YAML is missing required keys or contains invalid values.
    FileNotFoundError
        If *path* does not exist.
    """
    raise NotImplementedError("load_config is not yet implemented.")
