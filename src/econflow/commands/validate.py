"""
econflow.commands.validate — ``econflow validate`` command implementation.

Validates an EconFlow project's configuration files, directory structure,
variable declarations, and (optionally) the processed data file.

Checks performed
----------------
Config files
  [C-01]  config.yaml  is present and parseable YAML
  [C-02]  models.yaml  is present and parseable YAML
  [C-03]  outputs.yaml is present and parseable YAML

config.yaml schema
  [S-01]  data.path       is present
  [S-02]  data.entity_col is present
  [S-03]  data.time_col   is present
  [S-04]  variables.dependent  is present and non-empty
  [S-05]  variables.regressors is a non-empty list

models.yaml schema
  [M-01]  models list is present and non-empty
  [M-02]  each model has id, estimator, dependent, regressors
  [M-03]  no duplicate model IDs
  [M-04]  model estimators are from the supported set (OLS | FE)
  [M-05]  model dependents match variables.dependent in config.yaml

outputs.yaml schema
  [O-01]  outputs.base_dir is present
  [O-02]  outputs.tables.comparison_table.filename is present

Cross-file consistency
  [X-01]  model IDs referenced in outputs.models_order exist in models.yaml
  [X-02]  model regressors are a subset of variables.regressors (warn if not)

Data file (only when --data flag is set)
  [D-01]  data file exists
  [D-02]  data file is a valid CSV
  [D-03]  entity_col and time_col are present in the CSV
  [D-04]  dependent and regressors are present in the CSV
  [D-05]  no duplicate (entity, time) rows

Exit codes
----------
0   All checks passed (or only warnings)
1   One or more FAIL checks
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import yaml
from rich.console import Console
from rich.table import Table

# ---------------------------------------------------------------------------
# Result model
# ---------------------------------------------------------------------------

Status = Literal["pass", "warn", "fail", "skip"]


@dataclass
class CheckResult:
    """Outcome of a single validation check."""

    code: str
    name: str
    status: Status
    message: str
    detail: str = ""


@dataclass
class ValidationReport:
    """Aggregated results from all checks."""

    checks: list[CheckResult] = field(default_factory=list)

    # ------------------------------------------------------------------
    # Helpers

    def add(
        self,
        code: str,
        name: str,
        status: Status,
        message: str,
        detail: str = "",
    ) -> None:
        self.checks.append(CheckResult(code, name, status, message, detail))

    def passed(self, code: str) -> bool:
        """Return True if *code* has status 'pass'."""
        return any(c.code == code and c.status == "pass" for c in self.checks)

    @property
    def n_fail(self) -> int:
        return sum(1 for c in self.checks if c.status == "fail")

    @property
    def n_warn(self) -> int:
        return sum(1 for c in self.checks if c.status == "warn")

    @property
    def n_pass(self) -> int:
        return sum(1 for c in self.checks if c.status == "pass")

    @property
    def ok(self) -> bool:
        return self.n_fail == 0


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_STATUS_ICON = {
    "pass": "[bold green]✔[/bold green]",
    "warn": "[bold yellow]⚠[/bold yellow]",
    "fail": "[bold red]✘[/bold red]",
    "skip": "[dim]–[/dim]",
}

_SUPPORTED_ESTIMATORS = {"OLS", "FE"}


def _load_yaml_safe(path: Path) -> tuple[dict | None, str]:
    """Try to load a YAML file.  Returns (data, error_message)."""
    if not path.exists():
        return None, f"File not found: {path}"
    try:
        with path.open(encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if not isinstance(data, dict):
            return None, "YAML parsed but did not produce a mapping (dict)"
        return data, ""
    except yaml.YAMLError as exc:
        return None, f"YAML parse error: {exc}"


def _deep_get(data: dict, *keys: str) -> object:
    """Navigate nested dict with dot-notation keys; return None if missing."""
    obj = data
    for key in keys:
        if not isinstance(obj, dict):
            return None
        obj = obj.get(key)
    return obj


# ---------------------------------------------------------------------------
# Check suites
# ---------------------------------------------------------------------------

def _check_config_files(
    config_path: Path,
    models_path: Path,
    outputs_path: Path,
    report: ValidationReport,
) -> tuple[dict | None, dict | None, dict | None]:
    """Parse all three config files.  Returns (cfg, models_cfg, out_cfg)."""
    results = []
    for code, label, path in [
        ("C-01", "config.yaml  parseable", config_path),
        ("C-02", "models.yaml  parseable", models_path),
        ("C-03", "outputs.yaml parseable", outputs_path),
    ]:
        data, err = _load_yaml_safe(path)
        if data is not None:
            report.add(code, label, "pass", f"Loaded: {path}")
        else:
            report.add(code, label, "fail", err, f"Path: {path}")
        results.append(data)

    return tuple(results)  # type: ignore[return-value]


def _check_config_schema(cfg: dict, report: ValidationReport) -> None:
    """Validate required keys in config.yaml."""
    _req(report, "S-01", "data.path present",
         _deep_get(cfg, "data", "path") is not None,
         "Add `data.path: \"data/processed/panel.csv\"` to config.yaml")

    _req(report, "S-02", "data.entity_col present",
         _deep_get(cfg, "data", "entity_col") is not None,
         "Add `data.entity_col: \"entity\"` to config.yaml")

    _req(report, "S-03", "data.time_col present",
         _deep_get(cfg, "data", "time_col") is not None,
         "Add `data.time_col: \"time\"` to config.yaml")

    dep = _deep_get(cfg, "variables", "dependent")
    _req(report, "S-04", "variables.dependent present",
         dep is not None and dep != "",
         "Add `variables.dependent: \"outcome\"` to config.yaml")

    regressors = _deep_get(cfg, "variables", "regressors")
    _req(report, "S-05", "variables.regressors non-empty list",
         isinstance(regressors, list) and len(regressors) > 0,
         "Add at least one regressor under `variables.regressors:`")


def _check_models_schema(
    models_cfg: dict,
    cfg: dict,
    report: ValidationReport,
) -> list[dict]:
    """Validate models.yaml and return model list."""
    specs = models_cfg.get("models")
    if not isinstance(specs, list) or len(specs) == 0:
        report.add("M-01", "models list non-empty", "fail",
                   "models.yaml must contain a `models:` list with at least one entry")
        return []

    report.add("M-01", "models list non-empty", "pass",
               f"{len(specs)} model(s) defined")

    # Check each spec
    seen_ids: set[str] = set()
    for i, spec in enumerate(specs):
        mid = spec.get("id", f"[{i}]")
        prefix = f"Model '{mid}'"

        # Required fields
        for field_name in ("id", "estimator", "dependent", "regressors"):
            if field_name not in spec:
                report.add("M-02", f"{prefix}: field `{field_name}` present",
                           "fail", f"Add `{field_name}:` to model '{mid}'")

        # Estimator from supported set
        est = str(spec.get("estimator", "")).upper()
        if est and est not in _SUPPORTED_ESTIMATORS:
            report.add("M-04", f"{prefix}: estimator recognised",
                       "warn",
                       f"Estimator '{est}' not in generic pipeline set {_SUPPORTED_ESTIMATORS}. "
                       "Will fail at runtime unless a custom estimator is registered.")
        elif est:
            report.add("M-04", f"{prefix}: estimator recognised", "pass", est)

        # Duplicate IDs
        actual_id = spec.get("id")
        if actual_id is not None:
            if actual_id in seen_ids:
                report.add("M-03", f"Model ID '{actual_id}' unique", "fail",
                           f"Duplicate model ID '{actual_id}'.")
            else:
                seen_ids.add(actual_id)
                report.add("M-03", f"Model ID '{actual_id}' unique", "pass", "")

        # dependent matches config
        cfg_dep = _deep_get(cfg, "variables", "dependent")
        spec_dep = spec.get("dependent")
        if cfg_dep and spec_dep and spec_dep != cfg_dep:
            report.add("M-05", f"{prefix}: dependent matches config",
                       "warn",
                       f"Model dependent '{spec_dep}' differs from config.yaml "
                       f"variables.dependent '{cfg_dep}'.")

    return specs


def _check_outputs_schema(out_cfg: dict, report: ValidationReport) -> None:
    """Validate required keys in outputs.yaml."""
    base_dir = _deep_get(out_cfg, "outputs", "base_dir")
    _req(report, "O-01", "outputs.base_dir present",
         base_dir is not None,
         "Add `outputs.base_dir: \"outputs\"` to outputs.yaml")

    filename = _deep_get(out_cfg, "outputs", "tables", "comparison_table", "filename")
    _req(report, "O-02", "comparison_table.filename present",
         filename is not None,
         "Add `outputs.tables.comparison_table.filename:` to outputs.yaml")


def _check_cross_consistency(
    out_cfg: dict,
    specs: list[dict],
    cfg: dict,
    report: ValidationReport,
) -> None:
    """Cross-file checks."""
    model_ids = {s["id"] for s in specs if "id" in s}
    cfg_regressors = set(_deep_get(cfg, "variables", "regressors") or [])

    # Check models referenced in outputs.models exist
    out_models = _deep_get(out_cfg, "outputs", "tables", "comparison_table", "models") or []
    if isinstance(out_models, list) and out_models:
        missing = [m for m in out_models if m not in model_ids]
        if missing:
            report.add("X-01", "outputs model IDs exist in models.yaml",
                       "fail",
                       f"outputs.yaml references unknown model ID(s): {missing}")
        else:
            report.add("X-01", "outputs model IDs exist in models.yaml", "pass", "")

    # Check each model's regressors are in config regressors
    if cfg_regressors:
        for spec in specs:
            spec_regs = set(spec.get("regressors") or [])
            extra = spec_regs - cfg_regressors
            if extra:
                report.add("X-02", f"Model '{spec.get('id')}' regressors in config",
                           "warn",
                           f"Regressors {sorted(extra)} not listed in config.yaml "
                           f"variables.regressors. This is allowed but may indicate a typo.")


def _check_data_file(cfg: dict, report: ValidationReport) -> None:
    """Validate the data file (only when --data flag is set)."""
    data_path_str = _deep_get(cfg, "data", "path")
    if data_path_str is None:
        report.add("D-01", "data file path configured", "skip",
                   "data.path not set in config.yaml — skipping data checks")
        return

    data_path = Path(str(data_path_str))

    if not data_path.exists():
        report.add("D-01", "data file exists", "fail",
                   f"File not found: {data_path}",
                   "Run your data preparation script to generate it.")
        for code in ("D-02", "D-03", "D-04", "D-05"):
            report.add(code, code, "skip", "Skipped — data file missing")
        return

    report.add("D-01", "data file exists", "pass", str(data_path))

    # Parse CSV header
    try:
        with data_path.open(encoding="utf-8", newline="") as f:
            reader = csv.reader(f)
            headers = next(reader)
            rows = list(reader)
        report.add("D-02", "data file parseable CSV", "pass",
                   f"{len(rows):,} data rows, {len(headers)} columns")
    except Exception as exc:
        report.add("D-02", "data file parseable CSV", "fail", str(exc))
        for code in ("D-03", "D-04", "D-05"):
            report.add(code, code, "skip", "Skipped — CSV parse failed")
        return

    col_set = set(headers)

    # entity_col and time_col
    entity_col = str(_deep_get(cfg, "data", "entity_col") or "")
    time_col = str(_deep_get(cfg, "data", "time_col") or "")
    missing_dims = [c for c in [entity_col, time_col] if c and c not in col_set]
    if missing_dims:
        report.add("D-03", "entity/time cols present", "fail",
                   f"Missing columns: {missing_dims}",
                   f"Available columns: {headers[:10]}{'…' if len(headers) > 10 else ''}")
    else:
        report.add("D-03", "entity/time cols present", "pass",
                   f"'{entity_col}' and '{time_col}' found")

    # dependent + regressors
    dep = str(_deep_get(cfg, "variables", "dependent") or "")
    regressors = list(_deep_get(cfg, "variables", "regressors") or [])
    needed = ([dep] if dep else []) + regressors
    missing_vars = [c for c in needed if c and c not in col_set]
    if missing_vars:
        report.add("D-04", "analysis variables present", "fail",
                   f"Missing columns: {missing_vars}")
    else:
        report.add("D-04", "analysis variables present", "pass",
                   f"{len(needed)} variable(s) found in CSV")

    # Duplicate (entity, time) rows
    if entity_col in col_set and time_col in col_set:
        ei = headers.index(entity_col)
        ti = headers.index(time_col)
        keys = [(row[ei], row[ti]) for row in rows if len(row) > max(ei, ti)]
        duplicates = len(keys) - len(set(keys))
        if duplicates > 0:
            report.add("D-05", "no duplicate (entity, time) rows", "warn",
                       f"{duplicates} duplicate panel keys detected.",
                       "Duplicates will cause errors in linearmodels. "
                       "Check your data preparation script.")
        else:
            report.add("D-05", "no duplicate (entity, time) rows", "pass",
                       f"{len(keys):,} unique panel observations")


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------

def _render_report(report: ValidationReport, console: Console) -> None:
    """Print the validation report to *console*."""
    table = Table(
        show_header=True,
        header_style="bold",
        box=None,
        padding=(0, 2, 0, 0),
    )
    table.add_column("", width=2)   # icon
    table.add_column("Code", style="dim", width=6)
    table.add_column("Check")
    table.add_column("Message", style="dim")

    for c in report.checks:
        if c.status == "skip":
            continue
        icon = _STATUS_ICON[c.status]
        detail = f" — {c.detail}" if c.detail else ""
        table.add_row(icon, c.code, c.name, c.message + detail)

    console.print()
    console.print(table)
    console.print()


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def _req(
    report: ValidationReport,
    code: str,
    name: str,
    condition: bool,
    fix: str = "",
) -> None:
    """Add a pass/fail check based on *condition*."""
    if condition:
        report.add(code, name, "pass", "")
    else:
        report.add(code, name, "fail", fix)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def run_validate(
    config_path: Path,
    models_path: Path,
    outputs_path: Path,
    check_data: bool,
    console: Console,
) -> int:
    """
    Run all validation checks and render a report.

    Parameters
    ----------
    config_path, models_path, outputs_path:
        Paths to the three configuration files.
    check_data:
        If True, also validate the data file referenced in config.yaml.
    console:
        Rich console for output.

    Returns
    -------
    int
        0 if all checks passed (or only warnings), 1 if any check failed.
    """
    console.print()
    console.print("[bold]EconFlow validate[/bold]\n")

    report = ValidationReport()

    # ------------------------------------------------------------------ Parse YAML
    cfg, models_cfg, out_cfg = _check_config_files(
        config_path, models_path, outputs_path, report
    )

    # ------------------------------------------------------------------ Schema
    if cfg is not None:
        _check_config_schema(cfg, report)
    else:
        for code in ("S-01", "S-02", "S-03", "S-04", "S-05"):
            report.add(code, code, "skip", "Skipped — config.yaml could not be parsed")

    specs: list[dict] = []
    if models_cfg is not None and cfg is not None:
        specs = _check_models_schema(models_cfg, cfg, report)
    elif models_cfg is None:
        for code in ("M-01", "M-02", "M-03", "M-04", "M-05"):
            report.add(code, code, "skip", "Skipped — models.yaml could not be parsed")

    if out_cfg is not None:
        _check_outputs_schema(out_cfg, report)
    else:
        for code in ("O-01", "O-02"):
            report.add(code, code, "skip", "Skipped — outputs.yaml could not be parsed")

    # ------------------------------------------------------------------ Cross-file
    if cfg is not None and out_cfg is not None and specs:
        _check_cross_consistency(out_cfg, specs, cfg, report)

    # ------------------------------------------------------------------ Data file
    if check_data and cfg is not None:
        _check_data_file(cfg, report)
    elif check_data:
        report.add("D-01", "data checks", "skip",
                   "Skipped — config.yaml could not be parsed")

    # ------------------------------------------------------------------ Render
    _render_report(report, console)

    # Summary line
    n_fail = report.n_fail
    n_warn = report.n_warn
    n_pass = report.n_pass

    if n_fail == 0 and n_warn == 0:
        console.print(f"[bold green]✔ All {n_pass} checks passed.[/bold green]\n")
    elif n_fail == 0:
        console.print(
            f"[bold yellow]⚠ {n_pass} passed · {n_warn} warning(s) · 0 errors.[/bold yellow]\n"
        )
    else:
        console.print(
            f"[bold red]✘ {n_fail} error(s) · {n_warn} warning(s) · {n_pass} passed.[/bold red]\n"
        )

    return 0 if report.ok else 1
