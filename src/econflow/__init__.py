"""
EconFlow — Panel Econometrics Research Platform.

A reusable infrastructure for cross-country panel econometric research.
Any project can be run by pointing the platform at a project configuration
(``projects/<name>/config.yaml``) and calling ``econflow run <project>``.

Quick start
-----------
    pip install econflow
    econflow project init my_study
    econflow run my_study

Subpackages
-----------
core            Configuration, provenance, pipeline orchestration, registry
ingestion       Data connectors: World Bank, OECD, PWT
processing      Harmonisation, feature engineering, composite index, TFP, quality
estimation      Panel estimators: FE, GLS, IV, GMM, quantile
diagnostics     Post-estimation tests: Hausman, Sargan, Pesaran CD, AB AR
sensitivity     SensitivityRunner, ResultsComparison
visualization   Publication figures
reporting       Narrative generation
outputs         Table, figure, and report renderers
"""

__version__ = "0.1.0"
__author__ = "Ab"
__email__ = "abrhamgs3@gmail.com"

from econflow.exceptions import (
    EconFlowError,
    AIProdError,          # deprecated alias — kept for backward compat until v0.3.0
    DataValidationError,
    MergeError,
    ModelSpecificationError,
    PipelineError,
)

__all__ = [
    "__version__",
    # Canonical name
    "EconFlowError",
    # Deprecated alias (removed in v0.3.0)
    "AIProdError",
    # Concrete exception types
    "DataValidationError",
    "MergeError",
    "ModelSpecificationError",
    "PipelineError",
]
