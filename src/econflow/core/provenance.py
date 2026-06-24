"""
econflow.core.provenance — Run snapshot and lineage recording.

Responsibilities
----------------
* Capture a :class:`RunRecord` at the end of each pipeline run: timestamp,
  Git SHA, serialised configuration, and terminal status.
* Persist the record as a single JSON file inside the project output
  directory so runs are reproducible from the snapshot alone.

Design notes
------------
v0.1 needs one snapshot per run, written atomically at completion.
A full append-only journal with open/finish lifecycle, random-access
retrieval, and concurrent-write safety is deferred to a future release.

Usage (once implemented)
-------------------------
    from econflow.core.provenance import RunRecord, record_run
    record = RunRecord(git_sha=sha, config_snapshot=cfg.model_dump())
    path = record_run(record, output_dir="outputs/econflow")
"""

from __future__ import annotations

import datetime
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal


RunStatus = Literal["success", "failed"]


@dataclass(frozen=True)
class RunRecord:
    """
    Immutable snapshot of a single pipeline run.

    Attributes
    ----------
    run_id:
        UUID-4 string that uniquely identifies this run.
    started_at:
        UTC timestamp when the run began.
    finished_at:
        UTC timestamp when the run completed.
    git_sha:
        Short Git commit SHA of the codebase at run time.
    config_snapshot:
        Serialised project configuration as a plain dict.
    status:
        Terminal status of the run.
    """

    run_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    started_at: datetime.datetime = field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc)
    )
    finished_at: datetime.datetime | None = None
    git_sha: str = ""
    config_snapshot: dict[str, Any] = field(default_factory=dict)
    status: RunStatus = "success"


def record_run(record: RunRecord, output_dir: str | Path) -> Path:
    """
    Serialise *record* to ``<output_dir>/provenance/<run_id>.json``.

    The file is written atomically (write to a temp file, then rename) so
    a crash during serialisation never produces a partial record.

    Parameters
    ----------
    record:
        The completed :class:`RunRecord` to persist.
    output_dir:
        Root output directory for the project (e.g. ``"outputs/econflow"``).

    Returns
    -------
    Path
        Absolute path to the written JSON file.

    Raises
    ------
    econflow.core.exceptions.APRPError
        If serialisation or the atomic rename fails.
    """
    raise NotImplementedError
