"""
econflow.pipeline_generic — Config-driven pipeline for arbitrary panel datasets.

No column names are hardcoded.  All structure (entity column, time column,
dependent variable, regressors, model specifications, output directory) is
read from three YAML configuration files:

    config.yaml   — data paths and variable names
    models.yaml   — list of model specifications
    outputs.yaml  — output directory and table formatting

Usage
-----
    econflow run \\
        --config  examples/getting_started/config/config.yaml \\
        --models  examples/getting_started/config/models.yaml \\
        --outputs examples/getting_started/config/outputs.yaml

This module is the implementation for the issue
"Generalize the pipeline to arbitrary panel datasets".
"""

from __future__ import annotations

import hashlib
import json
import platform
import uuid
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from econflow import __version__
from econflow.core.exceptions import RegistryError
from econflow.estimation.dispatcher import EstimationDispatcher, PipelineContext
from econflow.exceptions import EconFlowError, ModelSpecificationError
from econflow.logging import get_logger

log = get_logger(__name__)

# ---------------------------------------------------------------------------
# Phase 6 diagnostic-label mapping
# ---------------------------------------------------------------------------
# Maps DiagnosticResult.diagnostic_id → the CSV ``diagnostic`` column label
# used since Phase 0.  The label values are frozen by the Architecture Freeze
# (§I-8: diagnostics.csv schema must not change).  Adding a new diagnostic
# requires a new entry here AND a schema migration document.
_DIAG_CSV_LABEL: dict[str, str] = {
    "vif":           "VIF (max)",
    "breusch_pagan": "Breusch-Pagan",
    "durbin_watson": "Serial Correlation (DW)",
}


# ---------------------------------------------------------------------------
# YAML loading
# ---------------------------------------------------------------------------

def _load_yaml(path: Path) -> dict:
    """Load a YAML file and return its contents as a dict."""
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


# ---------------------------------------------------------------------------
# Panel preparation
# ---------------------------------------------------------------------------

def _prepare_panel(
    df: pd.DataFrame,
    entity_col: str,
    time_col: str,
) -> pd.DataFrame:
    """
    Set a (entity, time) MultiIndex on *df* and sort.

    Parameters
    ----------
    df:
        Raw DataFrame loaded from CSV.
    entity_col:
        Column name for the entity dimension (e.g. ``"firm"``).
    time_col:
        Column name for the time dimension (e.g. ``"year"``).

    Returns
    -------
    pd.DataFrame
        A copy with a (entity_col, time_col) MultiIndex, sorted.
    """
    if not {entity_col, time_col}.issubset(df.columns):
        missing = {entity_col, time_col} - set(df.columns)
        raise EconFlowError(
            f"Data is missing required panel columns: {sorted(missing)}. "
            f"Available columns: {list(df.columns)}"
        )
    return df.set_index([entity_col, time_col]).sort_index()


# ---------------------------------------------------------------------------
# Table formatting
# ---------------------------------------------------------------------------

_STARS_THRESHOLDS = [(0.01, "***"), (0.05, "**"), (0.10, "*")]


def _stars(pval: float) -> str:
    for threshold, star in _STARS_THRESHOLDS:
        if pval < threshold:
            return star
    return ""


def _fmt_coef(val: float, pval: float, decimal_places: int = 4) -> str:
    return f"{val:.{decimal_places}f}{_stars(pval)}"


def _fmt_se(val: float, decimal_places: int = 4) -> str:
    return f"({val:.{decimal_places}f})"


def _fmt_r2(val: object) -> str:
    if val is None:
        return "—"  # em dash
    try:
        f = float(val)
        if np.isnan(f):
            return "—"
        return f"{f:.4f}"
    except (TypeError, ValueError):
        return "—"


