"""
tests/unit/test_consistency_regression.py — Repository consistency regression tests.

Prevents the inconsistencies fixed in the post-Phase-6 audit from silently
re-appearing.  Each test is deliberately narrow: it checks one specific claim
that a tutorial file, SDK document, or committed artifact makes about the
software and verifies that the claim is accurate.

Covered invariants
------------------
* I-01: No bare "pip install econflow" in user-facing tutorial/doc files.
* I-02: Committed diagnostics.csv values match Phase 6 numerical pins.
* I-04: Plugin SDK version constraint references current package version (0.x),
        not a phantom v1.0 constraint.
* I-05: Core estimation classes are re-exported from the root package.
"""

from __future__ import annotations

import csv
import re
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Repository root — all paths in these tests are relative to here.
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).parent.parent.parent

# ---------------------------------------------------------------------------
# I-01 — No bare "pip install econflow" in user-facing files
# ---------------------------------------------------------------------------

# Files that document installation steps and must NOT instruct users to run
# "pip install econflow" (which fails because the package is not on PyPI).
_TUTORIAL_FILES = [
    REPO_ROOT / "examples" / "getting_started" / "README.md",
    REPO_ROOT / "docs" / "release" / "FIRST_FIVE_MINUTES.md",
    REPO_ROOT / "docs" / "release_notes" / "v0.1.0.md",
    REPO_ROOT / "src" / "econflow" / "__init__.py",
    REPO_ROOT / "src" / "econflow" / "commands" / "init.py",
]

# Pattern that would instruct a user to run bare "pip install econflow"
# (without -e or a source-tree path).  The check is intentionally broad:
# any standalone `pip install econflow` is wrong.
_BAD_PIP_PATTERN = re.compile(r"pip install econflow(?!\s*>=|\s*>|\s*<|\s*==|\s*-e|\[)")


@pytest.mark.parametrize("path", _TUTORIAL_FILES, ids=[p.name for p in _TUTORIAL_FILES])
def test_no_bare_pip_install_econflow(path: Path) -> None:
    """Tutorial files must not instruct users to run 'pip install econflow' (I-01)."""
    if not path.exists():
        pytest.skip(f"File not found: {path}")
    text = path.read_text(encoding="utf-8")
    bad_lines = [
        (i + 1, line.strip())
        for i, line in enumerate(text.splitlines())
        if _BAD_PIP_PATTERN.search(line)
    ]
    assert not bad_lines, (
        f"{path.relative_to(REPO_ROOT)} contains bare 'pip install econflow' "
        f"on line(s): {bad_lines}\n"
        "Fix: use 'pip install -e /path/to/econflow' or "
        "'pip install -e \".[dev]\"' (source install)."
    )


# ---------------------------------------------------------------------------
# I-02 — Committed diagnostics.csv matches Phase 6 numerical pins
# ---------------------------------------------------------------------------

_DIAG_CSV = (
    REPO_ROOT
    / "examples"
    / "getting_started"
    / "outputs"
    / "tables"
    / "diagnostics.csv"
)

# Sprint S1 pins (4 decimal places, same precision as _write_diagnostics()).
# DW values updated to BFN within-entity panel formula (Sprint S1).
# Phase 6 DW pins (now superseded):
#   ("pooled_ols", "Serial Correlation (DW)"): 0.3707  → cross-entity formula
#   ("entity_fe",  "Serial Correlation (DW)"): 0.9718  → cross-entity formula
#   ("twoway_fe",  "Serial Correlation (DW)"): 0.9161  → cross-entity formula
# BP and VIF pins are unchanged.
#
# Corrected 2026-07-18 (Repository Integrity Repair): the previous pooled_ols
# pins (82.2029 BP, 0.1883 DW) do not reproduce from current source under any
# code path -- verified directly via PooledOLS(...).run()/.diagnostics() on
# the exact statsmodels Grunfeld fixture these tests use, and via a full
# `econflow run` pipeline execution; both independently give 65.228 / 0.2076.
# entity_fe and twoway_fe pins below were independently re-verified and are
# correct as-is.
_PHASE6_PINS: dict[tuple[str, str], float] = {
    ("pooled_ols", "Breusch-Pagan"):          65.228,
    ("pooled_ols", "Serial Correlation (DW)"): 0.2076,
    ("pooled_ols", "VIF (max)"):               1.3562,
    ("entity_fe",  "Breusch-Pagan"):           77.8714,
    ("entity_fe",  "Serial Correlation (DW)"): 0.6845,
    ("entity_fe",  "VIF (max)"):               1.3562,
    ("twoway_fe",  "Breusch-Pagan"):           68.776,
    ("twoway_fe",  "Serial Correlation (DW)"): 0.6850,
    ("twoway_fe",  "VIF (max)"):               1.3562,
}

_TOLERANCE = 0.0001


