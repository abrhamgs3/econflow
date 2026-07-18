"""
econflow.replication.reporter — Format replication results as documents.

Converts :class:`~econflow.replication.models.InspectionReport`,
:class:`~econflow.replication.models.ReplicationResult`, and
:class:`~econflow.replication.models.ComparisonReport` objects into
human-readable Markdown and machine-readable JSON.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from econflow.replication.models import (
    ComparisonReport,
    InspectionReport,
    ReplicationResult,
)

_STATUS_EMOJI = {
    "pass": "✔",
    "warn": "⚠",
    "fail": "✘",
    "success": "✔",
    "partial": "⚠",
    "failed": "✘",
    "match": "✔",
    "mismatch": "✘",
    "missing_replica": "⚠",
    "missing_baseline": "⚠",
    "skip": "–",
}


# ---------------------------------------------------------------------------
# Bundled report
# ---------------------------------------------------------------------------

@dataclass
class ReproducibilityReport:
    """
    Full replication report bundling inspection, execution, and comparison.

    At minimum, *inspection* must be provided.  *execution* and *comparison*
    are optional — they are ``None`` when the corresponding step was not run.
    """

    timestamp_utc: str = field(
        default_factory=lambda: datetime.now(tz=timezone.utc).isoformat()
    )
    inspection: InspectionReport | None = None
    execution: ReplicationResult | None = None
    comparison: ComparisonReport | None = None

    @property
    def overall_status(self) -> str:
        statuses = []
        if self.inspection:
            statuses.append(self.inspection.overall_status)
        if self.execution:
            statuses.append(
                "pass" if self.execution.status == "success" else
                "warn" if self.execution.status == "partial" else
                "fail"
            )
        if self.comparison:
            statuses.append(self.comparison.overall_status)

        if not statuses:
            return "skip"
        if "fail" in statuses:
            return "fail"
        if "warn" in statuses:
            return "warn"
        return "pass"

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp_utc": self.timestamp_utc,
            "overall_status": self.overall_status,
            "inspection": self.inspection.to_dict() if self.inspection else None,
            "execution": self.execution.to_dict() if self.execution else None,
            "comparison": self.comparison.to_dict() if self.comparison else None,
        }

    def to_json(self, *, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    def to_markdown(self) -> str:
        """Render the report as a Markdown document."""
        lines: list[str] = []
        emoji = _STATUS_EMOJI.get(self.overall_status, "?")

        lines.append("# EconFlow Reproducibility Report")
        lines.append("")
        lines.append(f"**Generated:** {self.timestamp_utc}")
        lines.append(f"**Overall status:** {emoji} {self.overall_status.upper()}")
        lines.append("")

        if self.inspection:
            lines.extend(_inspection_md(self.inspection))
        if self.execution:
            lines.extend(_execution_md(self.execution))
        if self.comparison:
            lines.extend(_comparison_md(self.comparison))

        return "\n".join(lines)

    def save(self, output_dir: Path) -> tuple[Path, Path]:
        """
        Write ``replication_report.md`` and ``replication_report.json``
        to *output_dir*.

        Returns
        -------
        tuple[Path, Path]
            Paths to the Markdown and JSON files respectively.
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        md_path = output_dir / "replication_report.md"
        json_path = output_dir / "replication_report.json"
        md_path.write_text(self.to_markdown(), encoding="utf-8")
        json_path.write_text(self.to_json(), encoding="utf-8")
        return md_path, json_path


# ---------------------------------------------------------------------------
# Markdown builders
# ---------------------------------------------------------------------------

def _inspection_md(report: InspectionReport) -> list[str]:
    lines = ["## Pre-flight Inspection", ""]
    lines.append(f"**Project:** `{report.project_dir}`")
    lines.append(f"**Timestamp:** {report.timestamp_utc}")
    emoji = _STATUS_EMOJI.get(report.overall_status, "?")
    lines.append(f"**Status:** {emoji} {report.overall_status.upper()}")
    lines.append("")
    lines.append("| Check | Status | Message |")
    lines.append("|-------|--------|---------|")
    for c in report.checks:
        e = _STATUS_EMOJI.get(c.status, "?")
        detail = f" — {c.detail}" if c.detail else ""
        lines.append(
            f"| {c.name} | {e} {c.status} | {c.message}{detail} |"
        )
    lines.append("")
    summary = (
        f"{report.pass_count} passed, {report.warn_count} warned, "
        f"{report.fail_count} failed"
    )
    lines.append(f"*{summary}*")
    lines.append("")
    return lines


def _execution_md(result: ReplicationResult) -> list[str]:
    lines = ["## Replication Execution", ""]
    emoji = _STATUS_EMOJI.get(result.status, "?")
    lines.append(f"**Run ID:** `{result.run_id}`")
    lines.append(f"**Timestamp:** {result.timestamp_utc}")
    lines.append(f"**Status:** {emoji} {result.status.upper()}")
    lines.append(f"**Elapsed:** {result.elapsed_seconds:.1f} s")
    lines.append(f"**Output directory:** `{result.outputs_dir}`")
    lines.append("")
    lines.append("### Steps")
    lines.append("")
    lines.append("| Step | Status | Elapsed | Notes |")
    lines.append("|------|--------|---------|-------|")
    for sr in result.step_results:
        e = _STATUS_EMOJI.get(sr.status, "?")
        notes = ""
        if sr.status == "skipped":
            notes = sr.skip_reason
        elif sr.status == "failed" and sr.stderr:
            notes = sr.stderr[:80].replace("\n", " ")
        lines.append(
            f"| {sr.description} | {e} {sr.status} | "
            f"{sr.elapsed_seconds:.1f}s | {notes} |"
        )
    lines.append("")
    if result.outputs:
        lines.append(f"**Outputs produced:** {len(result.outputs)} file(s)")
        for op in result.outputs[:10]:
            lines.append(f"  - `{op}`")
        if len(result.outputs) > 10:
            lines.append(f"  - *(and {len(result.outputs) - 10} more)*")
    lines.append("")
    return lines


def _comparison_md(report: ComparisonReport) -> list[str]:
    lines = ["## Output Comparison", ""]
    emoji = _STATUS_EMOJI.get(report.overall_status, "?")
    lines.append(f"**Baseline:** `{report.baseline_dir}`")
    lines.append(f"**Replica:** `{report.replica_dir}`")
    lines.append(f"**Status:** {emoji} {report.overall_status.upper()}")
    lines.append(f"**Numeric tolerance:** {report.numeric_tolerance:.0e}")
    lines.append("")
    lines.append("| File | Status | Notes |")
    lines.append("|------|--------|-------|")
    for c in report.comparisons:
        e = _STATUS_EMOJI.get(c.status, "?")
        msg = c.message[:100] if c.message else ""
        lines.append(f"| `{c.filename}` | {e} {c.status} | {msg} |")
    lines.append("")
    summary = (
        f"{report.match_count} matched, {report.mismatch_count} mismatched, "
        f"{report.missing_count} missing"
    )
    lines.append(f"*{summary}*")
    lines.append("")
    return lines