def _write_diagnostics(
    results: dict,
    out_cfg: dict,
    outputs_path: Path,
) -> None:
    """
    Write ``outputs/tables/diagnostics.csv`` from pre-computed diagnostics.

    Phase 6 thin writer — reads
    :attr:`~econflow.estimation.result.EstimationResult.diagnostic_results`
    on each :class:`~econflow.estimation.result.EstimationResult` and writes
    one CSV row per recognised diagnostic.  Diagnostic values are produced by
    :func:`~econflow.estimation._diagnostics.compute_standard_diagnostics`
    inside each estimator's ``diagnostics()`` method; no re-computation is done
    here.

    CSV schema (unchanged from Phase 0):

    .. code-block:: text

        model_id, diagnostic, statistic, p_value, conclusion

    The ``diagnostic`` column uses the frozen labels defined in
    :data:`_DIAG_CSV_LABEL` (see Architecture Freeze §I-8).  Any
    :class:`~econflow.estimation.result.DiagnosticResult` with an unknown
    ``diagnostic_id`` or a ``None`` statistic is silently skipped, matching
    the historical behaviour of the Phase 0–5 inline implementation.
    """
    out_section = out_cfg.get("outputs", {})
    _raw_base_dir = Path(out_section.get("base_dir", "outputs"))
    if not _raw_base_dir.is_absolute():
        base_dir = (outputs_path.parent / _raw_base_dir).resolve()
    else:
        base_dir = _raw_base_dir
    diag_path = base_dir / "tables" / "diagnostics.csv"
    diag_path.parent.mkdir(parents=True, exist_ok=True)

    rows = []
    for mid, result in results.items():
        for diag in result.diagnostic_results:
            label = _DIAG_CSV_LABEL.get(diag.diagnostic_id)
            if label is None:
                log.debug(
                    "Skipping unknown diagnostic_id %r for model %s",
                    diag.diagnostic_id, mid,
                )
                continue
            if diag.statistic is None:
                # Degenerate / not-applicable result (e.g. VIF with < 2 regressors)
                log.debug(
                    "Skipping %r for model %s: statistic is None",
                    diag.diagnostic_id, mid,
                )
                continue
            rows.append({
                "model_id":   mid,
                "diagnostic": label,
                "statistic":  round(diag.statistic, 4),
                "p_value":    round(diag.pvalue, 4) if diag.pvalue is not None else None,
                "conclusion": diag.conclusion,
            })

    if rows:
        diag_df = pd.DataFrame(rows)
        diag_df.to_csv(diag_path, index=False)
        log.info("Diagnostics written: %s", diag_path)
    else:
        log.info("No diagnostics produced")


def _build_comparison_table(
    results: dict,
    model_specs: list[dict],
    regressors: list[str],
    table_cfg: dict,
    entity_col: str = "Entity",
    decimal_places: int = 4,
) -> pd.DataFrame:
    """
    Build a wide-format comparison table DataFrame from
    :class:`~econflow.estimation.result.EstimationResult` objects.

    Rows: coefficient / SE for each regressor, then FE indicators, N, R² within.
    Columns: one per model in the order specified by ``comparison_table.models``.

    R² within is read from ``extra["rsquared_within"]`` for FE estimators
    (stored by :class:`~econflow.estimation.fixed_effects.EntityFE` and
    :class:`~econflow.estimation.fixed_effects.TwoWayFE`) with a fallback to
    ``rsquared`` for any estimator that does not populate that key.
    Pooled OLS is suppressed with an em dash because its ``rsquared_within``
    conflates within/between variation.
    """
    model_ids = table_cfg.get("models", list(results.keys()))
    id_to_label = {s["id"]: s.get("label", s["id"]) for s in model_specs}
    col_names = [id_to_label.get(mid, mid) for mid in model_ids]

    rows: list[list] = []

    # Coefficient + SE rows for each regressor
    for reg in regressors:
        coef_row: list = [f"Coefficient: {reg}"]
        se_row: list = [f"SE: {reg}"]
        for mid in model_ids:
            res = results[mid]
            if reg in res.params.index:
                coef_row.append(
                    _fmt_coef(res.params[reg], res.pvalues[reg], decimal_places)
                )
                se_row.append(_fmt_se(res.std_err[reg], decimal_places))
            else:
                coef_row.append("—")
                se_row.append("—")
        rows.append(coef_row)
        rows.append(se_row)

    # Fixed effects indicator rows (use actual entity/time column names)
    entity_fe_label = f"{entity_col.capitalize()} FE"
    entity_row: list = [entity_fe_label]
    time_row: list = ["Year FE"]
    for mid in model_ids:
        spec = next(s for s in model_specs if s["id"] == mid)
        entity_row.append("Yes" if spec.get("entity_effects") else "No")
        time_row.append("Yes" if spec.get("time_effects") else "No")
    rows.append(entity_row)
    rows.append(time_row)

    # Observation count
    n_row: list = ["N"]
    for mid in model_ids:
        n_row.append(str(int(results[mid].nobs)))
    rows.append(n_row)

    # R² within — use estimator_id to detect OLS (suppress with em dash).
    # For FE estimators, use extra["rsquared_within"] (linearmodels within-R²)
    # rather than rsquared (overall R²), which differ for two-way FE models.
    r2_row: list = ["R² within"]
    for mid in model_ids:
        res = results[mid]
        is_ols = getattr(res, "estimator_id", "").lower() == "ols"
        if is_ols:
            r2_row.append("—")
        else:
            r2w = res.extra.get("rsquared_within", res.rsquared)
            r2_row.append(_fmt_r2(r2w))
    rows.append(r2_row)

    return pd.DataFrame(rows, columns=["Specification"] + col_names)


def _write_csv(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)
    log.info("CSV table written: %s", path)


