"""
econflow.config.linter — Configuration linter for EconFlow YAML files.

Architecture Stabilization Milestone 4.

The linter runs *semantic* checks that go beyond JSON-schema validation:
field types and presence are verified by the Pydantic models in
:mod:`econflow.config.models`; the linter checks *relationships* between
values that Pydantic cannot express as field validators.

Lint rules
----------

.. list-table::
   :widths: 10 60 10
   :header-rows: 1

   * - Code
     - Description
     - Severity
   * - L-01
     - ``variables.dependent`` also appears in ``variables.regressors``
     - error
   * - L-02
     - ``variables.regressors`` contains duplicate entries
     - error
   * - L-03
     - ``sample.start_year >= sample.end_year``
     - error
   * - L-04
     - Unknown estimator string — suggests closest match
     - warning
   * - L-05
     - Model regressors not declared in ``variables.regressors``
     - warning
   * - L-06
     - ``outputs.base_dir`` is an absolute path
     - warning
   * - L-07
     - ``data.path`` has an unsupported file extension
     - warning
   * - L-08
     - ``project.version`` is not a valid semver string
     - warning
   * - L-09
     - Model dependent differs from ``variables.dependent``
     - info
   * - L-10
     - Model ``label`` is empty (falls back to ``id`` in output)
     - info

Usage
-----
::

    from econflow.config.linter import ConfigLinter
    from econflow.config.models import ProjectConfig, ModelsConfig, OutputsConfig

    linter = ConfigLinter()
    issues = linter.lint(project_cfg, models_cfg, outputs_cfg)
    for issue in issues:
        print(issue.severity, issue.code, issue.message)
        if issue.fix:
            print(" Fix:", issue.fix)
        if issue.example:
            print(" Example:", issue.example)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from difflib import get_close_matches
from pathlib import Path
from typing import Literal

# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

Severity = Literal["error", "warning", "info"]


@dataclass
class LintIssue:
    """A single linting finding."""

    code: str
    """Rule code, e.g. ``"L-01"``."""

    severity: Severity
    """``"error"``, ``"warning"``, or ``"info"``."""

    message: str
    """Plain-English description of the problem."""

    fix: str = ""
    """Actionable fix instruction."""

    example: str = ""
    """Concrete YAML snippet that would resolve the issue."""

    location: str = ""
    """File and key path where the issue was found, e.g. ``"models.yaml: model 'fe'``."""

    def __str__(self) -> str:
        parts = [f"[{self.code}] {self.severity.upper()}: {self.message}"]
        if self.location:
            parts.append(f"  Location : {self.location}")
        if self.fix:
            parts.append(f"  Fix      : {self.fix}")
        if self.example:
            parts.append(f"  Example  : {self.example}")
        return "\n".join(parts)


# ---------------------------------------------------------------------------
# Semver regex
# ---------------------------------------------------------------------------

_SEMVER_RE = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-((?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)"
    r"(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?"
    r"(?:\+([0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?$"
)

_SUPPORTED_EXTENSIONS = frozenset({".csv", ".parquet", ".tsv"})

# Canonical lower-case estimator IDs (kept in sync with registry at lint time)
_CANONICAL_ESTIMATORS: frozenset[str] = frozenset(
    {"ols", "fe", "twfe", "re", "fd", "iv", "gmm", "quantile"}
)

# Common aliases accepted by the validate command
_ESTIMATOR_ALIASES: dict[str, str] = {
    "OLS": "ols", "FE": "fe", "TWFE": "twfe",
    "RE": "re", "FD": "fd", "IV": "iv",
    "GMM": "gmm", "QUANTILE": "quantile",
    "PooledOLS": "ols", "EntityFE": "fe", "TwoWayFE": "twfe",
    "RandomEffects": "re", "FirstDifference": "fd",
}