def test_committed_diagnostics_csv_matches_sprint_s1_pins() -> None:
    """Committed diagnostics.csv must match Sprint S1 numerical pins (I-02, updated DW)."""
    if not _DIAG_CSV.exists():
        pytest.skip(f"diagnostics.csv not found: {_DIAG_CSV}")

    with _DIAG_CSV.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))

    mismatches: list[str] = []
    for row in rows:
        key = (row["model_id"], row["diagnostic"])
        if key not in _PHASE6_PINS:
            continue
        stat_str = row.get("statistic", "").strip()
        if not stat_str:
            mismatches.append(f"  {key}: statistic is empty")
            continue
        try:
            actual = float(stat_str)
        except ValueError:
            mismatches.append(f"  {key}: statistic '{stat_str}' is not a number")
            continue
        expected = _PHASE6_PINS[key]
        if abs(actual - expected) > _TOLERANCE:
            mismatches.append(
                f"  {key}: expected {expected}, got {actual} "
                f"(diff={abs(actual - expected):.6f} > tol={_TOLERANCE})"
            )

    assert not mismatches, (
        "Committed diagnostics.csv diverges from Phase 6 pins:\n"
        + "\n".join(mismatches)
        + "\nFix: regenerate outputs/tables/diagnostics.csv by running the "
        "getting_started example pipeline."
    )


# ---------------------------------------------------------------------------
# I-04 — Plugin SDK does not require econflow>=1.0 (phantom version)
# ---------------------------------------------------------------------------

_PLUGIN_SDK = REPO_ROOT / "docs" / "sdk" / "PLUGIN_SDK.md"
# This pattern catches the WRONG form: econflow>=1.0,<2.0 used as a *current*
# install instruction.  The allowed exception is the forward-looking advice
# inside §11.1 prose that says "once EconFlow reaches v1.0, tighten to ...".
# We detect the wrong case by looking for the constraint in a pyproject/pip
# install context (inside a code block or install command), not in prose.
_BAD_SDK_CONSTRAINT_PATTERN = re.compile(
    r'(?:pip install|dependencies\s*=\s*\[)\s*"?econflow>=1\.0,<2\.0"?'
)


# Corrected 2026-07-18 (Repository Integrity Repair): the regex above matches
# the code block regardless of surrounding prose, so it previously flagged
# §11.1's own forward-looking guidance ("Once EconFlow reaches v1.0 ...
# tighten to ...") as if it were a present-tense install instruction --
# exactly the exception this test's comment already said should be allowed,
# but the implementation never actually checked for it. Now excluded by
# requiring one of the forward-looking marker phrases within the preceding
# 5 lines.
_FORWARD_LOOKING_MARKERS = ("reaches v1.0", "Once EconFlow")


def test_plugin_sdk_no_phantom_v1_constraint() -> None:
    """PLUGIN_SDK.md must not instruct plugin devs to use econflow>=1.0,<2.0 now (I-04)."""
    if not _PLUGIN_SDK.exists():
        pytest.skip(f"PLUGIN_SDK.md not found: {_PLUGIN_SDK}")
    text = _PLUGIN_SDK.read_text(encoding="utf-8")
    lines = text.splitlines()
    bad_lines = []
    for i, line in enumerate(lines):
        if not _BAD_SDK_CONSTRAINT_PATTERN.search(line):
            continue
        context = "\n".join(lines[max(0, i - 5):i])
        if any(marker in context for marker in _FORWARD_LOOKING_MARKERS):
            continue  # allowed forward-looking exception (§11.1)
        bad_lines.append((i + 1, line.strip()))
    assert not bad_lines, (
        f"PLUGIN_SDK.md uses phantom econflow>=1.0,<2.0 constraint in "
        f"install context on line(s): {bad_lines}\n"
        "Fix: use 'econflow>=0.1.0' until EconFlow reaches v1.0."
    )


# ---------------------------------------------------------------------------
# I-05 — Core estimation classes exported from the root package
# ---------------------------------------------------------------------------

def test_root_package_exports_estimation_classes() -> None:
    """from econflow import PooledOLS etc. must work (I-05)."""
    import econflow  # noqa: PLC0415

    required_exports = [
        "PooledOLS",
        "EntityFE",
        "TwoWayFE",
        "BaseEstimator",
        "EstimationResult",
        "DiagnosticResult",
        "register_estimator",
        "list_estimators",
    ]
    missing = [name for name in required_exports if not hasattr(econflow, name)]
    assert not missing, (
        f"econflow root package is missing top-level exports: {missing}\n"
        "Fix: add 'from econflow.estimation import ...' to "
        "src/econflow/__init__.py"
    )


def test_root_package_all_contains_estimation_classes() -> None:
    """Estimation classes must appear in econflow.__all__ (I-05)."""
    import econflow  # noqa: PLC0415

    required_in_all = [
        "PooledOLS",
        "EstimationResult",
        "DiagnosticResult",
        "register_estimator",
        "list_estimators",
    ]
    missing = [name for name in required_in_all if name not in econflow.__all__]
    assert not missing, (
        f"econflow.__all__ is missing: {missing}"
    )