def _write_latex(
    df: pd.DataFrame,
    path: Path,
    regressors: list[str],
    caption: str = "Panel regression results",
) -> None:
    """Write a booktabs-style LaTeX table."""
    path.parent.mkdir(parents=True, exist_ok=True)

    n_models = len(df.columns) - 1
    col_spec = "l" + "r" * n_models
    header_cells = [""] + [f"({i + 1}) {col}" for i, col in enumerate(df.columns[1:])]
    header = " & ".join(header_cells) + " \\\\"

    def _tex_escape(s: str) -> str:
        """Escape a table cell value for LaTeX.

        Significance stars are converted in a single regex pass to avoid
        the cascade problem: replacing '***' → '$^{***}$' then '**' on
        the already-replaced string would corrupt the output.
        """
        import re

        # Non-star substitutions first
        s = s.replace("R² within", "$R^2$ within").replace("—", "---")

        # Single-pass star replacement — longest match wins (re.sub is greedy)
        _STAR_MAP = {3: "$^{***}$", 2: "$^{**}$", 1: "$^{*}$"}

        def _star_sub(m: re.Match) -> str:
            n = min(len(m.group()), 3)
            return _STAR_MAP[n]

        return re.sub(r"\*+", _star_sub, s)

    _CAPTION_SPECIAL = [
        ("\\", r"\textbackslash{}"), ("&", r"\&"), ("%", r"\%"),
        ("$", r"\$"), ("#", r"\#"), ("_", r"\_"), ("{", r"\{"),
        ("}", r"\}"),
    ]
    caption_escaped = caption
    for _old, _new in _CAPTION_SPECIAL:
        caption_escaped = caption_escaped.replace(_old, _new)

    lines = [
        "\\begin{table}[htbp]",
        "\\centering",
        f"\\caption{{{caption_escaped}}}",
        "\\begin{threeparttable}",
        f"\\begin{{tabular}}{{{col_spec}}}",
        "\\toprule",
        header,
        "\\midrule",
    ]

    last_se = f"SE: {regressors[-1]}"
    for _, row in df.iterrows():
        spec = str(row["Specification"])
        vals = [_tex_escape(str(v)) for v in row.iloc[1:]]
        label = _tex_escape(spec)
        if spec.startswith("SE:"):
            label = ""  # SE row has no label
        line = " & ".join([label] + vals) + " \\\\"
        lines.append(line)
        if spec == last_se:
            lines.append("\\midrule")
        if spec == "Year FE":
            lines.append("\\midrule")

    lines += [
        "\\bottomrule",
        "\\end{tabular}",
        "\\begin{tablenotes}[flushleft]",
        "  \\footnotesize",
        r"  \item $^{*}p<0.10$, $^{**}p<0.05$, $^{***}p<0.01$",
        "\\end{tablenotes}",
        "\\end{threeparttable}",
        "\\end{table}",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")
    log.info("LaTeX table written: %s", path)


def _write_markdown(df, path):
    """Write a GitHub-Flavored Markdown table."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(df.to_markdown(index=False), encoding="utf-8")
    log.info("Markdown table written: %s", path)


def _write_html(df, path):
    """Write an HTML table."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(df.to_html(index=False, border=1), encoding="utf-8")
    log.info("HTML table written: %s", path)


def _write_json(df, path):
    """Write a JSON array of records."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(df.to_json(orient="records", indent=2), encoding="utf-8")
    log.info("JSON table written: %s", path)


# ---------------------------------------------------------------------------
# Provenance
# ---------------------------------------------------------------------------

def _sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _record_provenance(config_path, models_path, outputs_path, data_path, model_ids, out_dir):
    """Write run_metadata.json with SHA-256 hashes and run details."""
    meta = {
        "run_id": str(uuid.uuid4()),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "econflow_version": __version__,
        "python_version": platform.python_version(),
        "platform": platform.system(),
        "inputs": {
            "config": str(config_path),
            "models": str(models_path),
            "outputs": str(outputs_path),
            "data": str(data_path),
        },
        "input_hashes": {
            "config": _sha256(config_path),
            "data": _sha256(data_path),
        },
        "models_run": model_ids,
    }
    prov_dir = out_dir / "provenance"
    prov_dir.mkdir(parents=True, exist_ok=True)
    prov_file = prov_dir / "run_metadata.json"
    prov_file.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    log.info("Provenance written: %s", prov_file)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def run_from_config(config_path, models_path, outputs_path):
    """
    Execute the generic config-driven panel pipeline.

    Parameters
    ----------
    config_path:
        Path to ``config.yaml``.
    models_path:
        Path to ``models.yaml``.
    outputs_path:
        Path to ``outputs.yaml``.
    """
    # ------------------------------------------------------------------ Load
    log.info("Reading configuration from %s", config_path)
    cfg = _load_yaml(config_path)
    models_cfg = _load_yaml(models_path)
    out_cfg = _load_yaml(outputs_path)

    data_cfg = cfg["data"]
    _raw_data_path = Path(data_cfg["path"])
    if not _raw_data_path.is_absolute():
        data_path = (config_path.parent / _raw_data_path).resolve()
    else:
        data_path = _raw_data_path
    entity_col = data_cfg["entity_col"]
    time_col = data_cfg["time_col"]
    dependent = cfg["variables"]["dependent"]
    regressors = list(cfg["variables"]["regressors"])

    # ---------------------------------------------------------------- [1/5] Load data
    log.info("[1/5] Loading data: %s", data_path)
    df = pd.read_csv(data_path)
    n_entities = df[entity_col].nunique()
    n_periods = df[time_col].nunique()
    log.info(
        "      %d obs | %d %ss | %d %ss",
        len(df), n_entities, entity_col, n_periods, time_col,
    )

    required = data_cfg.get(
        "required_columns",
        [entity_col, time_col, dependent] + regressors,
    )
    missing_cols = [c for c in required if c not in df.columns]
    if missing_cols:
        raise EconFlowError(
            f"Data is missing required columns: {missing_cols}. "
            f"Available: {list(df.columns)}"
        )

    # ----------------------------------------------------------- [2/5] Validate panel
    log.info("[2/5] Validating panel structure")
    panel_df = _prepare_panel(df, entity_col, time_col)

    analysis_cols = [dependent] + regressors
    n_missing = panel_df[analysis_cols].isnull().sum().sum()
    if n_missing:
        log.warning("      %d missing values in analysis columns (rows will be dropped)", n_missing)
    else:
        log.info("      No missing values in analysis columns")

    # ---------------------------------------------------------------- [3/5] Run models
    log.info("[3/5] Running models")
    model_specs = models_cfg["models"]
    results: dict = {}

    context = PipelineContext(entity_col=entity_col, time_col=time_col)
    for spec in model_specs:
        mid = spec["id"]
        try:
            results[mid] = EstimationDispatcher.dispatch(spec, df, context)
        except NotImplementedError as exc:
            resolved = EstimationDispatcher.resolve_id(spec)
            raise ModelSpecificationError(
                f"Estimator '{spec.get('estimator')}' "
                f"(resolved: '{resolved}') is a stub and is not yet "
                "implemented.  Remove it from models.yaml or wait for "
                "the implementation in a future EconFlow release."
            ) from exc
        except RegistryError as exc:
            raise ModelSpecificationError(str(exc)) from exc

    # -------------------------------------------------------- [3.5/5] Write diagnostics
    log.info("[3.5/5] Writing diagnostics")
    _write_diagnostics(
        results=results,
        out_cfg=out_cfg,
        outputs_path=outputs_path,
    )

    # --------------------------------------------------------------- [4/5] Export tables
    log.info("[4/5] Exporting tables")
    out_section = out_cfg["outputs"]
    _raw_base_dir = Path(out_section["base_dir"])
    if not _raw_base_dir.is_absolute():
        base_dir = (outputs_path.parent / _raw_base_dir).resolve()
    else:
        base_dir = _raw_base_dir
    tables_section = out_section["tables"]
    tables_dir = base_dir / "tables"
    table_filename = tables_section["comparison_table"]["filename"]
    formats = tables_section.get("formats", ["csv"])
    decimal_places = int(tables_section.get("decimal_places", 4))

    table_df = _build_comparison_table(
        results,
        model_specs,
        regressors,
        tables_section,
        entity_col=entity_col,
        decimal_places=decimal_places,
    )

    _stem = (
        table_filename
        .removesuffix(".csv").removesuffix(".CSV")
        .removesuffix(".tex").removesuffix(".TEX")
        .removesuffix(".md").removesuffix(".html").removesuffix(".json")
    )

    if "csv" in formats:
        _write_csv(table_df, tables_dir / f"{_stem}.csv")
    if "latex" in formats:
        project_name = cfg.get("project", {}).get("name", "panel regression")
        _write_latex(
            table_df,
            tables_dir / f"{_stem}.tex",
            regressors,
            caption=f"Panel regression results -- {project_name}",
        )
    if "markdown" in formats:
        _write_markdown(table_df, tables_dir / f"{_stem}.md")
    if "html" in formats:
        _write_html(table_df, tables_dir / f"{_stem}.html")
    if "json" in formats:
        _write_json(table_df, tables_dir / f"{_stem}.json")

    # --------------------------------------------------------- [5/5] Record provenance
    log.info("[5/5] Recording provenance")
    _record_provenance(
        config_path, models_path, outputs_path,
        data_path,
        [s["id"] for s in model_specs],
        base_dir,
    )

    log.info("Pipeline complete.")
