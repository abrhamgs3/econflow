"""
econflow.commands.validate — ``econflow validate`` command implementation.

Architecture Stabilization Milestone 4.

Produces a three-phase validation report:

    Phase 1 — Schema validation   (Pydantic v2 models)
    Phase 2 — Semantic validation (config linter rules)
    Phase 3 — Cross-file checks   (cross-file consistency)

Optionally Phase 4 — Data file validation (opt-in via ``--data`` flag).

Output format
-------------
::

    EconFlow validate  config/

    Phase 1: Schema validation
      ✓ config.yaml   — schema valid
      ✓ models.yaml   — schema valid
      ✓ outputs.yaml  — schema valid

    Phase 2: Semantic validation
      ✓ semantic validation passed

    Phase 3: Cross-file validation
      ✓ cross-file validation passed

    ✔ All checks passed.

If errors are found::

    Phase 1: Schema validation
      ✓ config.yaml   — schema valid
      ✗ models.yaml   — schema errors

        models.yaml:
          [models → 0 → estimator]
            Value error: Unknown estimator 'badname'
            Fix: Use one of: ols, fe, twfe, re, fd, iv

    ...

Exit codes
----------
0   All checks passed (errors = 0, warnings allowed)
1   One or more errors
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from rich.console import Console
from rich.markup import escape

from econflow.commands._shared import deep_get, load_yaml_safe

# ---------------------------------------------------------------------------
# Registry-driven supported estimator IDs (backward-compat with existing tests)
# ---------------------------------------------------------------------------
from econflow.estimation.registry import list_estimators as _list_est


def _get_supported_estimators() -> frozenset[str]:
    try:
        import econflow.estimation  # noqa: F401
        return frozenset(e["id"] for e in _list_est() if e["status"] == "implemented")
    except Exception:
        return frozenset()


_SUPPORTED_ESTIMATORS: frozenset[str] = _get_supported_estimators()


# ---------------------------------------------------------------------------
# Status type
# ---------------------------------------------------------------------------

Status = Literal["pass", "warn", "fail", "skip"]

_ICONS: dict[Status, str] = {
    "pass": "[green]✓[/green]",
    "warn": "[yellow]⚠[/yellow]",
    "fail": "[red]✗[/red]",
    "skip": "[dim]-[/dim]",
}


# ---------------------------------------------------------------------------
# Internal result types
# ---------------------------------------------------------------------------

@dataclass
class _Issue:
    source: str         # "config.yaml", "models.yaml", "outputs.yaml"
    location: str       # human-readable key path, e.g. "variables → dependent"
    message: str
    fix: str = ""
    severity: str = "error"   # "error" | "warning" | "info"


@dataclass
class _PhaseResult:
    name: str
    issues: list[_Issue] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not any(i.severity == "error" for i in self.issues)

    @property
    def n_errors(self) -> int:
        return sum(1 for i in self.issues if i.severity == "error")

    @property
    def n_warnings(self) -> int:
        return sum(1 for i in self.issues if i.severity == "warning")


# ---------------------------------------------------------------------------
# Phase 1 — Schema validation via Pydantic
# ---------------------------------------------------------------------------

def _pydantic_loc_to_str(loc: tuple) -> str:
    """Convert a Pydantic error location tuple to a readable key path."""
    parts = []
    for part in loc:
        if isinstance(part, int):
            parts.append(f"[{part}]")
        else:
            parts.append(str(part))
    return " → ".join(parts)


def _schema_validate(
    config_path: Path,
    models_path: Path,
    outputs_path: Path,
) -> tuple[_PhaseResult, Any, Any, Any, dict | None, dict | None, dict | None]:
    """
    Parse YAML and validate with Pydantic models.

    Returns (phase, project_cfg, models_cfg, outputs_cfg, raw_config, raw_models, raw_outputs).
    All config objects may be None if parsing / validation failed.
    """
    from econflow.config.models import ModelsConfig, OutputsConfig, ProjectConfig

    try:
        from pydantic import ValidationError
    except ImportError:
        ValidationError = Exception  # fallback

    phase = _PhaseResult(name="Schema validation")
    raw_config: dict | None = None
    raw_models: dict | None = None
    raw_outputs: dict | None = None

    def _validate_file(path: Path, model_class: Any, label: str):
        raw, err = load_yaml_safe(path)
        if raw is None:
            phase.issues.append(_Issue(
                source=label,
                location="(YAML parse)",
                message=f"Cannot parse YAML: {err}",
                fix=(
                    f"Check {label} for syntax errors.  Common causes: "
                    "wrong indentation, missing quotes around special characters."
                ),
                severity="error",
            ))
            return None, None

        try:
            obj = model_class.model_validate(raw)
            return obj, raw
        except ValidationError as exc:
            for e in exc.errors():
                loc = _pydantic_loc_to_str(e.get("loc", ()))
                msg = e.get("msg", "")
                # Generate a helpful fix hint based on error type
                fix = _pydantic_fix_hint(label, loc, msg, e)
                phase.issues.append(_Issue(
                    source=label,
                    location=loc,
                    message=msg,
                    fix=fix,
                    severity="error",
                ))
            return None, raw

    config_obj, raw_config = _validate_file(config_path, ProjectConfig, "config.yaml")
    models_obj, raw_models = _validate_file(models_path, ModelsConfig, "models.yaml")
    outputs_obj, raw_outputs = _validate_file(outputs_path, OutputsConfig, "outputs.yaml")

    return phase, config_obj, models_obj, outputs_obj, raw_config, raw_models, raw_outputs


def _pydantic_fix_hint(source: str, loc: str, msg: str, err_dict: dict) -> str:
    """Generate an actionable fix hint for a Pydantic validation error."""
    etype = err_dict.get("type", "")

    if etype == "missing":
        return f"Add the required field `{loc.split(' → ')[-1]}:` to {source}."

    if etype == "string_type":
        return f"The value of `{loc}` must be a string.  Wrap it in quotes if needed."

    if etype in ("int_type", "int_parsing"):
        return f"The value of `{loc}` must be an integer."

    if etype == "bool_type":
        return f"The value of `{loc}` must be true or false (no quotes)."

    if etype in ("list_type", "too_short"):
        return f"The field `{loc}` must be a non-empty list."

    if etype == "extra_forbidden":
        field_key = loc.split(" → ")[-1]
        return (
            f"Unknown key `{field_key}` in {source}.  "
            "Remove it or check for a typo.  Run `econflow docs config` for allowed keys."
        )

    if "value_error" in etype or "assertion_error" in etype:
        return f"Check the value at `{loc}` in {source}: {msg}."

    if etype == "literal_error":
        expected = err_dict.get("ctx", {}).get("expected", "")
        return f"`{loc}` must be one of: {expected}."

    return f"Check `{loc}` in {source}."


# ---------------------------------------------------------------------------
# Phase 2 — Semantic validation via ConfigLinter
# ---------------------------------------------------------------------------

def _semantic_validate(
    project_cfg: Any,
    models_cfg: Any,
    outputs_cfg: Any,
    raw_config: dict | None,
    raw_models: dict | None,
    raw_outputs: dict | None,
) -> _PhaseResult:
    """Run ConfigLinter and collect semantic issues."""
    from econflow.config.linter import ConfigLinter

    phase = _PhaseResult(name="Semantic validation")

    linter = ConfigLinter()
    lint_issues = linter.lint(
        project_cfg=project_cfg,
        models_cfg=models_cfg,
        outputs_cfg=outputs_cfg,
        raw_config=raw_config,
        raw_models=raw_models,
        raw_outputs=raw_outputs,
    )

    _sev_map = {"error": "error", "warning": "warning", "info": "info"}

    for issue in lint_issues:
        # Skip info-only items in main flow (surfaced separately)
        sev = _sev_map.get(issue.severity, "info")
        if sev == "info":
            sev = "warning"  # demote to warning for display
        source = issue.location.split(":")[0] if ":" in issue.location else "config"
        phase.issues.append(_Issue(
            source=source,
            location=issue.location,
            message=f"[{issue.code}] {issue.message}",
            fix=issue.fix,
            severity=sev,
        ))

    return phase


# ---------------------------------------------------------------------------
# Phase 3 — Cross-file consistency
# ---------------------------------------------------------------------------

def _cross_file_validate(
    project_cfg: Any,
    models_cfg: Any,
    outputs_cfg: Any,
    raw_config: dict | None,
    raw_models: dict | None,
    raw_outputs: dict | None,
) -> _PhaseResult:
    """Cross-file checks that span multiple config files."""
    phase = _PhaseResult(name="Cross-file validation")

    # Gather data from typed objects first, fall back to raw dicts
    cfg_regressors: set[str] = set()
    model_ids: list[str] = []
    output_model_refs: list[str] = []

    if project_cfg is not None:
        try:
            cfg_regressors = set(project_cfg.variables.regressors or [])
        except AttributeError:
            pass
    elif raw_config:
        cfg_regressors = set((raw_config.get("variables") or {}).get("regressors") or [])

    if models_cfg is not None:
        try:
            model_ids = [m.id for m in models_cfg.models]
        except AttributeError:
            pass
    elif raw_models:
        model_ids = [s.get("id", "") for s in (raw_models.get("models") or [])]

    if outputs_cfg is not None:
        try:
            output_model_refs = list(
                outputs_cfg.outputs.tables.comparison_table.models or []
            )
        except AttributeError:
            pass
    elif raw_outputs:
        output_model_refs = list(
            deep_get(raw_outputs, "outputs", "tables", "comparison_table", "models") or []
        )

    # X-01: model IDs referenced in outputs.comparison_table.models exist
    if output_model_refs:
        model_id_set = set(model_ids)
        missing = [mid for mid in output_model_refs if mid not in model_id_set]
        if missing:
            phase.issues.append(_Issue(
                source="outputs.yaml",
                location="outputs.tables.comparison_table.models",
                message=f"References unknown model ID(s): {missing}",
                fix=(
                    f"Add model(s) {missing} to models.yaml, or remove them "
                    "from outputs.tables.comparison_table.models."
                ),
                severity="error",
            ))

    # X-02: model regressors vs config regressors (already done in linter L-05,
    #        but we re-check here as a cross-file gate)
    if cfg_regressors and models_cfg is not None:
        try:
            for m in models_cfg.models:
                spec_regs = set(m.regressors or [])
                extra = spec_regs - cfg_regressors
                if extra:
                    phase.issues.append(_Issue(
                        source="models.yaml",
                        location=f"models → {m.id} → regressors",
                        message=(
                            f"Model '{m.id}' uses {sorted(extra)} which are not in "
                            "config.yaml variables.regressors"
                        ),
                        fix=(
                            f"Add {sorted(extra)} to config.yaml "
                            "variables.regressors, or fix the typo in models.yaml."
                        ),
                        severity="warning",
                    ))
        except AttributeError:
            pass

    return phase


# ---------------------------------------------------------------------------
# Optional Phase 4 — Data file
# ---------------------------------------------------------------------------

def _data_validate(
    project_cfg: Any,
    raw_config: dict | None,
    config_path: Path,
) -> _PhaseResult:
    phase = _PhaseResult(name="Data file validation")

    _cfg = raw_config or {}
    if project_cfg is not None:
        try:
            data_path_str = project_cfg.data.path
            entity_col = project_cfg.data.entity_col
            time_col = project_cfg.data.time_col
            dep = project_cfg.variables.dependent
            regressors = list(project_cfg.variables.regressors or [])
        except AttributeError:
            data_path_str = None
            entity_col = time_col = dep = ""
            regressors = []
    else:
        data_path_str = deep_get(_cfg, "data", "path")
        entity_col = str(deep_get(_cfg, "data", "entity_col") or "")
        time_col = str(deep_get(_cfg, "data", "time_col") or "")
        dep = str(deep_get(_cfg, "variables", "dependent") or "")
        regressors = list(deep_get(_cfg, "variables", "regressors") or [])

    if not data_path_str:
        phase.issues.append(_Issue(
            source="config.yaml",
            location="data.path",
            message="data.path not configured — cannot validate data file",
            severity="warning",
        ))
        return phase

    raw_p = Path(str(data_path_str))
    data_path = (config_path.parent / raw_p).resolve() if not raw_p.is_absolute() else raw_p

    if not data_path.exists():
        phase.issues.append(_Issue(
            source="data file",
            location=str(data_path),
            message=f"Data file not found: {data_path}",
            fix="Run your data preparation script to generate the file.",
            severity="error",
        ))
        return phase

    try:
        with data_path.open(encoding="utf-8", newline="") as f:
            reader = csv.reader(f)
            headers = next(reader)
            rows = list(reader)
    except Exception as exc:
        phase.issues.append(_Issue(
            source="data file",
            location=str(data_path),
            message=f"Cannot parse CSV: {exc}",
            severity="error",
        ))
        return phase

    col_set = set(headers)
    missing_dims = [c for c in [entity_col, time_col] if c and c not in col_set]
    if missing_dims:
        phase.issues.append(_Issue(
            source="data file",
            location="columns",
            message=f"Entity/time columns missing from CSV: {missing_dims}",
            fix=f"Check data.entity_col and data.time_col in config.yaml.  "
                f"Available: {headers[:8]}{'…' if len(headers) > 8 else ''}",
            severity="error",
        ))

    needed = ([dep] if dep else []) + regressors
    missing_vars = [c for c in needed if c and c not in col_set]
    if missing_vars:
        phase.issues.append(_Issue(
            source="data file",
            location="columns",
            message=f"Analysis variables missing from CSV: {missing_vars}",
            fix="Add these columns to your data file, or fix the names in config.yaml.",
            severity="error",
        ))

    if entity_col in col_set and time_col in col_set:
        ei = headers.index(entity_col)
        ti = headers.index(time_col)
        keys = [(r[ei], r[ti]) for r in rows if len(r) > max(ei, ti)]
        dupe_count = len(keys) - len(set(keys))
        if dupe_count > 0:
            phase.issues.append(_Issue(
                source="data file",
                location=f"({entity_col}, {time_col})",
                message=f"{dupe_count} duplicate panel observations detected",
                fix="Check your data preparation script for duplicate rows.",
                severity="warning",
            ))

    return phase


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def _render_phase(phase: _PhaseResult, console: Console, verbose: bool = False) -> None:
    """Print a single validation phase."""
    icon = _ICONS["pass"] if phase.ok else _ICONS["fail"]
    has_issues = bool(phase.issues)

    console.print(f"  Phase: [bold]{escape(phase.name)}[/bold]")

    if not has_issues:
        console.print(f"    {icon} {escape(phase.name.lower())} passed")
        return

    # Summarise errors vs warnings
    errors = [i for i in phase.issues if i.severity == "error"]
    warnings = [i for i in phase.issues if i.severity != "error"]

    if errors:
        console.print(
            f"    {_ICONS['fail']} {len(errors)} error(s)"
            + (f", {len(warnings)} warning(s)" if warnings else "")
        )
    else:
        console.print(f"    {_ICONS['warn']} {len(warnings)} warning(s)")

    # Group by source file
    by_source: dict[str, list[_Issue]] = {}
    for issue in phase.issues:
        by_source.setdefault(issue.source, []).append(issue)

    for source, issues in by_source.items():
        console.print(f"\n      [bold]{escape(source)}[/bold]")
        for issue in issues:
            sev_icon = _ICONS["fail"] if issue.severity == "error" else _ICONS["warn"]
            loc = escape(f"[{issue.location}]") + " " if issue.location else ""
            console.print(f"        {sev_icon} {loc}{escape(issue.message)}")
            if issue.fix:
                console.print(f"           [dim]Fix: {escape(issue.fix)}[/dim]")
    console.print()


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def run_validate(
    config_path: Path,
    models_path: Path,
    outputs_path: Path,
    check_data: bool,
    console: Console,
    verbose: bool = False,
) -> int:
    """
    Run three-phase validation and render a report.

    Parameters
    ----------
    config_path, models_path, outputs_path:
        Paths to the three configuration files.
    check_data:
        If True, also validate the data file referenced in config.yaml.
    console:
        Rich console for output.
    verbose:
        If True, print passing checks as well as failures.

    Returns
    -------
    int
        0 if all checks passed (errors = 0, warnings allowed), 1 on errors.
    """
    console.print()
    console.print(
        f"[bold]EconFlow validate[/bold]  "
        f"[dim]{escape(str(config_path.parent))}[/dim]\n"
    )

    # --- Phase 1: Schema ---------------------------------------------------
    (
        phase1,
        project_cfg,
        models_cfg,
        outputs_cfg,
        raw_config,
        raw_models,
        raw_outputs,
    ) = _schema_validate(config_path, models_path, outputs_path)

    _render_phase(phase1, console, verbose)

    # Show per-file pass/fail for schema phase
    for label, obj in [
        ("config.yaml ", project_cfg),
        ("models.yaml ", models_cfg),
        ("outputs.yaml", outputs_cfg),
    ]:
        icon = _ICONS["pass"] if obj is not None else _ICONS["fail"]
        status = "schema valid" if obj is not None else "schema errors"
        console.print(f"    {icon} {label} — {status}")
    console.print()

    # --- Phase 2: Semantic -------------------------------------------------
    phase2 = _semantic_validate(
        project_cfg, models_cfg, outputs_cfg, raw_config, raw_models, raw_outputs
    )

    icon2 = _ICONS["pass"] if phase2.ok else _ICONS["fail"]
    if phase2.ok and not phase2.issues:
        console.print(f"    {icon2} semantic validation passed")
    else:
        n_e = phase2.n_errors
        n_w = phase2.n_warnings
        if n_e:
            console.print(f"    {icon2} semantic validation — {n_e} error(s), {n_w} warning(s)")
        else:
            console.print(f"    {_ICONS['warn']} semantic validation — {n_w} warning(s)")
        for issue in phase2.issues:
            sev_icon = _ICONS["fail"] if issue.severity == "error" else _ICONS["warn"]
            loc = escape(f"[{issue.location}]") + "  " if issue.location else ""
            console.print(f"      {sev_icon} {loc}{escape(issue.message)}")
            if issue.fix:
                console.print(f"        [dim]Fix: {escape(issue.fix)}[/dim]")
    console.print()

    # --- Phase 3: Cross-file -----------------------------------------------
    phase3 = _cross_file_validate(
        project_cfg, models_cfg, outputs_cfg, raw_config, raw_models, raw_outputs
    )

    icon3 = _ICONS["pass"] if phase3.ok else _ICONS["fail"]
    if phase3.ok and not phase3.issues:
        console.print(f"    {icon3} cross-file validation passed")
    else:
        n_e = phase3.n_errors
        n_w = phase3.n_warnings
        if n_e:
            console.print(f"    {icon3} cross-file validation — {n_e} error(s), {n_w} warning(s)")
        else:
            console.print(f"    {_ICONS['warn']} cross-file validation — {n_w} warning(s)")
        for issue in phase3.issues:
            sev_icon = _ICONS["fail"] if issue.severity == "error" else _ICONS["warn"]
            loc = escape(f"[{issue.location}]") + "  " if issue.location else ""
            console.print(f"      {sev_icon} {loc}{escape(issue.message)}")
            if issue.fix:
                console.print(f"        [dim]Fix: {escape(issue.fix)}[/dim]")
    console.print()

    # --- Phase 4: Data file (optional) ------------------------------------
    if check_data:
        phase4 = _data_validate(project_cfg, raw_config, config_path)
        icon4 = _ICONS["pass"] if phase4.ok else _ICONS["fail"]
        if phase4.ok and not phase4.issues:
            console.print(f"    {icon4} data file validation passed")
        else:
            n_e = phase4.n_errors
            n_w = phase4.n_warnings
            label = "data file validation"
            if n_e:
                console.print(f"    {icon4} {label} — {n_e} error(s), {n_w} warning(s)")
            else:
                console.print(f"    {_ICONS['warn']} {label} — {n_w} warning(s)")
            for issue in phase4.issues:
                sev_icon = _ICONS["fail"] if issue.severity == "error" else _ICONS["warn"]
                loc = escape(f"[{issue.location}]") + "  " if issue.location else ""
                console.print(f"      {sev_icon} {loc}{escape(issue.message)}")
                if issue.fix:
                    console.print(f"        [dim]Fix: {escape(issue.fix)}[/dim]")
        console.print()
    else:
        phase4 = _PhaseResult("Data file validation")

    # --- Summary -----------------------------------------------------------
    all_phases = [phase1, phase2, phase3, phase4]
    total_errors = sum(p.n_errors for p in all_phases)
    total_warnings = sum(p.n_warnings for p in all_phases)

    if total_errors == 0 and total_warnings == 0:
        console.print("[bold green]✔ All checks passed.[/bold green]\n")
    elif total_errors == 0:
        console.print(
            f"[bold yellow]⚠ Passed with {total_warnings} warning(s).[/bold yellow]\n"
        )
    else:
        console.print(
            f"[bold red]✘ {total_errors} error(s) · {total_warnings} warning(s).[/bold red]\n"
        )

    return 0 if total_errors == 0 else 1
