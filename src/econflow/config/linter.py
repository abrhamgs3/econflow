"""
econflow.config.linter — Configuration linter for EconFlow YAML files.

Architecture Stabilization Milestone 4 | Phase 4 (registry-driven validation).

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
     - Unknown estimator — not found in the live registry; suggests closest
       registered ID and provides plugin registration guidance
     - warning
   * - L-04b
     - Estimator is registered with ``status="stub"`` — present in the registry
       but raises ``NotImplementedError`` at runtime
     - error
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
   * - L-11
     - IV estimator with empty or missing instruments list
     - error
   * - L-12
     - TWFE estimator but ``entity_effects`` and ``time_effects`` are both False
     - warning
   * - L-13
     - ``outputs.tables.formats`` contains an unrecognised renderer ID
     - warning
   * - L-14
     - ``cluster`` value is not one of ``"entity"``, ``"time"``, or ``""``
       (empty); the pipeline does not silently fall back to entity clustering
     - error

Phase 4 note
------------
Rules L-04 and L-04b no longer compare against a hard-coded frozenset of
estimator names.  Instead they call
:func:`~econflow.estimation.dispatcher.EstimationDispatcher.resolve_id` and
then :func:`~econflow.estimation.registry.get_estimator` to check whether the
ID is in the **live registry** at validation time.  This means:

* Plugin estimators registered via ``[project.entry-points."econflow.plugins"]``
  are automatically accepted.
* Stub estimators are detected via the ``status`` field in registry metadata
  (``status="stub"``) rather than a second hardcoded frozenset.
* Error messages list the currently registered estimators, not a hardcoded
  list.

If the estimation package is unavailable at validation time (e.g. in a CI
environment where only the config dependencies are installed), the linter
silently skips the L-04/L-04b checks rather than crashing.

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
from dataclasses import dataclass
from difflib import get_close_matches
from pathlib import Path
from typing import Literal

# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

Severity = Literal["error", "warning", "info"]


@dataclass
class LintIssue:
    """A single linting finding emitted by :class:`ConfigLinter`.

    Instances are collected into :attr:`ConfigLinter.issues` and displayed
    by ``econflow validate`` with the actionable ``fix`` hint.

    Attributes
    ----------
    code : str
        Rule code, e.g. ``"L-01"``.
    severity : Severity
        ``"error"``, ``"warning"``, or ``"info"``.
    message : str
        Plain-English description of the problem.
    fix : str
        Actionable fix instruction shown to the user.
    """

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

#: Supported renderer IDs for L-13
_SUPPORTED_FORMATS: frozenset[str] = frozenset(
    {"csv", "latex", "markdown", "html", "json"}
)

# ---------------------------------------------------------------------------
# Phase 4 — registry-driven estimator validation
# ---------------------------------------------------------------------------

#: Valid values for the ``cluster`` field (L-14).
#: ``"entity"`` and ``"time"`` are the two clustering dimensions accepted by
#: :func:`~econflow.estimation.dispatcher._translate_cov`; empty string means
#: no clustering.  Any other value is an error — the dispatcher does NOT
#: silently fall back to entity clustering.
_VALID_CLUSTER_VALUES: frozenset[str] = frozenset({"entity", "time", ""})

#: Guidance shown in L-04 warnings so users know how to register plugins.
_PLUGIN_REGISTRATION_HINT: str = (
    "If you installed a plugin estimator, ensure it declares itself in "
    "pyproject.toml under [project.entry-points.\"econflow.plugins\"].  "
    "Run `econflow info` to list all currently registered estimators."
)


def _fmt_estimator_error(
    raw: str,
    suggestions: list[str],
    available: list[str],
) -> str:
    """Build a human-readable L-04 error string.

    Parameters
    ----------
    raw:
        The unrecognised estimator string from the YAML file.
    suggestions:
        Closest registered estimator IDs (from :func:`difflib.get_close_matches`).
    available:
        All estimator IDs currently in the live registry.

    Returns
    -------
    str
        Ready-to-embed message fragment (no trailing newline).
    """
    parts: list[str] = [f"Unknown estimator '{raw}'."]
    if suggestions:
        parts.append(
            f"Did you mean: {', '.join(repr(s) for s in suggestions)}?"
        )
    parts.append(f"Registered estimators: {available}.")
    return "  ".join(parts)


def _resolve_via_registry(
    spec: dict,
    live_estimator_ids: frozenset[str] | None,
) -> tuple[str, bool, str | None]:
    """
    Resolve the estimator in *spec* against the live registry.

    This is the single entry point for L-04 / L-04b logic.  All estimation
    imports are deferred inside this function so the linter remains importable
    even when the estimation package is not installed.

    Parameters
    ----------
    spec:
        Model spec dict from ``_lint_models()`` — must contain at minimum
        ``"estimator"``, and optionally ``"entity_effects"`` / ``"time_effects"``
        for the FE adapter in
        :meth:`~econflow.estimation.dispatcher.EstimationDispatcher.resolve_id`.
    live_estimator_ids:
        If not ``None``, bypass the live registry entirely and check the
        estimator against this set instead.  Intended for test isolation only:
        pass ``frozenset({"ols", "fe", ...})`` to avoid importing the
        estimation package in a unit test.

    Returns
    -------
    tuple[str, bool, str | None]
        ``(resolved_id, is_stub, error_message)``

        * ``resolved_id`` — the dispatcher-resolved (lowercased) ID; best-effort
          if the estimator is unknown.
        * ``is_stub`` — ``True`` if the estimator is registered with
          ``status="stub"`` in :data:`~econflow.estimation.registry._REGISTRY_META`.
        * ``error_message`` — ``None`` when the estimator is valid and
          implemented; a non-empty string when it is unknown (L-04) or when
          the check could not be performed (caller should treat as valid).
    """
    raw = str(spec.get("estimator", "")).strip()

    # ------------------------------------------------------------------
    # Override path: test-isolation via live_estimator_ids
    # ------------------------------------------------------------------
    if live_estimator_ids is not None:
        lower = raw.lower()
        if lower in live_estimator_ids:
            return lower, False, None
        available = sorted(live_estimator_ids)
        suggestions = get_close_matches(lower, available, n=2, cutoff=0.4)
        return lower, False, _fmt_estimator_error(raw, suggestions, available)

    # ------------------------------------------------------------------
    # Live registry path (default)
    # ------------------------------------------------------------------
    # Lazy imports: keep the linter importable without the estimation package.
    try:
        import warnings as _warnings  # noqa: PLC0415
        from econflow.estimation.dispatcher import (  # noqa: PLC0415
            EstimationDispatcher as _Dispatcher,
        )
        from econflow.estimation.registry import (  # noqa: PLC0415
            RegistryError as _RegistryError,
            get_estimator as _get_estimator,
            list_estimators as _list_estimators,
        )
    except ImportError:
        # Estimation package unavailable — skip estimator validation silently.
        return raw.lower(), False, None

    # Resolve via dispatcher (handles case normalisation and the FE adapter).
    try:
        with _warnings.catch_warnings():
            _warnings.simplefilter("ignore", DeprecationWarning)
            resolved = _Dispatcher.resolve_id(spec)
    except Exception:  # noqa: BLE001
        resolved = raw.lower()

    # Check whether the resolved ID is in the registry.
    try:
        _get_estimator(resolved)
    except _RegistryError:
        available = sorted(e["id"] for e in _list_estimators())
        suggestions = get_close_matches(raw.lower(), available, n=2, cutoff=0.4)
        return resolved, False, _fmt_estimator_error(raw, suggestions, available)
    except Exception:  # noqa: BLE001
        # Unexpected error — don't crash the linter; treat as valid.
        return resolved, False, None

    # Valid estimator — check stub status via registry metadata.
    try:
        meta_map = {e["id"]: e for e in _list_estimators()}
        is_stub = meta_map.get(resolved, {}).get("status") == "stub"
    except Exception:  # noqa: BLE001
        is_stub = False

    return resolved, is_stub, None


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
        Override for estimator ID validation.  When ``None`` (the default),
        L-04 and L-04b resolve estimators through the live registry via
        :func:`~econflow.estimation.dispatcher.EstimationDispatcher.resolve_id`
        and :func:`~econflow.estimation.registry.get_estimator`.

        Pass a ``frozenset[str]`` to bypass the live registry entirely —
        useful in unit tests that need to isolate from the estimation package.
        The set should contain only lowercase registry keys (e.g.
        ``frozenset({"ols", "fe", "twfe"})``).
    """

    def __init__(
        self,
        live_estimator_ids: frozenset[str] | None = None,
    ) -> None:
        # None means "use the live registry"; a frozenset is a test override.
        self._estimator_ids = live_estimator_ids

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
            try:
                _ss, _se = int(sample_start), int(sample_end)
            except (TypeError, ValueError):
                _ss, _se = None, None
            if _ss is not None and _ss >= _se:
                issues.append(LintIssue(
                    code="L-03",
                    severity="error",
                    message=(
                        f"sample.start_year ({_ss}) must be strictly "
                        f"less than sample.end_year ({_se})."
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
                        "entity_effects": getattr(m, "entity_effects", False),
                        "time_effects": getattr(m, "time_effects", False),
                        "instruments": list(getattr(m, "instruments", None) or []),
                        "cluster": str(getattr(m, "cluster", "") or ""),
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
                    "entity_effects": bool(s.get("entity_effects", False)),
                    "time_effects": bool(s.get("time_effects", False)),
                    "instruments": list(s.get("instruments") or []),
                    "cluster": str(s.get("cluster", "") or ""),
                }
                for s in (raw.get("models") or [])
            ]

        for spec in specs:
            mid = spec["id"] or "(unknown)"
            loc = f"models.yaml: model '{mid}'"

            est_raw = spec["estimator"]

            # ----------------------------------------------------------
            # L-04 / L-04b — estimator resolution via live registry
            # ----------------------------------------------------------
            resolved_id: str = est_raw.lower() if est_raw else ""
            if est_raw:
                resolved_id, is_stub, err_msg = _resolve_via_registry(
                    spec, self._estimator_ids
                )

                if err_msg is not None:
                    # L-04: estimator not found in the live registry
                    issues.append(LintIssue(
                        code="L-04",
                        severity="warning",
                        message=f"Model '{mid}': {err_msg}",
                        fix=_PLUGIN_REGISTRATION_HINT,
                        example='  estimator: "fe"  # example of a valid built-in estimator',
                        location=loc,
                    ))

                elif is_stub:
                    # L-04b: estimator registered with status="stub"
                    issues.append(LintIssue(
                        code="L-04b",
                        severity="error",
                        message=(
                            f"Estimator '{est_raw}' (resolved: '{resolved_id}') "
                            "is registered but not yet implemented — it will raise "
                            "NotImplementedError at runtime."
                        ),
                        fix=(
                            "Use an implemented estimator.  "
                            "Run `econflow info` to list all available estimators."
                        ),
                        example='  estimator: "fe"  # two-way fixed effects',
                        location=loc,
                    ))

            # ----------------------------------------------------------
            # L-14 — cluster value must be "entity", "time", or ""
            # ----------------------------------------------------------
            cluster_val = spec.get("cluster", "")
            if cluster_val and cluster_val not in _VALID_CLUSTER_VALUES:
                _cluster_candidates = sorted(_VALID_CLUSTER_VALUES - {""})
                suggestions = get_close_matches(
                    cluster_val, _cluster_candidates, n=1, cutoff=0.5
                )
                hint = f"  Did you mean: '{suggestions[0]}'?" if suggestions else ""
                issues.append(LintIssue(
                    code="L-14",
                    severity="error",
                    message=(
                        f"Model '{mid}': invalid cluster value '{cluster_val}'.{hint}  "
                        f"Valid values: {_cluster_candidates} or '' (no clustering)."
                    ),
                    fix=(
                        "Set cluster to 'entity' (cluster by cross-sectional unit), "
                        "'time' (cluster by time period), or remove the field for "
                        "heteroskedasticity-robust standard errors.  "
                        "The pipeline does not silently fall back to entity clustering."
                    ),
                    example=(
                        "  cluster: entity   # cluster by cross-sectional unit\n"
                        "  # cluster: time   # cluster by time period\n"
                        "  # cluster: \"\"    # no clustering (HC robust SEs)"
                    ),
                    location=f"{loc}: cluster",
                ))

            # ----------------------------------------------------------
            # L-05 — model regressors not in config regressors
            # ----------------------------------------------------------
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

            # ----------------------------------------------------------
            # L-09 — model dependent differs from config dependent
            # ----------------------------------------------------------
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

            # ----------------------------------------------------------
            # L-10 — empty label
            # ----------------------------------------------------------
            if not spec.get("label"):
                issues.append(LintIssue(
                    code="L-10",
                    severity="info",
                    message=f"Model '{mid}' has no label; will use id as display name.",
                    fix=f"Add `label: \"Human Readable Name\"` to model '{mid}'.",
                    location=loc,
                ))

            # ----------------------------------------------------------
            # L-11 — IV estimator with no instruments
            # ----------------------------------------------------------
            est_lower = (est_raw or "").lower()
            _iv_aliases = {"iv", "iv2sls", "2sls"}
            if est_lower in _iv_aliases or resolved_id == "iv":
                instruments = spec.get("instruments") or []
                if not instruments:
                    # Also check if instruments exist at config level
                    cfg_instruments: list[str] = []
                    if project_cfg is not None:
                        try:
                            cfg_instruments = list(
                                getattr(project_cfg.variables, "instruments", None) or []  # type: ignore[union-attr]
                            )
                        except AttributeError:
                            pass
                    elif raw_config is not None:
                        cfg_instruments = list(
                            (raw_config.get("variables") or {}).get("instruments") or []
                        )
                    if not cfg_instruments:
                        issues.append(LintIssue(
                            code="L-11",
                            severity="error",
                            message=(
                                f"Model '{mid}' uses estimator 'iv' but no instruments "
                                "are defined.  IV/2SLS requires excluded instruments."
                            ),
                            fix=(
                                "Add an `instruments:` list to config.yaml "
                                "variables block, or add `instruments:` to this "
                                "model spec."
                            ),
                            example=(
                                "variables:\n"
                                "  instruments:\n"
                                "    - distance_to_coast\n"
                                "    - colonial_origin"
                            ),
                            location=loc,
                        ))

            # ----------------------------------------------------------
            # L-12 — TWFE but effects flags not set
            # ----------------------------------------------------------
            _twfe_aliases = {"twfe", "two_way_fe", "twfe_robust"}
            if est_lower in _twfe_aliases or resolved_id == "twfe":
                entity_fx = spec.get("entity_effects", False)
                time_fx = spec.get("time_effects", False)
                if not entity_fx and not time_fx:
                    issues.append(LintIssue(
                        code="L-12",
                        severity="warning",
                        message=(
                            f"Model '{mid}' uses TWFE but both entity_effects and "
                            "time_effects are False (or absent).  Two-way FE will "
                            "not absorb either dimension."
                        ),
                        fix=(
                            "Set entity_effects: true and time_effects: true for "
                            "two-way fixed effects estimation."
                        ),
                        example=(
                            "  entity_effects: true\n"
                            "  time_effects: true"
                        ),
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

        # L-13: unknown renderer format ID
        formats: list[str] = []
        if cfg is not None:
            try:
                formats = list(cfg.outputs.tables.formats or [])  # type: ignore[union-attr]
            except AttributeError:
                pass
        elif raw is not None:
            formats = list(
                ((raw.get("outputs") or {}).get("tables") or {}).get("formats") or []
            )
        for fmt in formats:
            if fmt not in _SUPPORTED_FORMATS:
                suggestions = get_close_matches(
                    fmt.lower(),
                    sorted(_SUPPORTED_FORMATS),
                    n=1,
                    cutoff=0.5,
                )
                hint = f"  Did you mean: '{suggestions[0]}'?" if suggestions else ""
                issues.append(LintIssue(
                    code="L-13",
                    severity="warning",
                    message=(
                        f"outputs.tables.formats contains unknown renderer '{fmt}'.{hint}"
                    ),
                    fix=(
                        f"Use one of the supported renderers: "
                        f"{sorted(_SUPPORTED_FORMATS)}.  "
                        "Unknown formats are silently skipped."
                    ),
                    location=f"outputs.yaml: outputs.tables.formats['{fmt}']",
                ))

        return issues
