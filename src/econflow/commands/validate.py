"""
econflow.commands.validate -- ``econflow validate`` command implementation.

This module is a *rendering layer* only.  All validation logic lives in
:mod:`econflow.config.validator`.  This module converts a
:class:`~econflow.config.validator.ValidationResult` into a human-readable
Rich terminal report.

Validation stages
-----------------
1. **YAML syntax**  -- malformed YAML detected before any parsing.
2. **Schema**       -- Pydantic v2 strict validation; unknown keys, wrong
   types, incorrect nesting, and missing required fields rejected here.
3. **Semantic**     -- linter rules L-01 through L-13 check value
   relationships within a single file.
4. **Cross-file**   -- consistency checks that span multiple files.

Optional stage 5 (``--data``):
   **Data file**    -- verifies the CSV path, column presence, and uniqueness
   of panel keys.

Exit codes
----------
0   All checks passed (errors = 0; warnings are printed but do not block)
1   One or more errors found
"""

from __future__ import annotations

from pathlib import Path

from rich.console import Console
from rich.markup import escape

from econflow.estimation.registry import list_estimators as _list_est


def _get_supported_estimators() -> frozenset[str]:
    try:
        import econflow.estimation  # noqa: F401
        return frozenset(e["id"] for e in _list_est() if e["status"] == "implemented")
    except Exception:
        return frozenset()


_SUPPORTED_ESTIMATORS: frozenset[str] = _get_supported_estimators()

_ICONS: dict[str, str] = {
    "pass": "[green]\u2713[/green]",
    "warn": "[yellow]\u26a0[/yellow]",
    "fail": "[red]\u2717[/red]",
    "skip": "[dim]-[/dim]",
}

_DOC_REF = "docs/reference/configuration.md"

_STAGE_DOC_ANCHOR: dict[str, str] = {
    "yaml_syntax": "#configyaml",
    "schema":      "#configyaml",
    "semantic":    "#configyaml",
    "cross_file":  "#modelsyaml",
    "data":        "#configyaml",
}

_STAGE_LABELS: dict[str, str] = {
    "yaml_syntax": "YAML syntax",
    "schema":      "Schema validation",
    "semantic":    "Semantic validation",
    "cross_file":  "Cross-file validation",
    "data":        "Data file validation",
}


def _render_stage(
    stage_key: str,
    issues: list,
    console: Console,
    verbose: bool,
) -> None:
    label = _STAGE_LABELS.get(stage_key, stage_key)
    errors = [i for i in issues if i.severity == "error"]
    warnings = [i for i in issues if i.severity == "warning"]
    n_e, n_w = len(errors), len(warnings)

    if not issues:
        if verbose:
            console.print(f"  {_ICONS['pass']} {label} -- passed")
        return

    if n_e:
        console.print(
            f"  {_ICONS['fail']} {label} -- "
            f"{n_e} error(s)" + (f", {n_w} warning(s)" if n_w else "")
        )
    else:
        console.print(f"  {_ICONS['warn']} {label} -- {n_w} warning(s)")

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


def run_validate(
    config_path: Path,
    models_path: Path,
    outputs_path: Path,
    check_data: bool,
    console: Console,
    verbose: bool = False,
) -> int:
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

    # -- Data preview (show even if no errors, so user knows the file was read) --
    if check_data and result.project_cfg is not None:
        try:
            import pandas as pd
            data_path = config_path.parent / result.project_cfg.data.path
            entity_col = result.project_cfg.data.entity_col
            time_col   = result.project_cfg.data.time_col
            df = pd.read_csv(data_path)
            n_obs      = len(df)
            n_entities = df[entity_col].nunique() if entity_col in df.columns else "?"
            n_periods  = df[time_col].nunique()   if time_col  in df.columns else "?"
            console.print(
                f"  [dim]Data loaded:[/dim] {n_obs:,} rows · "
                f"{n_entities} {escape(entity_col)}s · "
                f"{n_periods} {escape(time_col)}s"
            )
            console.print()
        except Exception:
            pass  # silently skip if anything goes wrong

    all_stage_keys = ["yaml_syntax", "schema", "semantic", "cross_file"]
    if check_data:
        all_stage_keys.append("data")

    for stage_key in all_stage_keys:
        stage_label = _STAGE_LABELS.get(stage_key, stage_key)
        stage_issues = result.by_stage(stage_key)
        has_errors = any(i.severity == "error" for i in stage_issues)
        has_issues = bool(stage_issues)

        icon = (
            _ICONS["fail"] if has_errors
            else _ICONS["warn"] if has_issues
            else _ICONS["pass"]
        )

        if not has_issues and not verbose:
            console.print(f"  {icon} Stage: {stage_label}")
            continue

        if not has_issues and verbose:
            console.print(f"  {icon} Stage: {stage_label} -- passed")
            continue

        console.print(f"\n  [bold]Stage: {escape(stage_label)}[/bold]")
        _render_stage(stage_key, stage_issues, console, verbose)

    console.print()

    console.print("  [dim]Schema status:[/dim]")
    for label, obj in [
        ("config.yaml ", result.project_cfg),
        ("models.yaml ", result.models_cfg),
        ("outputs.yaml", result.outputs_cfg),
    ]:
        icon = _ICONS["pass"] if obj is not None else _ICONS["fail"]
        status = "valid" if obj is not None else "errors"
        console.print(f"    {icon} {label} -- {status}")
    console.print()

    n_errors = len(result.errors)
    n_warnings = len(result.warnings)

    if n_errors == 0 and n_warnings == 0:
        console.print("[bold green]\u2714 All checks passed.[/bold green]\n")
    elif n_errors == 0:
        console.print(
            f"[bold yellow]\u26a0 Passed with {n_warnings} warning(s).[/bold yellow]\n"
        )
        console.print(
            f"  [dim]Reference: {_DOC_REF}  "
            f"(run 'econflow docs config' to regenerate)[/dim]\n"
        )
    else:
        console.print(
            f"[bold red]\u2718 {n_errors} error(s) \u00b7 {n_warnings} warning(s).[/bold red]\n"
        )
        console.print(
            f"  [dim]Reference: {_DOC_REF}  "
            f"(run 'econflow docs config' to view all options)[/dim]\n"
        )

    return 0 if n_errors == 0 else 1
