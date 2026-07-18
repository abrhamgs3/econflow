"""
econflow.replication.inspector — Pre-flight checks for project replication.

Examines a project directory and returns an :class:`InspectionReport`
without executing the pipeline or modifying any files.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import yaml

from econflow.replication.models import InspectionReport, ProjectCheck

# Minimum Python version for EconFlow
_MIN_PYTHON = (3, 10)

# Config file locations relative to project root (first match wins)
_CONFIG_CANDIDATES = [
    Path("config") / "config.yaml",
    Path("config.yaml"),
]
_MODELS_CANDIDATES = [
    Path("config") / "models.yaml",
    Path("models.yaml"),
]
_OUTPUTS_CANDIDATES = [
    Path("config") / "outputs.yaml",
    Path("outputs.yaml"),
]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def inspect_project(project_dir: Path) -> InspectionReport:
    """
    Run all pre-flight checks on *project_dir*.

    Parameters
    ----------
    project_dir:
        Root directory of an EconFlow project.

    Returns
    -------
    InspectionReport
        Structured result with one :class:`~econflow.replication.models.ProjectCheck`
        per check performed.
    """
    project_dir = project_dir.resolve()
    checks: list[ProjectCheck] = []

    # 1. Python version ---------------------------------------------------
    checks.append(_check_python_version())

    # 2. Config files -----------------------------------------------------
    cfg_check, cfg_path, cfg_data = _check_config(project_dir)
    checks.append(cfg_check)

    mdl_check, mdl_path, mdl_data = _check_models(project_dir)
    checks.append(mdl_check)

    out_check, out_path, _out_data = _check_outputs_cfg(project_dir)
    checks.append(out_check)

    # 3. Data file --------------------------------------------------------
    data_path: Path | None = None
    if cfg_data is not None:
        data_check, data_path = _check_data_file(project_dir, cfg_path, cfg_data)
        checks.append(data_check)

        # 4. Data checksum against provenance ----------------------------
        checks.append(_check_data_checksum(project_dir, data_path, cfg_data))
    else:
        checks.append(
            ProjectCheck(
                check_id="data_found",
                name="Data file",
                status="skip",
                message="Skipped — config could not be parsed.",
            )
        )
        checks.append(
            ProjectCheck(
                check_id="data_checksum",
                name="Data checksum",
                status="skip",
                message="Skipped — config could not be parsed.",
            )
        )

    # 5. Estimator registration -------------------------------------------
    if mdl_data is not None:
        checks.append(_check_estimators(mdl_data))
    else:
        checks.append(
            ProjectCheck(
                check_id="estimators_registered",
                name="Estimator registry",
                status="skip",
                message="Skipped — models.yaml could not be parsed.",
            )
        )

    # 6. Key dependencies -------------------------------------------------
    checks.append(_check_dependencies(project_dir))

    return InspectionReport.build(project_dir=project_dir, checks=checks)


# ---------------------------------------------------------------------------
# Individual checks
# ---------------------------------------------------------------------------

def _check_python_version() -> ProjectCheck:
    v = sys.version_info
    ok = (v.major, v.minor) >= _MIN_PYTHON
    ver_str = f"{v.major}.{v.minor}.{v.micro}"
    min_str = ".".join(str(x) for x in _MIN_PYTHON)
    if ok:
        return ProjectCheck(
            check_id="python_version",
            name="Python version",
            status="pass",
            message=f"Python {ver_str}",
        )
    return ProjectCheck(
        check_id="python_version",
        name="Python version",
        status="fail",
        message=f"Python {ver_str} is below minimum {min_str}",
    )


def _find_file(project_dir: Path, candidates: list[Path]) -> Path | None:
    for rel in candidates:
        p = project_dir / rel
        if p.exists():
            return p
    return None


def _load_yaml_safe(path: Path) -> tuple[bool, Any, str]:
    """Returns (ok, data, error_message)."""
    try:
        with path.open() as f:
            data = yaml.safe_load(f)
        return True, data, ""
    except Exception as exc:
        return False, None, str(exc)


def _check_config(
    project_dir: Path,
) -> tuple[ProjectCheck, Path | None, dict | None]:
    p = _find_file(project_dir, _CONFIG_CANDIDATES)
    if p is None:
        tried = ", ".join(str(c) for c in _CONFIG_CANDIDATES)
        return (
            ProjectCheck(
                check_id="config_found",
                name="Config file",
                status="fail",
                message="config.yaml not found.",
                detail=f"Looked for: {tried}",
            ),
            None,
            None,
        )
    ok, data, err = _load_yaml_safe(p)
    if not ok:
        return (
            ProjectCheck(
                check_id="config_found",
                name="Config file",
                status="fail",
                message=f"config.yaml found but could not be parsed: {err}",
                detail=str(p),
            ),
            p,
            None,
        )
    return (
        ProjectCheck(
            check_id="config_found",
            name="Config file",
            status="pass",
            message=str(p.relative_to(project_dir)),
        ),
        p,
        data,
    )


def _check_models(
    project_dir: Path,
) -> tuple[ProjectCheck, Path | None, dict | None]:
    p = _find_file(project_dir, _MODELS_CANDIDATES)
    if p is None:
        tried = ", ".join(str(c) for c in _MODELS_CANDIDATES)
        return (
            ProjectCheck(
                check_id="models_found",
                name="Models config",
                status="fail",
                message="models.yaml not found.",
                detail=f"Looked for: {tried}",
            ),
            None,
            None,
        )
    ok, data, err = _load_yaml_safe(p)
    if not ok:
        return (
            ProjectCheck(
                check_id="models_found",
                name="Models config",
                status="fail",
                message=f"models.yaml found but could not be parsed: {err}",
                detail=str(p),
            ),
            p,
            None,
        )
    return (
        ProjectCheck(
            check_id="models_found",
            name="Models config",
            status="pass",
            message=str(p.relative_to(project_dir)),
        ),
        p,
        data,
    )


def _check_outputs_cfg(
    project_dir: Path,
) -> tuple[ProjectCheck, Path | None, dict | None]:
    p = _find_file(project_dir, _OUTPUTS_CANDIDATES)
    if p is None:
        tried = ", ".join(str(c) for c in _OUTPUTS_CANDIDATES)
        return (
            ProjectCheck(
                check_id="outputs_cfg_found",
                name="Outputs config",
                status="fail",
                message="outputs.yaml not found.",
                detail=f"Looked for: {tried}",
            ),
            None,
            None,
        )
    ok, data, err = _load_yaml_safe(p)
    if not ok:
        return (
            ProjectCheck(
                check_id="outputs_cfg_found",
                name="Outputs config",
                status="fail",
                message=f"outputs.yaml found but could not be parsed: {err}",
                detail=str(p),
            ),
            p,
            None,
        )
    return (
        ProjectCheck(
            check_id="outputs_cfg_found",
            name="Outputs config",
            status="pass",
            message=str(p.relative_to(project_dir)),
        ),
        p,
        data,
    )


def _check_data_file(
    project_dir: Path,
    config_file: Path | None,
    cfg_data: dict,
) -> tuple[ProjectCheck, Path | None]:
    raw_path = (cfg_data.get("data") or {}).get("path", "")
    if not raw_path:
        return (
            ProjectCheck(
                check_id="data_found",
                name="Data file",
                status="fail",
                message="data.path not set in config.yaml.",
            ),
            None,
        )
    # Resolve relative paths against the config file's directory (same convention
    # as pipeline_generic.py) so the project is CWD-independent.
    p = Path(raw_path)
    if not p.is_absolute():
        base = config_file.parent if config_file is not None else project_dir
        p = (base / p).resolve()
    if not p.exists():
        return (
            ProjectCheck(
                check_id="data_found",
                name="Data file",
                status="fail",
                message=f"Data file not found: {p}",
                detail=f"Declared in config.yaml as: {raw_path}",
            ),
            None,
        )
    size_kb = p.stat().st_size // 1024
    return (
        ProjectCheck(
            check_id="data_found",
            name="Data file",
            status="pass",
            message=f"{p.name} ({size_kb} KB)",
        ),
        p,
    )


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _check_data_checksum(
    project_dir: Path,
    data_path: Path | None,
    cfg_data: dict,
) -> ProjectCheck:
    if data_path is None or not data_path.exists():
        return ProjectCheck(
            check_id="data_checksum",
            name="Data checksum",
            status="skip",
            message="Skipped — data file not found.",
        )

    # Look for provenance record
    prov_path = project_dir / "outputs" / "provenance" / "run_metadata.json"
    if not prov_path.exists():
        return ProjectCheck(
            check_id="data_checksum",
            name="Data checksum",
            status="warn",
            message="No provenance record found; cannot verify checksum.",
            detail=str(prov_path),
        )

    try:
        with prov_path.open() as f:
            prov = json.load(f)
    except Exception as exc:
        return ProjectCheck(
            check_id="data_checksum",
            name="Data checksum",
            status="warn",
            message=f"Could not read provenance record: {exc}",
        )

    recorded_hash: str | None = None
    # Support both provenance schema versions
    input_hashes = prov.get("input_hashes") or {}
    if "data" in input_hashes:
        recorded_hash = input_hashes["data"]

    if not recorded_hash:
        return ProjectCheck(
            check_id="data_checksum",
            name="Data checksum",
            status="warn",
            message="Provenance record exists but no data checksum found.",
        )

    actual_hash = _sha256_file(data_path)
    if actual_hash == recorded_hash:
        return ProjectCheck(
            check_id="data_checksum",
            name="Data checksum",
            status="pass",
            message=f"SHA-256 verified: {actual_hash[:16]}…",
        )
    return ProjectCheck(
        check_id="data_checksum",
        name="Data checksum",
        status="fail",
        message="Data file checksum does not match provenance record.",
        detail=f"Expected: {recorded_hash[:16]}…  Got: {actual_hash[:16]}…",
    )


def _check_estimators(mdl_data: dict) -> ProjectCheck:
    from econflow.estimation import list_estimators

    models = mdl_data.get("models", [])
    if not models:
        return ProjectCheck(
            check_id="estimators_registered",
            name="Estimator registry",
            status="warn",
            message="No models defined in models.yaml.",
        )

    registered = {m["id"] for m in list_estimators()}
    missing: list[str] = []
    found: list[str] = []

    for spec in models:
        raw_id = spec.get("estimator", "")
        if not raw_id:
            continue
        # Normalize to lowercase to match registry (pipeline also does .upper() internally)
        estimator_id = raw_id.lower()
        if estimator_id in registered:
            found.append(estimator_id)
        else:
            missing.append(raw_id)

    if missing:
        return ProjectCheck(
            check_id="estimators_registered",
            name="Estimator registry",
            status="fail",
            message=f"Unregistered estimator(s): {', '.join(missing)}",
            detail=f"Available: {', '.join(sorted(registered))}",
        )
    return ProjectCheck(
        check_id="estimators_registered",
        name="Estimator registry",
        status="pass",
        message=f"{len(found)} estimator(s) registered: {', '.join(found)}",
    )


def _check_dependencies(project_dir: Path) -> ProjectCheck:
    import importlib.metadata as importlib_metadata

    tracked = [
        "econflow",
        "pandas",
        "linearmodels",
        "statsmodels",
        "numpy",
        "pyyaml",
    ]
    installed: dict[str, str] = {}
    missing: list[str] = []

    for pkg in tracked:
        try:
            installed[pkg] = importlib_metadata.version(pkg)
        except importlib_metadata.PackageNotFoundError:
            missing.append(pkg)

    if missing:
        return ProjectCheck(
            check_id="dependencies",
            name="Dependencies",
            status="fail",
            message=f"Required packages not installed: {', '.join(missing)}",
        )

    summary = "  ".join(f"{k} {v}" for k, v in installed.items())
    return ProjectCheck(
        check_id="dependencies",
        name="Dependencies",
        status="pass",
        message=summary,
    )
