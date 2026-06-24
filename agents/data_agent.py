"""
Backward-compatibility shim.

All logic has moved to ``src/econflow/data/``.
This file re-exports everything so existing scripts keep working.
"""
from econflow.data.loaders import (
    AGGREGATE_ENTITIES,
    NON_SOVEREIGN_ENTITIES,
    drop_aggregate_entities,
    load_panel,
)
from econflow.data.validators import (
    REQUIRED_COLUMNS,
    report_has_blockers,
    save_validation_report,
    validate_data,
)
from econflow.data.cleaning import sample_selection_summary

__all__ = [
    "drop_aggregate_entities", "load_panel",
    "validate_data", "report_has_blockers", "save_validation_report",
    "sample_selection_summary",
    "AGGREGATE_ENTITIES", "NON_SOVEREIGN_ENTITIES", "REQUIRED_COLUMNS",
]
