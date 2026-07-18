"""
econflow.config.validator — Configuration correctness boundary for EconFlow.

This module is the *single source of truth* for all configuration validation.
It orchestrates four sequential stages:

1. **YAML syntax**  — :func:`_stage_yaml` uses PyYAML to detect malformed files.
2. **Schema**       — :func:`_stage_schema` runs Pydantic v2 strict validation;
   unknown keys, wrong types, and missing required fields are rejected here.
3. **Semantic**     — :func:`_stage_semantic` runs :class:`~econflow.config.linter.ConfigLinter`
   rules (L-01 through L-13) that cross-check values within a single file.
4. **Cross-file**   — :func:`_stage_cross_file` checks consistency *between*
   files (e.g. model IDs referenced in outputs.yaml must exist in models.yaml).

An optional fifth stage is available via ``check_data=True``:

5. **Data**         — :func:`_stage_data` verifies that the CSV referenced by
   ``data.path`` exists, is readable, and contains every column declared in
   ``config.yaml``.

Public API
----------
::

    from econflow.config.validator import ConfigValidator, ValidationResult, ConfigValidationIssue

    validator = ConfigValidator()

    # Non-raising: returns all issues regardless of severity
    result = validator.validate(config_path, models_path, outputs_path)
    if not result.ok:
        for issue in result.errors:
            print(issue)

    # Raising: raises ConfigValidationError if any errors found
    project_cfg, models_cfg, outputs_cfg = validator.validate_strict(
        config_path, models_path, outputs_path
    )

CLI integration
---------------
``econflow run`` calls :meth:`ConfigValidator.validate_strict` before touching
any output files.  ``econflow validate`` calls :meth:`ConfigValidator.validate`
and renders the full issue list.

The guarantee
-------------
EconFlow *never* silently accepts an invalid configuration.  The pipeline
cannot be entered without passing at least stages 1–4.  Execution only begins
after :meth:`ConfigValidator.validate_strict` returns successfully.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

import yaml

# ---------------------------------------------------------------------------
# Stage and severity literals
# ---------------------------------------------------------------------------

Stage = Literal["yaml_syntax", "schema", "semantic", "cross_file", "data"]
Severity = Literal["error", "warning", "info"]

# ---------------------------------------------------------------------------
# ConfigValidationIssue
# ---------------------------------------------------------------------------


@dataclass
class ConfigValidationIssue:
    """
    A single finding produced during configuration validation.

    Attributes
    ----------
    stage:
        Which validation stage produced this issue.
        One of ``"yaml_syntax"``, ``"schema"``, ``"semantic"``,
        ``"cross_file"``, ``"data"``.
    severity:
        ``"error"`` blocks execution; ``"warning"`` is informational.
    source:
        Which file the issue is in (e.g. ``"config.yaml"``).
    location:
        Human-readable field path inside the file
        (e.g. ``"variables → regressors"``).
    message:
        Plain-English problem description.
    fix:
        Actionable remedy instruction.  May be empty.
    code:
        Rule code (e.g. ``"L-01"``).  Empty for schema/YAML errors.
    """

    stage: Stage
    severity: Severity
    source: str
    location: str
    message: str
    fix: str = ""
    code: str = ""

    def __str__(self) -> str:
        tag = f"[{self.code}] " if self.code else ""
        loc = f" [{self.location}]" if self.location else ""
        fix = f"\n    Fix: {self.fix}" if self.fix else ""
        return f"{self.stage}/{self.severity} {tag}{self.source}{loc}: {self.message}{fix}"


# ---------------------------------------------------------------------------
# ValidationResult
# ---------------------------------------------------------------------------


@dataclass
class ValidationResult:
    """
    The outcome of a :class:`ConfigValidator.validate` call.

    Contains all issues found across all stages plus the successfully
    parsed config objects (``None`` if that file failed schema validation).

    Attributes
    ----------
    issues : list[ConfigValidationIssue]
        All findings, ordered by stage then severity.
    project_cfg, models_cfg, outputs_cfg:
        Parsed Pydantic model instances; ``None`` if validation failed.
    """

    issues: list[ConfigValidationIssue] = field(default_factory=list)
    project_cfg: Any | None = None    # ProjectConfig | None
    models_cfg: Any | None = None     # ModelsConfig | None
    outputs_cfg: Any | None = None    # OutputsConfig | None

    # raw dicts (used by rendering layer)
    _raw_config: dict | None = field(default=None, repr=False)
    _raw_models: dict | None = field(default=None, repr=False)
    _raw_outputs: dict | None = field(default=None, repr=False)

    @property
    def ok(self) -> bool:
        """True if there are no *error*-severity issues."""
        return not any(i.severity == "error" for i in self.issues)

    @property
    def errors(self) -> list[ConfigValidationIssue]:
        """All error-severity issues."""
        return [i for i in self.issues if i.severity == "error"]

    @property
    def warnings(self) -> list[ConfigValidationIssue]:
        """All warning-severity issues."""
        return [i for i in self.issues if i.severity == "warning"]

    @property
    def infos(self) -> list[ConfigValidationIssue]:
        """All info-severity issues."""
        return [i for i in self.issues if i.severity == "info"]

    def by_stage(self, stage: Stage) -> list[ConfigValidationIssue]:
        """Return issues filtered to *stage*."""
        return [i for i in self.issues if i.stage == stage]

    def by_source(self, source: str) -> list[ConfigValidationIssue]:
        """Return issues filtered to *source* filename."""
        return [i for i in self.issues if i.source == source]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _pydantic_loc_str(loc: tuple) -> str:
    """Convert a Pydantic error location tuple to a human-readable key path."""
    parts: list[str] = []
    for part in loc:
        if isinstance(part, int):
            parts.append(f"[{part}]")
        else:
            parts.append(str(part))
    return " → ".join(parts)


def _pydantic_fix(source: str, loc: str, msg: str, err_dict: dict) -> str:
    """Generate a concrete fix hint from a Pydantic error dict."""
    etype = err_dict.get("type", "")
    last_key = loc.split(" → ")[-1].strip("[]")

    if etype == "missing":
        return f"Add the required field `{last_key}:` to {source}."
    if etype == "string_type":
        return f"`{loc}` must be a string — wrap the value in quotes."
    if etype in ("int_type", "int_parsing"):
        return f"`{loc}` must be an integer (no quotes)."
    if etype == "bool_type":
        return f"`{loc}` must be true or false (no quotes)."
    if etype in ("list_type", "too_short"):
        return f"`{loc}` must be a non-empty list."
    if etype == "extra_forbidden":
        return (
            f"Unknown key `{last_key}` in {source}. "
            "Remove it or run `econflow docs config` for the full schema."
        )
    if etype == "literal_error":
        expected = err_dict.get("ctx", {}).get("expected", "")
        return f"`{loc}` must be one of: {expected}."
    if "value_error" in etype or "assertion_error" in etype:
        return f"Check the value at `{loc}` in {source}: {msg}."
    return f"Check `{loc}` in {source}."


# ---------------------------------------------------------------------------
# Stage 1 — YAML syntax
# ---------------------------------------------------------------------------

def _stage_yaml(
    config_path: Path,
    models_path: Path,
    outputs_path: Path,
) -> tuple[list[ConfigValidationIssue], dict | None, dict | None, dict | None]:
    """
    Load and parse all three YAML files.

    Returns a list of issues plus the raw dicts (None on failure).
    This stage never raises; syntax errors are collected as issues.
    """
    issues: list[ConfigValidationIssue] = []
    raws: list[dict | None] = []

    for label, path in [
        ("config.yaml", config_path),
        ("models.yaml", models_path),
        ("outputs.yaml", outputs_path),
    ]:
        if not path.exists():
            issues.append(ConfigValidationIssue(
                stage="yaml_syntax",
                severity="error",
                source=label,
                location="(file)",
                message=f"File not found: {path}",
                fix=(
                    f"Create {label} in the config directory, or pass the "
                    "correct path with --config / --models / --outputs."
                ),
            ))
            raws.append(None)
            continue

        try:
            with path.open(encoding="utf-8") as fh:
                raw = yaml.safe_load(fh)
            if raw is None:
                raw = {}
            if not isinstance(raw, dict):
                issues.append(ConfigValidationIssue(
                    stage="yaml_syntax",
                    severity="error",
                    source=label,
                    location="(root)",
                    message=(
                        f"Expected a YAML mapping (dictionary) at the top level, "
                        f"got {type(raw).__name__}."
                    ),
                    fix=f"Make sure {label} starts with a key: value pair, not a list.",
                ))
                raws.append(None)
            else:
                raws.append(raw)
        except yaml.YAMLError as exc:
            # Extract line number from YAMLError if available
            loc = "(YAML parse error)"
            if hasattr(exc, "problem_mark") and exc.problem_mark is not None:  # type: ignore[union-attr]
                mark = exc.problem_mark  # type: ignore[union-attr]
                loc = f"line {mark.line + 1}, column {mark.column + 1}"
            issues.append(ConfigValidationIssue(
                stage="yaml_syntax",
                severity="error",
                source=label,
                location=loc,
                message=f"YAML syntax error: {exc}",
                fix=(
                    "Common causes: wrong indentation, missing colon after a key, "
                    "unquoted special characters (: { } [ ] # & * ? | > ' \" %)."
                ),
            ))
            raws.append(None)

    raw_config, raw_models, raw_outputs = raws
    return issues, raw_config, raw_models, raw_outputs


# ---------------------------------------------------------------------------
# Stage 2 — Pydantic schema
# ---------------------------------------------------------------------------

def _stage_schema(
    raw_config: dict | None,
    raw_models: dict | None,
    raw_outputs: dict | None,
) -> tuple[list[ConfigValidationIssue], Any, Any, Any]:
    """
    Validate raw dicts against Pydantic v2 models.

    Returns issues plus parsed config objects (None if validation failed).
    Unknown keys trigger ``extra_forbidden`` errors because all top-level
    models use ``model_config = ConfigDict(extra="forbid")``.
    """
    from econflow.config.models import ModelsConfig, OutputsConfig, ProjectConfig

    try:
        from pydantic import ValidationError
    except ImportError:
        ValidationError = Exception  # type: ignore[misc,assignment]

    issues: list[ConfigValidationIssue] = []
    results = []

    for label, raw, model_class in [
        ("config.yaml", raw_config, ProjectConfig),
        ("models.yaml", raw_models, ModelsConfig),
        ("outputs.yaml", raw_outputs, OutputsConfig),
    ]:
        if raw is None:
            results.append(None)
            continue
        try:
            obj = model_class.model_validate(raw)
            results.append(obj)
        except ValidationError as exc:
            results.append(None)
            for e in exc.errors():
                loc = _pydantic_loc_str(e.get("loc", ()))
                msg = e.get("msg", "")
                fix = _pydantic_fix(label, loc, msg, e)
                issues.append(ConfigValidationIssue(
                    stage="schema",
                    severity="error",
                    source=label,
                    location=loc,
                    message=msg,
                    fix=fix,
                ))

    project_cfg, models_cfg, outputs_cfg = results
    return issues, project_cfg, models_cfg, outputs_cfg


# ---------------------------------------------------------------------------
# Stage 3 — Semantic (ConfigLinter)
# ---------------------------------------------------------------------------

def _stage_semantic(
    project_cfg: Any,
    models_cfg: Any,
    outputs_cfg: Any,
    raw_config: dict | None,
    raw_models: dict | None,
    raw_outputs: dict | None,
    *,
    live_estimator_ids: frozenset[str] | None = None,
) -> list[ConfigValidationIssue]:
    """Run ConfigLinter rules L-01 through L-14 and map results to ConfigValidationIssue.

    Parameters
    ----------
    live_estimator_ids:
        Forwarded to :class:`~econflow.config.linter.ConfigLinter`.  When
        ``None`` (the default), the linter uses the live registry for
        estimator validation.  Pass a frozenset to override (test isolation).
    """
    from econflow.config.linter import ConfigLinter

    linter = ConfigLinter(live_estimator_ids=live_estimator_ids)
    lint_issues = linter.lint(
        project_cfg=project_cfg,
        models_cfg=models_cfg,
        outputs_cfg=outputs_cfg,
        raw_config=raw_config,
        raw_models=raw_models,
        raw_outputs=raw_outputs,
    )

    issues: list[ConfigValidationIssue] = []
    for li in lint_issues:
        sev: Severity = li.severity if li.severity in ("error", "warning", "info") else "warning"
        source = li.location.split(":")[0].strip() if ":" in li.location else "config"
        issues.append(ConfigValidationIssue(
            stage="semantic",
            severity=sev,
            source=source,
            location=li.location,
            message=li.message,
            fix=li.fix,
            code=li.code,
        ))
    return issues


# ---------------------------------------------------------------------------
# Stage 4 — Cross-file consistency
# ---------------------------------------------------------------------------

def _stage_cross_file(
    project_cfg: Any,
    models_cfg: Any,
    outputs_cfg: Any,
    raw_config: dict | None,
    raw_models: dict | None,
    raw_outputs: dict | None,
) -> list[ConfigValidationIssue]:
    """
    Verify relationships that span multiple files.

    Checks:
    X-01  Model IDs referenced in outputs.tables.comparison_table.models
          must exist in models.yaml.
    X-02  Model regressors that are not in config.yaml variables.regressors
          (cross-file echo of L-05 — surfaces as error here because missing
          variables will cause a KeyError at runtime).
    X-03  Model dependent variable not in config.yaml variables.regressors
          or variables.dependent (info — may be intentional for robustness).
    """
    issues: list[ConfigValidationIssue] = []

    # --- collect model IDs -------------------------------------------------
    model_ids: list[str] = []
    if models_cfg is not None:
        try:
            model_ids = [m.id for m in models_cfg.models]
        except AttributeError:
            pass
    elif raw_models:
        model_ids = [s.get("id", "") for s in (raw_models.get("models") or [])]

    # --- collect outputs comparison table model refs -----------------------
    output_refs: list[str] = []
    if outputs_cfg is not None:
        try:
            output_refs = list(outputs_cfg.outputs.tables.comparison_table.models or [])
        except AttributeError:
            pass
    elif raw_outputs:
        ct = (
            (raw_outputs.get("outputs") or {})
            .get("tables", {})
            .get("comparison_table", {})
        )
        output_refs = list(ct.get("models") or [])

    # X-01
    if output_refs:
        id_set = set(model_ids)
        missing = [mid for mid in output_refs if mid not in id_set]
        if missing:
            issues.append(ConfigValidationIssue(
                stage="cross_file",
                severity="error",
                source="outputs.yaml",
                location="outputs.tables.comparison_table.models",
                message=f"References unknown model ID(s): {missing}",
                fix=(
                    f"Add model(s) {missing} to models.yaml, or remove them "
                    "from outputs.tables.comparison_table.models."
                ),
                code="X-01",
            ))

    # --- collect config regressors ----------------------------------------
    cfg_regressors: set[str] = set()
    if project_cfg is not None:
        try:
            cfg_regressors = set(project_cfg.variables.regressors or [])
        except AttributeError:
            pass
    elif raw_config:
        v = raw_config.get("variables", {})
        cfg_regressors = set(v.get("regressors") or [])
    # X-02: model regressors not in config regressors (hard error — will
    # fail at runtime when pipeline tries to select the column)
    if cfg_regressors and models_cfg is not None:
        try:
            for m in models_cfg.models:
                extra = set(m.regressors or []) - cfg_regressors
                if extra:
                    issues.append(ConfigValidationIssue(
                        stage="cross_file",
                        severity="error",
                        source="models.yaml",
                        location=f"models → {m.id} → regressors",
                        message=(
                            f"Model '{m.id}' uses variable(s) {sorted(extra)} "
                            "that are not declared in config.yaml "
                            "variables.regressors."
                        ),
                        fix=(
                            f"Add {sorted(extra)} to config.yaml "
                            "variables.regressors, or correct the typo "
                            "in models.yaml."
                        ),
                        code="X-02",
                    ))
        except AttributeError:
            pass

    return issues


# ---------------------------------------------------------------------------
# Stage 5 — Data file (optional)
# ---------------------------------------------------------------------------

def _stage_data(
    project_cfg: Any,
    raw_config: dict | None,
    config_path: Path,
) -> list[ConfigValidationIssue]:
    """
    Verify that the CSV file referenced by ``data.path`` exists and contains
    every column declared in ``config.yaml``.

    This stage is *optional*; it is skipped if the data file does not exist
    yet (a warning is emitted instead of an error in that case).
    """
    issues: list[ConfigValidationIssue] = []

    # Extract field values from typed or raw config
    if project_cfg is not None:
        try:
            data_path_str: str | None = project_cfg.data.path
            entity_col: str = project_cfg.data.entity_col
            time_col: str = project_cfg.data.time_col
            dep: str = project_cfg.variables.dependent
            regressors: list[str] = list(project_cfg.variables.regressors or [])
            instruments: list[str] = list(
                getattr(project_cfg.variables, "instruments", None) or []
            )
            controls: list[str] = list(
                getattr(project_cfg.variables, "controls", None) or []
            )
        except AttributeError:
            return issues
    elif raw_config:
        v = raw_config.get("variables", {})
        data_cfg = raw_config.get("data", {})
        data_path_str = data_cfg.get("path")
        entity_col = str(data_cfg.get("entity_col") or "")
        time_col = str(data_cfg.get("time_col") or "")
        dep = str(v.get("dependent") or "")
        regressors = list(v.get("regressors") or [])
        instruments = list(v.get("instruments") or [])
        controls = list(v.get("controls") or [])
    else:
        return issues

    if not data_path_str:
        issues.append(ConfigValidationIssue(
            stage="data",
            severity="warning",
            source="config.yaml",
            location="data.path",
            message="data.path is not set — cannot validate data file.",
            fix="Set data.path to the location of your panel CSV.",
        ))
        return issues

    raw_p = Path(str(data_path_str))
    data_path = (
        (config_path.parent / raw_p).resolve()
        if not raw_p.is_absolute()
        else raw_p
    )

    if not data_path.exists():
        issues.append(ConfigValidationIssue(
            stage="data",
            severity="error",
            source="data file",
            location=str(data_path),
            message=f"Data file not found: {data_path}",
            fix=(
                "Run your data preparation script to generate the file, "
                "or check the path in config.yaml data.path."
            ),
        ))
        return issues

    # Parse CSV header only
    try:
        with data_path.open(encoding="utf-8", newline="") as fh:
            reader = csv.reader(fh)
            headers = next(reader, [])
            rows = list(reader)
    except Exception as exc:
        issues.append(ConfigValidationIssue(
            stage="data",
            severity="error",
            source="data file",
            location=str(data_path),
            message=f"Cannot parse CSV: {exc}",
            fix="Check the file is a valid comma-separated CSV with a header row.",
        ))
        return issues

    col_set = set(headers)

    # D-01: entity and time dimension columns
    missing_dims = [c for c in [entity_col, time_col] if c and c not in col_set]
    if missing_dims:
        issues.append(ConfigValidationIssue(
            stage="data",
            severity="error",
            source="data file",
            location="columns",
            message=f"Entity/time columns missing from CSV: {missing_dims}",
            fix=(
                f"config.yaml data.entity_col='{entity_col}' and "
                f"data.time_col='{time_col}' must be column headers in the CSV.  "
                f"Available columns: {headers[:8]}{'…' if len(headers) > 8 else ''}"
            ),
            code="D-01",
        ))

    # D-02: analysis variables
    needed = ([dep] if dep else []) + regressors + instruments + controls
    missing_vars = [c for c in needed if c and c not in col_set]
    if missing_vars:
        issues.append(ConfigValidationIssue(
            stage="data",
            severity="error",
            source="data file",
            location="columns",
            message=f"Analysis variables missing from CSV: {missing_vars}",
            fix=(
                "Add the missing columns to your data file, "
                "or correct the names in config.yaml variables."
            ),
            code="D-02",
        ))

    # D-03: duplicate panel keys
    if entity_col in col_set and time_col in col_set and rows:
        ei = headers.index(entity_col)
        ti = headers.index(time_col)
        keys = [
            (r[ei], r[ti])
            for r in rows
            if len(r) > max(ei, ti)
        ]
        n_dupes = len(keys) - len(set(keys))
        if n_dupes > 0:
            issues.append(ConfigValidationIssue(
                stage="data",
                severity="warning",
                source="data file",
                location=f"({entity_col}, {time_col})",
                message=(
                    f"{n_dupes} duplicate panel observation(s) found. "
                    "Panel estimators require unique (entity, time) pairs."
                ),
                fix=(
                    "Check your data preparation script for merge or "
                    "aggregation bugs that produce duplicate rows."
                ),
                code="D-03",
            ))

    return issues


# ---------------------------------------------------------------------------
# ConfigValidator — public class
# ---------------------------------------------------------------------------

_SEVERITY_ORDER: dict[str, int] = {"error": 0, "warning": 1, "info": 2}
_STAGE_ORDER: dict[str, int] = {
    "yaml_syntax": 0,
    "schema": 1,
    "semantic": 2,
    "cross_file": 3,
    "data": 4,
}


class ConfigValidator:
    """
    Orchestrates all four (optionally five) validation stages for EconFlow
    configuration files.

    The validator is stateless and reusable.  Instantiate once and call
    :meth:`validate` or :meth:`validate_strict` as many times as needed.

    Parameters
    ----------
    live_estimator_ids:
        Optional override for the set of known estimator IDs used by the
        linter's L-04 rule.  Defaults to the built-in set (ols, fe, twfe,
        re, fd, iv).

    Examples
    --------
    Non-raising API::

        validator = ConfigValidator()
        result = validator.validate(config_path, models_path, outputs_path)
        if not result.ok:
            for issue in result.errors:
                print(issue)

    Raising API (used by the pipeline)::

        project_cfg, models_cfg, outputs_cfg = validator.validate_strict(
            config_path, models_path, outputs_path, check_data=True
        )
    """

    def __init__(
        self,
        live_estimator_ids: frozenset[str] | None = None,
    ) -> None:
        self._estimator_ids = live_estimator_ids

    # ------------------------------------------------------------------
    # Public methods
    # ------------------------------------------------------------------

    def validate(
        self,
        config_path: Path,
        models_path: Path,
        outputs_path: Path,
        *,
        check_data: bool = False,
    ) -> ValidationResult:
        """
        Run all validation stages and return a :class:`ValidationResult`.

        This method *never raises* (unless an unexpected internal error
        occurs).  All findings are returned as :class:`ConfigValidationIssue`
        objects in the result.

        Parameters
        ----------
        config_path, models_path, outputs_path:
            Absolute or relative paths to the three YAML configuration files.
        check_data:
            If ``True``, also run Stage 5 (data file validation).  The data
            file not existing causes a *warning*, not an error.

        Returns
        -------
        ValidationResult
        """
        config_path = Path(config_path)
        models_path = Path(models_path)
        outputs_path = Path(outputs_path)

        all_issues: list[ConfigValidationIssue] = []

        # Stage 1 — YAML syntax
        yaml_issues, raw_config, raw_models, raw_outputs = _stage_yaml(
            config_path, models_path, outputs_path
        )
        all_issues.extend(yaml_issues)

        # Stage 2 — Schema (Pydantic)
        schema_issues, project_cfg, models_cfg, outputs_cfg = _stage_schema(
            raw_config, raw_models, raw_outputs
        )
        all_issues.extend(schema_issues)

        # Stage 3 — Semantic (linter)
        sem_issues = _stage_semantic(
            project_cfg, models_cfg, outputs_cfg,
            raw_config, raw_models, raw_outputs,
            live_estimator_ids=self._estimator_ids,
        )
        all_issues.extend(sem_issues)

        # Stage 4 — Cross-file
        cross_issues = _stage_cross_file(
            project_cfg, models_cfg, outputs_cfg,
            raw_config, raw_models, raw_outputs,
        )
        all_issues.extend(cross_issues)

        # Stage 5 — Data (optional)
        if check_data:
            data_issues = _stage_data(project_cfg, raw_config, config_path)
            all_issues.extend(data_issues)

        # Sort: stage order first, then severity within stage
        all_issues.sort(key=lambda i: (
            _STAGE_ORDER.get(i.stage, 99),
            _SEVERITY_ORDER.get(i.severity, 99),
        ))

        return ValidationResult(
            issues=all_issues,
            project_cfg=project_cfg,
            models_cfg=models_cfg,
            outputs_cfg=outputs_cfg,
            _raw_config=raw_config,
            _raw_models=raw_models,
            _raw_outputs=raw_outputs,
        )

    def validate_strict(
        self,
        config_path: Path,
        models_path: Path,
        outputs_path: Path,
        *,
        check_data: bool = False,
    ) -> tuple[Any, Any, Any]:
        """
        Run all validation stages and raise :class:`ConfigValidationError`
        if any errors are found.

        This is the method called by ``econflow run`` before executing the
        pipeline.  It enforces the ``load → validate → execute`` flow.

        Parameters
        ----------
        config_path, models_path, outputs_path:
            Paths to the three configuration files.
        check_data:
            If ``True``, Stage 5 data validation is also run.  Missing data
            file emits a *warning* (not an error) so that validate_strict can
            succeed when the data file has not yet been generated.

        Returns
        -------
        tuple[ProjectConfig, ModelsConfig, OutputsConfig]
            The parsed configuration objects, ready for use by the pipeline.

        Raises
        ------
        ConfigValidationError
            If any *error*-severity issue was found.
        """
        from econflow.core.exceptions import ConfigValidationError

        result = self.validate(
            config_path, models_path, outputs_path, check_data=check_data
        )
        if not result.ok:
            raise ConfigValidationError(result.issues, config_path=config_path)
        return result.project_cfg, result.models_cfg, result.outputs_cfg


# ---------------------------------------------------------------------------
# Backward-compatibility alias (deprecated — will be removed in v2.0)
# ---------------------------------------------------------------------------

#: Deprecated alias for :class:`ConfigValidationIssue`.
#: Use ``ConfigValidationIssue`` in all new code.
ValidationIssue = ConfigValidationIssue
