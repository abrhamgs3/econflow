"""
EconFlow — Panel Econometrics Research Platform.

A reusable, config-driven framework for reproducible panel econometric research.

Quick start
-----------
    pip install econflow
    econflow init my_study
    cd my_study
    econflow validate
    econflow run --config config/config.yaml --models config/models.yaml \
                 --outputs config/outputs.yaml

Available subpackages (v1.0)
-----------------------------
ingestion       CSV, World Bank, OECD, PWT, FRED data connectors
estimation      Panel estimators: PooledOLS, EntityFE, TwoWayFE, RE, FD, IV2SLS
diagnostics     Post-estimation tests: Hausman, Breusch-Pagan, Pesaran CD, VIF
outputs         Table, figure, and report renderers (CSV, LaTeX, Markdown, HTML, JSON)
integrity       Provenance certificates, drift detection, replication packages
replication     Blind replication, execution planning, output comparison
config          YAML configuration models, linter, and reference docs

Not yet available (planned for v1.x)
--------------------------------------
processing      Harmonisation, feature engineering, composite index, TFP (stubs)
sensitivity     SensitivityRunner, ResultsComparison (stubs)
"""

__version__ = "0.1.0"
__author__ = "Ab"
__email__ = "abrhamgs3@gmail.com"

from econflow.core.exceptions import EconFlowCoreError
from econflow.exceptions import (
    AIProdError,  # deprecated alias — kept for backward compat until v0.3.0
    DataValidationError,
    EconFlowError,
    MergeError,
    ModelSpecificationError,
    PipelineError,
)

__all__ = [
    "__version__",
    # Root exception — catches everything
    "EconFlowError",
    # Core scaffold exceptions (share EconFlowError root)
    "EconFlowCoreError",
    # Deprecated alias for EconFlowError (removed in v0.3.0)
    "AIProdError",
    # Pipeline-layer exception types
    "DataValidationError",
    "MergeError",
    "ModelSpecificationError",
    "PipelineError",
]
