"""
econflow.replication.comparator — Compare two output directories.

Produces a :class:`~econflow.replication.models.ComparisonReport` by
comparing every file in the baseline directory against its counterpart
in the replica directory.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd

from econflow.replication.models import ComparisonReport, OutputComparison

# Default numeric tolerance for floating-point comparison
DEFAULT_TOLERANCE: float = 1e-6


def compare_outputs(
    baseline_dir: Path,
    replica_dir: Path,
    *,
    tolerance: float = DEFAULT_TOLERANCE,
    extensions: tuple[str, ...] = (".csv", ".tex", ".json"),
    baseline_only: bool = False,
) -> ComparisonReport:
    """
    Compare all matching files between *baseline_dir* and *replica_dir*.

    Parameters
    ----------
    baseline_dir:
        Directory containing the original (authoritative) outputs.
    replica_dir:
        Directory containing the reproduced outputs.
    tolerance:
        Absolute tolerance for floating-point comparisons.
    extensions:
        File extensions to compare.  Other files are ignored.
    baseline_only:
        When *True*, only files present in *baseline_dir* are compared.
        Extra files in *replica_dir* are silently ignored.  Use this in
        ``econflow reproduce`` where extra intermediate files are expected.
        When *False* (default), extra replica files are reported as
        ``missing_baseline`` warnings.

    Returns
    -------
    ComparisonReport
        Structured comparison with one entry per file.
    """
    baseline_dir = baseline_dir.resolve()
    replica_dir = replica_dir.resolve()

    comparisons: list[OutputComparison] = []

    # Files in baseline
    baseline_files = {
        p.relative_to(baseline_dir)
        for p in baseline_dir.rglob("*")
        if p.is_file() and p.suffix in extensions
    }

    # Files in replica
    replica_files = {
        p.relative_to(replica_dir)
        for p in replica_dir.rglob("*")
        if p.is_file() and p.suffix in extensions
    }

    # Compare files present in both (or only baseline if baseline_only=True)
    candidates = baseline_files if baseline_only else (baseline_files | replica_files)
    for rel in sorted(candidates):
        b_path = baseline_dir / rel
        r_path = replica_dir / rel

        if rel not in baseline_files:
            comparisons.append(
                OutputComparison(
                    filename=str(rel),
                    status="missing_baseline",
                    message="File exists in replica but not in baseline.",
                )
            )
            continue

        if rel not in replica_files:
            comparisons.append(
                OutputComparison(
                    filename=str(rel),
                    status="missing_replica",
                    message="File exists in baseline but not in replica.",
                )
            )
            continue

        # Both exist — compare by type
        suffix = rel.suffix.lower()
        if suffix == ".csv":
            comparisons.append(_compare_csv(rel, b_path, r_path, tolerance))
        elif suffix == ".tex":
            comparisons.append(_compare_tex(rel, b_path, r_path))
        elif suffix == ".json":
            comparisons.append(_compare_json(rel, b_path, r_path, tolerance))
        else:
            comparisons.append(
                OutputComparison(
                    filename=str(rel),
                    status="skip",
                    message=f"Unsupported extension: {suffix}",
                )
            )

    if not comparisons:
        comparisons.append(
            OutputComparison(
                filename="(none)",
                status="skip",
                message="No comparable files found.",
            )
        )

    return ComparisonReport.build(
        baseline_dir=baseline_dir,
        replica_dir=replica_dir,
        comparisons=comparisons,
        numeric_tolerance=tolerance,
    )


# ---------------------------------------------------------------------------
# File-type comparators
# ---------------------------------------------------------------------------

def _compare_csv(
    rel: Path,
    b_path: Path,
    r_path: Path,
    tolerance: float,
) -> OutputComparison:
    filename = str(rel)
    try:
        df_b = pd.read_csv(b_path)
        df_r = pd.read_csv(r_path)
    except Exception as exc:
        return OutputComparison(
            filename=filename,
            status="mismatch",
            message=f"Could not read CSV: {exc}",
        )

    # Shape check
    if df_b.shape != df_r.shape:
        return OutputComparison(
            filename=filename,
            status="mismatch",
            message=(
                f"Shape mismatch: baseline {df_b.shape} vs "
                f"replica {df_r.shape}"
            ),
        )

    # Column check
    if list(df_b.columns) != list(df_r.columns):
        missing = set(df_b.columns) - set(df_r.columns)
        extra = set(df_r.columns) - set(df_b.columns)
        msg_parts = []
        if missing:
            msg_parts.append(f"missing columns: {sorted(missing)}")
        if extra:
            msg_parts.append(f"extra columns: {sorted(extra)}")
        return OutputComparison(
            filename=filename,
            status="mismatch",
            message="; ".join(msg_parts),
            columns_differ=sorted(missing | extra),
        )

    # Per-column comparison
    max_diff = 0.0
    rows_differ_total = 0
    diff_cols: list[str] = []

    for col in df_b.columns:
        b_col = df_b[col]
        r_col = df_r[col]

        # Numeric comparison
        if pd.api.types.is_numeric_dtype(b_col):
            try:
                b_vals = b_col.astype(float)
                r_vals = r_col.astype(float)
                abs_diff = (b_vals - r_vals).abs()
                col_max = abs_diff.max()
                if pd.isna(col_max):
                    col_max = 0.0
                max_diff = max(max_diff, col_max)
                rows_differ = int((abs_diff > tolerance).sum())
                if rows_differ > 0:
                    rows_differ_total += rows_differ
                    diff_cols.append(col)
            except Exception:
                diff_cols.append(col)
        else:
            # String comparison
            mismatch_mask = b_col.fillna("").astype(str) != r_col.fillna("").astype(str)
            n_differ = int(mismatch_mask.sum())
            if n_differ > 0:
                rows_differ_total += n_differ
                diff_cols.append(col)

    if diff_cols:
        return OutputComparison(
            filename=filename,
            status="mismatch",
            max_abs_diff=max_diff,
            rows_differ=rows_differ_total,
            columns_differ=diff_cols,
            message=(
                f"Differences in columns: {diff_cols}  "
                f"max |Δ| = {max_diff:.2e}  rows differ = {rows_differ_total}"
            ),
        )

    return OutputComparison(
        filename=filename,
        status="match",
        max_abs_diff=max_diff,
        rows_differ=0,
        message=f"All {len(df_b)} rows match (max |Δ| = {max_diff:.2e})",
    )


def _compare_tex(rel: Path, b_path: Path, r_path: Path) -> OutputComparison:
    filename = str(rel)
    try:
        b_text = _normalise_tex(b_path.read_text(encoding="utf-8"))
        r_text = _normalise_tex(r_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return OutputComparison(
            filename=filename,
            status="mismatch",
            message=f"Could not read LaTeX file: {exc}",
        )

    if b_text == r_text:
        return OutputComparison(
            filename=filename,
            status="match",
            message="LaTeX content matches (after normalisation).",
        )

    # Count structural elements to distinguish minor formatting vs real changes
    b_lines = b_text.splitlines()
    r_lines = r_text.splitlines()
    if len(b_lines) != len(r_lines):
        return OutputComparison(
            filename=filename,
            status="mismatch",
            message=(
                f"LaTeX line count differs: baseline {len(b_lines)} vs "
                f"replica {len(r_lines)}"
            ),
        )
    # Same line count but different content — treat as warn-level mismatch
    return OutputComparison(
        filename=filename,
        status="mismatch",
        message="LaTeX content differs after normalisation.",
    )


def _normalise_tex(text: str) -> str:
    """Strip comments and normalise whitespace in LaTeX text."""
    # Remove % comments
    lines = [re.sub(r"%.*$", "", line) for line in text.splitlines()]
    # Collapse whitespace within lines
    lines = [" ".join(line.split()) for line in lines]
    # Remove empty lines
    lines = [line for line in lines if line.strip()]
    return "\n".join(lines)


def _compare_json(
    rel: Path,
    b_path: Path,
    r_path: Path,
    tolerance: float,
) -> OutputComparison:
    filename = str(rel)
    try:
        b_data = json.loads(b_path.read_text(encoding="utf-8"))
        r_data = json.loads(r_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return OutputComparison(
            filename=filename,
            status="mismatch",
            message=f"Could not parse JSON: {exc}",
        )

    diffs = _json_diff(b_data, r_data, tolerance=tolerance, path="")
    if not diffs:
        return OutputComparison(
            filename=filename,
            status="match",
            message="JSON content matches.",
        )

    # Emit first 3 diffs in message
    msg = "; ".join(diffs[:3])
    if len(diffs) > 3:
        msg += f" (and {len(diffs) - 3} more)"
    return OutputComparison(
        filename=filename,
        status="mismatch",
        message=msg,
    )


def _json_diff(
    a: object,
    b: object,
    tolerance: float,
    path: str,
) -> list[str]:
    diffs: list[str] = []
    if isinstance(a, dict) and isinstance(b, dict):
        for key in sorted(set(a) | set(b)):
            child_path = f"{path}.{key}" if path else key
            if key not in a:
                diffs.append(f"{child_path}: missing in baseline")
            elif key not in b:
                diffs.append(f"{child_path}: missing in replica")
            else:
                diffs.extend(_json_diff(a[key], b[key], tolerance, child_path))
    elif isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            diffs.append(f"{path}: list length {len(a)} vs {len(b)}")
        else:
            for i, (ai, bi) in enumerate(zip(a, b)):
                diffs.extend(_json_diff(ai, bi, tolerance, f"{path}[{i}]"))
    elif isinstance(a, (int, float)) and isinstance(b, (int, float)):
        if abs(float(a) - float(b)) > tolerance:
            diffs.append(f"{path}: {a} vs {b} (diff={abs(float(a)-float(b)):.2e})")
    else:
        if a != b:
            diffs.append(f"{path}: {a!r} vs {b!r}")
    return diffs
