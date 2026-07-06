"""
econflow.integrity.drift — Configuration and environment drift detection.

:func:`detect_drift` compares two :class:`ReproducibilityCertificate`
JSON dicts and reports which fields changed.  Typical use cases:

* Verify a re-run against the published certificate.
* Detect package-version upgrades between two runs.
* Alert when input data has changed.

Usage
-----
::

    from econflow.integrity.drift import detect_drift
    from econflow.integrity.certificate import ReproducibilityCertificate

    baseline = ReproducibilityCertificate.load("outputs/baseline_cert.json")
    current  = ReproducibilityCertificate.load("outputs/current_cert.json")

    report = detect_drift(baseline.to_dict(), current.to_dict())
    print(report.to_json())
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# DriftItem
# ---------------------------------------------------------------------------


@dataclass
class DriftItem:
    """
    A single detected difference between baseline and current certificates.

    Parameters
    ----------
    field:
        Dot-path of the changed field (e.g. ``"environment.git.commit"``).
    baseline_value:
        Value in the baseline certificate.
    current_value:
        Value in the current certificate.
    delta:
        Human-readable description of the change, or ``None`` for
        non-numeric fields.
    severity:
        ``"none"`` (informational), ``"warn"``, or ``"fail"``.
    message:
        Short human-readable explanation.
    """

    field: str
    baseline_value: Any
    current_value: Any
    delta: Any = None
    severity: str = "warn"    # "none" | "warn" | "fail"
    message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "field": self.field,
            "baseline_value": self.baseline_value,
            "current_value": self.current_value,
            "delta": self.delta,
            "severity": self.severity,
            "message": self.message,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DriftItem:
        return cls(
            field=str(data.get("field", "")),
            baseline_value=data.get("baseline_value"),
            current_value=data.get("current_value"),
            delta=data.get("delta"),
            severity=str(data.get("severity", "warn")),
            message=str(data.get("message", "")),
        )


# ---------------------------------------------------------------------------
# DriftReport
# ---------------------------------------------------------------------------

_STATUS_RANK: dict[str, int] = {"fail": 2, "warn": 1, "none": 0}


@dataclass
class DriftReport:
    """
    Aggregated drift-detection result comparing two certificates.

    Parameters
    ----------
    baseline_id:
        ``certificate_id`` of the baseline certificate.
    current_id:
        ``certificate_id`` of the current certificate.
    baseline_path:
        Filesystem path of the baseline certificate (informational).
    current_path:
        Filesystem path of the current certificate (informational).
    items:
        List of detected :class:`DriftItem` objects.
    overall_status:
        Worst severity across all items: ``"pass"``, ``"warn"``, or ``"fail"``.
    generated_utc:
        ISO-8601 UTC timestamp when the report was generated.
    """

    baseline_id: str = ""
    current_id: str = ""
    baseline_path: str = ""
    current_path: str = ""
    items: list[DriftItem] = field(default_factory=list)
    overall_status: str = "pass"
    generated_utc: str = field(
        default_factory=lambda: datetime.now(tz=timezone.utc).isoformat()
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "baseline_id": self.baseline_id,
            "current_id": self.current_id,
            "baseline_path": self.baseline_path,
            "current_path": self.current_path,
            "overall_status": self.overall_status,
            "generated_utc": self.generated_utc,
            "n_items": len(self.items),
            "items": [i.to_dict() for i in self.items],
        }

    def to_json(self, *, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    def save(self, path: str | Path) -> None:
        """Write the drift report to *path* as a JSON file."""
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".tmp")
        try:
            with open(tmp, "w", encoding="utf-8") as fh:
                fh.write(self.to_json())
                fh.write("\n")
                fh.flush()
                os.fsync(fh.fileno())
            tmp.replace(p)
        except Exception as exc:
            try:
                tmp.unlink(missing_ok=True)
            except OSError:
                pass
            raise OSError(f"Could not write drift report to {p}: {exc}") from exc

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DriftReport:
        return cls(
            baseline_id=str(data.get("baseline_id", "")),
            current_id=str(data.get("current_id", "")),
            baseline_path=str(data.get("baseline_path", "")),
            current_path=str(data.get("current_path", "")),
            overall_status=str(data.get("overall_status", "pass")),
            generated_utc=str(data.get("generated_utc", "")),
            items=[DriftItem.from_dict(i) for i in (data.get("items") or [])],
        )

    def __repr__(self) -> str:
        return (
            f"<DriftReport status={self.overall_status!r} "
            f"items={len(self.items)}>"
        )


# ---------------------------------------------------------------------------
# Internal comparison helpers
# ---------------------------------------------------------------------------


def _severity_from_items(items: list[DriftItem]) -> str:
    """Return worst severity across *items*."""
    if not items:
        return "pass"
    rank = max(_STATUS_RANK.get(i.severity, 0) for i in items)
    if rank >= 2:
        return "fail"
    if rank >= 1:
        return "warn"
    return "pass"


def _compare_git(
    baseline: dict[str, Any],
    current: dict[str, Any],
) -> list[DriftItem]:
    items: list[DriftItem] = []
    b_commit = (baseline.get("environment") or {}).get("git", {}).get("commit")
    c_commit = (current.get("environment") or {}).get("git", {}).get("commit")
    if b_commit != c_commit:
        items.append(
            DriftItem(
                field="environment.git.commit",
                baseline_value=b_commit,
                current_value=c_commit,
                severity="warn",
                message=(
                    "Git commit changed between baseline and current run.  "
                    "The codebase may have been modified."
                ),
            )
        )

    b_dirty = (baseline.get("environment") or {}).get("git", {}).get("dirty")
    c_dirty = (current.get("environment") or {}).get("git", {}).get("dirty")
    if b_dirty != c_dirty and c_dirty:
        items.append(
            DriftItem(
                field="environment.git.dirty",
                baseline_value=b_dirty,
                current_value=c_dirty,
                severity="warn",
                message="Working tree is dirty in the current run.",
            )
        )
    return items


def _compare_packages(
    baseline: dict[str, Any],
    current: dict[str, Any],
) -> list[DriftItem]:
    items: list[DriftItem] = []
    b_pkgs: dict[str, Any] = (
        (baseline.get("environment") or {}).get("packages") or {}
    )
    c_pkgs: dict[str, Any] = (
        (current.get("environment") or {}).get("packages") or {}
    )
    all_keys = sorted(set(b_pkgs) | set(c_pkgs))
    for pkg in all_keys:
        bv = b_pkgs.get(pkg)
        cv = c_pkgs.get(pkg)
        if bv != cv:
            sev = "warn"
            msg = f"Package '{pkg}' version changed: {bv!r} → {cv!r}."
            if cv is None:
                sev = "fail"
                msg = f"Package '{pkg}' present in baseline but missing now."
            elif bv is None:
                sev = "none"
                msg = f"Package '{pkg}' is new in the current environment."
            items.append(
                DriftItem(
                    field=f"environment.packages.{pkg}",
                    baseline_value=bv,
                    current_value=cv,
                    severity=sev,
                    message=msg,
                )
            )
    return items


def _compare_data(
    baseline: dict[str, Any],
    current: dict[str, Any],
) -> list[DriftItem]:
    items: list[DriftItem] = []
    b_data: list[dict] = baseline.get("data") or []
    c_data: list[dict] = current.get("data") or []

    # Index by path for comparison
    b_by_path = {d.get("path", ""): d for d in b_data}
    c_by_path = {d.get("path", ""): d for d in c_data}

    all_paths = sorted(set(b_by_path) | set(c_by_path))
    for path in all_paths:
        bd = b_by_path.get(path)
        cd = c_by_path.get(path)
        if bd is None:
            items.append(
                DriftItem(
                    field=f"data[{path!r}]",
                    baseline_value=None,
                    current_value=path,
                    severity="none",
                    message=f"Dataset {path!r} is new in the current run.",
                )
            )
            continue
        if cd is None:
            items.append(
                DriftItem(
                    field=f"data[{path!r}]",
                    baseline_value=path,
                    current_value=None,
                    severity="warn",
                    message=f"Dataset {path!r} was present in baseline but is absent now.",
                )
            )
            continue
        b_sha = bd.get("sha256")
        c_sha = cd.get("sha256")
        if b_sha != c_sha:
            items.append(
                DriftItem(
                    field=f"data[{path!r}].sha256",
                    baseline_value=b_sha,
                    current_value=c_sha,
                    severity="fail",
                    message=(
                        f"Input dataset {path!r} content changed "
                        f"(SHA-256 mismatch).  Results may differ."
                    ),
                )
            )
        b_rows = bd.get("row_count")
        c_rows = cd.get("row_count")
        if b_rows is not None and c_rows is not None and b_rows != c_rows:
            delta = c_rows - b_rows
            items.append(
                DriftItem(
                    field=f"data[{path!r}].row_count",
                    baseline_value=b_rows,
                    current_value=c_rows,
                    delta=delta,
                    severity="warn",
                    message=(
                        f"Dataset {path!r} row count changed: "
                        f"{b_rows} → {c_rows} (Δ={delta:+d})."
                    ),
                )
            )
    return items


def _compare_config(
    baseline: dict[str, Any],
    current: dict[str, Any],
) -> list[DriftItem]:
    items: list[DriftItem] = []
    b_cfg = baseline.get("config") or {}
    c_cfg = current.get("config") or {}
    if not b_cfg and not c_cfg:
        return items
    b_sha = b_cfg.get("sha256") if b_cfg else None
    c_sha = c_cfg.get("sha256") if c_cfg else None
    if b_sha != c_sha:
        items.append(
            DriftItem(
                field="config.sha256",
                baseline_value=b_sha,
                current_value=c_sha,
                severity="warn",
                message=(
                    "Configuration file content changed between runs.  "
                    "Verify that analysis settings are identical."
                ),
            )
        )
    return items


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def detect_drift(
    baseline: dict[str, Any] | str | Path,
    current: dict[str, Any] | str | Path,
    *,
    baseline_path: str = "",
    current_path: str = "",
) -> DriftReport:
    """
    Compare two certificate dicts and return a :class:`DriftReport`.

    Parameters
    ----------
    baseline:
        Baseline certificate as a dict, or a path to a JSON file.
    current:
        Current certificate as a dict, or a path to a JSON file.
    baseline_path:
        Display path for the baseline (informational only).
    current_path:
        Display path for the current certificate (informational only).

    Returns
    -------
    DriftReport
    """
    def _load(source: dict[str, Any] | str | Path) -> tuple[dict, str]:
        if isinstance(source, dict):
            return source, ""
        p = Path(source)
        data = json.loads(p.read_text(encoding="utf-8"))
        return data, str(p)

    b_dict, b_path_auto = _load(baseline)
    c_dict, c_path_auto = _load(current)

    items: list[DriftItem] = []
    items.extend(_compare_git(b_dict, c_dict))
    items.extend(_compare_packages(b_dict, c_dict))
    items.extend(_compare_data(b_dict, c_dict))
    items.extend(_compare_config(b_dict, c_dict))

    return DriftReport(
        baseline_id=str(b_dict.get("certificate_id", "")),
        current_id=str(c_dict.get("certificate_id", "")),
        baseline_path=baseline_path or b_path_auto,
        current_path=current_path or c_path_auto,
        items=items,
        overall_status=_severity_from_items(items),
    )