def _resolve_estimator(raw: str) -> str | None:
    """Return the canonical estimator ID for *raw*, or None if not recognised."""
    if raw in _CANONICAL_ESTIMATORS:
        return raw
    if raw in _ESTIMATOR_ALIASES:
        return _ESTIMATOR_ALIASES[raw]
    # Try canonical lookup after lower-casing
    lower = raw.lower()
    if lower in _CANONICAL_ESTIMATORS:
        return lower
    return None


# ---------------------------------------------------------------------------
# Linter
# ---------------------------------------------------------------------------

class ConfigLinter:
    """
    Semantic linter for EconFlow configuration files.

    Accepts parsed Pydantic model instances and returns a list of
    :class:`LintIssue` objects.  The linter never raises; all findings are
    returned as issues.

    Parameters
    ----------
    live_estimator_ids:
        Override the set of known estimator IDs.  Defaults to the built-in
        set of 8 estimators.  Pass the result of
        ``{e["id"] for e in list_estimators()}`` to use the live registry.
    """

    def __init__(
        self,
        live_estimator_ids: frozenset[str] | None = None,
    ) -> None:
        self._estimator_ids = live_estimator_ids or _CANONICAL_ESTIMATORS

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def lint(
        self,
        project_cfg: object | None = None,
        models_cfg: object | None = None,
        outputs_cfg: object | None = None,
        raw_config: dict | None = None,
        raw_models: dict | None = None,
        raw_outputs: dict | None = None,
    ) -> list[LintIssue]:
        """
        Run all lint rules and return the findings.

        Accepts either typed Pydantic model instances (preferred) or raw
        dicts (fallback when Pydantic validation failed).  Either set may
        be ``None``; rules that require a specific input are skipped.

        Parameters
        ----------
        project_cfg:
            Parsed :class:`~econflow.config.models.ProjectConfig` or ``None``.
        models_cfg:
            Parsed :class:`~econflow.config.models.ModelsConfig` or ``None``.
        outputs_cfg:
            Parsed :class:`~econflow.config.models.OutputsConfig` or ``None``.
        raw_config / raw_models / raw_outputs:
            Fallback raw dicts (used when Pydantic parse failed).

        Returns
        -------
        list[LintIssue]
            All findings, ordered by severity (error → warning → info).
        """
        issues: list[LintIssue] = []

        issues.extend(self._lint_config(project_cfg, raw_config))
        issues.extend(self._lint_models(models_cfg, raw_models, project_cfg, raw_config))
        issues.extend(self._lint_outputs(outputs_cfg, raw_outputs))

        # Sort: errors first, then warnings, then info
        _order = {"error": 0, "warning": 1, "info": 2}
        return sorted(issues, key=lambda i: _order[i.severity])

    # ------------------------------------------------------------------
    # Config-specific rules
    # ------------------------------------------------------------------

    def _lint_config(
        self,
        cfg: object | None,
        raw: dict | None,
    ) -> list[LintIssue]:
        issues: list[LintIssue] = []

        # Resolve variables block
        dep: str | None = None
        regressors: list[str] = []
        sample_start: int | None = None
        sample_end: int | None = None
        version: str | None = None
        data_path: str | None = None

        if cfg is not None:
            try:
                dep = cfg.variables.dependent  # type: ignore[union-attr]
                regressors = list(cfg.variables.regressors or [])  # type: ignore[union-attr]
                sample_start = cfg.sample.start_year  # type: ignore[union-attr]
                sample_end = cfg.sample.end_year  # type: ignore[union-attr]
                version = cfg.project.version  # type: ignore[union-attr]
                data_path = cfg.data.path  # type: ignore[union-attr]
            except AttributeError:
                pass
        elif raw is not None:
            variables = raw.get("variables", {})
            dep = variables.get("dependent")
            regressors = list(variables.get("regressors") or [])
            sample = raw.get("sample", {})
            sample_start = sample.get("start_year")
            sample_end = sample.get("end_year")
            version = (raw.get("project") or {}).get("version")
            data_path = (raw.get("data") or {}).get("path")

        # L-01: dependent in regressors
        if dep and dep in regressors:
            issues.append(LintIssue(
                code="L-01",
                severity="error",
                message=f"variables.dependent '{dep}' also appears in variables.regressors.",
                fix=(
                    f"Remove '{dep}' from the regressors list.  The dependent "
                    "variable is never a regressor."
                ),
                example=(
                    f"variables:\n"
                    f"  dependent: \"{dep}\"\n"
                    f"  regressors:\n"
                    f"    - \"x1\"   # not '{dep}'"
                ),
                location="config.yaml: variables",
            ))

        # L-02: duplicate regressors
        seen: set[str] = set()
        dupes: list[str] = []
        for r in regressors:
            if r in seen:
                dupes.append(r)
            seen.add(r)
        if dupes:
            issues.append(LintIssue(
                code="L-02",
                severity="error",
                message=f"Duplicate entries in variables.regressors: {dupes}.",
                fix="Remove the duplicate regressor name(s) from the list.",
                location="config.yaml: variables.regressors",
            ))

        # L-03: start_year >= end_year (also caught by Pydantic validator, but
        # the Pydantic error message is less readable — emit linter version too)
        if sample_start is not None and sample_end is not None:
            if sample_start >= sample_end:
                issues.append(LintIssue(
                    code="L-03",
                    severity="error",
                    message=(
                        f"sample.start_year ({sample_start}) must be strictly "
                        f"less than sample.end_year ({sample_end})."
                    ),
                    fix="Set start_year to an earlier year than end_year.",
                    example=(
                        "sample:\n"
                        "  start_year: 2000\n"
                        "  end_year:   2020"
                    ),
                    location="config.yaml: sample",
                ))

        # L-07: data.path extension
        if data_path:
            ext = Path(str(data_path)).suffix.lower()
            if ext and ext not in _SUPPORTED_EXTENSIONS:
                issues.append(LintIssue(
                    code="L-07",
                    severity="warning",
                    message=(
                        f"data.path has extension '{ext}' which is not in the "
                        f"supported set {sorted(_SUPPORTED_EXTENSIONS)}."
                    ),
                    fix="Use a .csv or .parquet file.",
                    location=f"config.yaml: data.path = {data_path!r}",
                ))

        # L-08: version semver
        if version and not _SEMVER_RE.match(version):
            issues.append(LintIssue(
                code="L-08",
                severity="warning",
                message=f"project.version '{version}' is not a valid semver string.",
                fix="Use the MAJOR.MINOR.PATCH format, e.g. '1.0.0'.",
                example="project:\n  version: \"1.0.0\"",
                location="config.yaml: project.version",
            ))

        return issues

    # ------------------------------------------------------------------
    # Models-specific rules
    # ------------------------------------------------------------------

    def _lint_models(
        self,
        cfg: object | None,
        raw: dict | None,
        project_cfg: object | None,
        raw_config: dict | None,
    ) -> list[LintIssue]:
        issues: list[LintIssue] = []

        # Resolve config regressors + dependent for cross-file checks
        config_dep: str | None = None
        config_regressors: set[str] = set()
        if project_cfg is not None:
            try:
                config_dep = project_cfg.variables.dependent  # type: ignore[union-attr]
                config_regressors = set(project_cfg.variables.regressors or [])  # type: ignore[union-attr]
            except AttributeError:
                pass
        elif raw_config is not None:
            variables = raw_config.get("variables", {})
            config_dep = variables.get("dependent")
            config_regressors = set(variables.get("regressors") or [])

        # Resolve model specs
        specs: list[dict] = []
        if cfg is not None:
            try:
                specs = [
                    {
                        "id": m.id,
                        "estimator": m.estimator,
                        "dependent": m.dependent,
                        "regressors": list(m.regressors or []),
                        "label": getattr(m, "label", ""),
                    }
                    for m in cfg.models  # type: ignore[union-attr]
                ]
            except AttributeError:
                pass
        elif raw is not None:
            specs = [
                {
                    "id": s.get("id", ""),
                    "estimator": str(s.get("estimator", "")),
                    "dependent": s.get("dependent", ""),
                    "regressors": list(s.get("regressors") or []),
                    "label": s.get("label", ""),
                }
                for s in (raw.get("models") or [])
            ]

        all_estimators = (
            self._estimator_ids
            | set(_ESTIMATOR_ALIASES.keys())
            | {e.lower() for e in _ESTIMATOR_ALIASES}
        )

        for spec in specs:
            mid = spec["id"] or "(unknown)"
            loc = f"models.yaml: model '{mid}'"

            est_raw = spec["estimator"]
            resolved = _resolve_estimator(est_raw)

            # L-04: unknown estimator (with suggestion)
            if est_raw and resolved is None:
                suggestions = get_close_matches(
                    est_raw.lower(),
                    [e.lower() for e in self._estimator_ids],
                    n=2,
                    cutoff=0.5,
                )
                hint = ""
                if suggestions:
                    hint = f"  Did you mean: {', '.join(repr(s) for s in suggestions)}?"
                issues.append(LintIssue(
                    code="L-04",
                    severity="warning",
                    message=f"Unknown estimator '{est_raw}' in model '{mid}'.{hint}",
                    fix=(
                        "Use one of the registered estimator IDs.  "
                        "Run `econflow info` to list all available estimators."
                    ),
                    example=(
                        f"  estimator: \"fe\"  "
                        f"# valid IDs: {sorted(self._estimator_ids)}"
                    ),
                    location=loc,
                ))

            # L-05: model regressors not in config regressors
            if config_regressors:
                extra = set(spec["regressors"]) - config_regressors
                if extra:
                    issues.append(LintIssue(
                        code="L-05",
                        severity="warning",
                        message=(
                            f"Model '{mid}' uses regressor(s) {sorted(extra)} "
                            "not declared in config.yaml variables.regressors."
                        ),
                        fix=(
                            "Either add the variable(s) to config.yaml "
                            "variables.regressors, or check for a typo in the "
                            "model spec."
                        ),
                        location=loc,
                    ))

            # L-09: model dependent differs from config dependent
            if config_dep and spec["dependent"] and spec["dependent"] != config_dep:
                issues.append(LintIssue(
                    code="L-09",
                    severity="info",
                    message=(
                        f"Model '{mid}' dependent '{spec['dependent']}' differs "
                        f"from config.yaml variables.dependent '{config_dep}'."
                    ),
                    fix=(
                        "This is allowed for alternative-outcome robustness checks. "
                        "Ignore if intentional."
                    ),
                    location=loc,
                ))

            # L-10: empty label
            if not spec.get("label"):
                issues.append(LintIssue(
                    code="L-10",
                    severity="info",
                    message=f"Model '{mid}' has no label; will use id as display name.",
                    fix=f"Add `label: \"Human Readable Name\"` to model '{mid}'.",
                    location=loc,
                ))

        return issues

    # ------------------------------------------------------------------
    # Outputs-specific rules
    # ------------------------------------------------------------------

    def _lint_outputs(
        self,
        cfg: object | None,
        raw: dict | None,
    ) -> list[LintIssue]:
        issues: list[LintIssue] = []

        base_dir: str | None = None
        if cfg is not None:
            try:
                base_dir = cfg.outputs.base_dir  # type: ignore[union-attr]
            except AttributeError:
                pass
        elif raw is not None:
            base_dir = (raw.get("outputs") or {}).get("base_dir")

        # L-06: absolute outputs.base_dir
        if base_dir:
            p = Path(str(base_dir))
            if p.is_absolute():
                issues.append(LintIssue(
                    code="L-06",
                    severity="warning",
                    message=(
                        f"outputs.base_dir '{base_dir}' is an absolute path.  "
                        "This makes the project non-portable."
                    ),
                    fix="Use a relative path such as 'outputs' or '../results'.",
                    example="outputs:\n  base_dir: \"outputs\"",
                    location="outputs.yaml: outputs.base_dir",
                ))

        return issues
