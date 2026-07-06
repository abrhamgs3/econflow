"""
econflow.commands.validate — ``econflow validate`` command implementation.

This module is a *rendering layer* only.  All validation logic lives in
:mod:`econflow.config.validator`.  This module converts a
:class:`~econflow.config.validator.ValidationResult` into a human-readable
Rich terminal report.

Validation stages
-----------------
1. **YAML syntax**  — malformed YAML detected before any parsing.
2. **Schema**       — Pydantic v2 strict validation; unknown keys, wrong
   types, incorrect nesting, and missing required fields rejected here.
3. **Semantic**     — linter rules L-01 through L-13 check value
   relationships within a single file.
4. **Cross-file**   — consistency checks that span multiple files.

Optional stage 5 (``--data``):
   **Data file**    — verifies the CSV path, column presence, and uniqueness
   of panel keys.

CLI output format
-----------------
::

    EconFlow validate  config/

    Stage 1 · YAML syntax
      ✓ config.yaml
      ✓ models.yaml
      ✓ outputs.yaml

    Stage 2 · Schema validation
      ✓ config.yaml — schema valid
      ✗ models.yaml — schema errors

        [models → 0 → estimator]
          Value error: 'badname' is not a valid estimator
          Fix: Use one of the registered estimator IDs.

    ...

    ✘ 1 error(s) · 0 warning(s).

Exit codes
----------
0   All checks passed (errors = 0; warnings are printed but do not block)
1   One or more errors found
"""

from __future__ import annotations

from pathlib import Path

from rich.console import Console
from rich.markup import escape

# ---------------------------------------------------------------------------
# Re-export for backward compatibility with existing tests that import
# _SUPPORTED_ESTIMATORS from this module.
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
# Status icons (Rich markup)
# ---------------------------------------------------------------------------

_ICONS: dict[str, str] = {
    "pass": "[green]✓[/green]",
    "warn": "[yellow]⚠[/yellow]",
    "fail": "[red]✗[/red]",
    "skip": "[dim]-[/dim]",
}

_STAGE_LABELS: dict[str, str] = {
    "yaml_syntax": "YAML syntax",
    "schema":      "Schema validation",
    "semantic":    "Semantic validation",
    "cross_file":  "Cross-file validation",
    "data":        "Data file validation",
}


# ---------------------------------------------------------------------------
# Rendering helpers
# ---------------------------------------------------------------------------

def _render_stage(
    stage_key: str,
    issues: list,
    console: Console,
    verbose: bool,
) -> None:
    """Render one validation stage block."""
    label = _STAGE_LABELS.get(stage_key, stage_key)
    errors = [i for i in issues if i.severity == "error"]
    warnings = [i for i in issues if i.severity == "warning"]
    n_e, n_w = len(errors), len(warnings)

    if not issues:
        if verbose:
            console.print(f"  {_ICONS['pass']} {label} — passed")
        return

    if n_e:
        console.print(
            f"  {_ICONS['fail']} {label} — "
            f"{n_e} error(s)" + (f", {n_w} warning(s)" if n_w else "")
        )
    else:
        console.print(f"  {_ICONS['warn']} {label} — {n_w} warning(s)")

    # Group by source file
    by_source: dict[str, list] = {}
    for issue in issues:
        if issue.severity == "info":
            continue
        by_source.setdefault(issue.source, []).append(issue)

    for source, src_issues in by_source.items():
        console.print(f"\n    [bold]{escape(source)}[/bold]")
        for issue in src_issues:
            icon = _ICONS["fail"] if issue.severity == "error" else _ICONS["warn"]
            code = escape(f"[{issue.code}] ") if issue.code else ""
            loc = escape(f"[{issue.location}]  ") if issue.location else ""
            console.print(f"      {icon} {code}{loc}{escape(issue.message)}")
            if issue.fix:
                console.print(f"         [dim]Fix: {escape(issue.fix)}[/dim]")
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
    Run all validation stages and render a Rich report.

    Delegates validation to :class:`~econflow.config.validator.ConfigValidator`.
    This function only handles rendering.

    Parameters
    ----------
    config_path, models_path, outputs_path:
        Paths to the three YAML configuration files.
    check_data:
        If ``True``, run Stage 5 data file validation.
    console:
        Rich console for output.
    verbose:
        If ``True``, print passing stages as well as failures.

    Returns
    -------
    int
        0 if all checks passed (zero errors); 1 if any errors found.
    """
    from econflow.config.validator import ConfigValidator

    console.print()
    console.print(
        f"[bold]EconFlow validate[/bold]  "
        f"[dim]{escape(str(config_path.parent))}[/dim]\n"
    )

    validator = ConfigValidator()
    result = validator.validate(
        config_path, models_path, outputs_path, check_data=check_data
    )

    # --- Per-stage rendering -----------------------------------------------
    all_stage_keys = ["yaml_syntax", "schema", "semantic", "cross_file"]
    if check_data:
        all_stage_keys.append("data")

    for stage_key in all_stage_keys:
        stage_label = _STAGE_LABELS.get(stage_key, stage_key)
        stage_issues = result.by_stage(stage_key)  # type: ignore[arg-type]
        has_errors = any(i.severity == "error" for i in stage_issues)
        has_issues = bool(stage_issues)

        icon = (
            _ICONS["fail"] if has_errors
            else _ICONS["warn"] if has_issues
            else _ICONS["pass"]
        )

        if not has_issues and not verbose:
            # Compact: one line per passing stage
            console.print(f"  {icon} Stage: {stage_label}")
            continue

        if not has_issues and verbose:
            console.print(f"  {icon} Stage: {stage_label} — passed")
            continue

        console.print(f"\n  [bold]Stage: {escape(stage_label)}[/bold]")
        _render_stage(stage_key, stage_issues, console, verbose)

    console.print()

    # --- Per-file schema pass/fail summary ---------------------------------
    console.print("  [dim]Schema status:[/dim]")
    for label, obj in [
        ("config.yaml ", result.project_cfg),
        ("models.yaml ", result.models_cfg),
        ("outputs.yaml", result.outputs_cfg),
    ]:
        icon = _ICONS["pass"] if obj is not None else _ICONS["fail"]
        status = "valid" if obj is not None else "errors"
        console.print(f"    {icon} {label} — {status}")
    console.print()

    # --- Summary -----------------------------------------------------------
    n_errors = len(result.errors)
    n_warnings = len(result.warnings)

    if n_errors == 0 and n_warnings == 0:
        console.print("[bold green]✔ All checks passed.[/bold green]\n")
    elif n_errors == 0:
        console.print(
            f"[bold yellow]⚠ Passed with {n_warnings} warning(s).[/bold yellow]\n"
        )
    else:
        console.print(
            f"[bold red]✘ {n_errors} error(s) · {n_warnings} warning(s).[/bold red]\n"
        )

    return 0 if n_errors == 0 else 1
