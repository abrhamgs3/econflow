"""
tests/integration/test_phase5a_dual_path.py  — RETIRED

Phase 5A dual-path tests have been superseded by Phase 5C.

The legacy _run_model() path and the _USE_DISPATCHER flag were both removed
in Phase 5C.  EstimationDispatcher is now the only production execution path.

Replacement test file: tests/integration/test_phase5c_pipeline.py
"""

import pytest

pytestmark = pytest.mark.skip(
    reason=(
        "Phase 5A dual-path tests retired in Phase 5C.  "
        "The legacy _run_model() path has been removed.  "
        "See tests/integration/test_phase5c_pipeline.py instead."
    )
)
