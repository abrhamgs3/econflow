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
import statsmodels.api as sm
import yaml
from linearmodels.panel import PanelOLS, PooledOLS

from econflow import __version__
from econflow.exceptions import EconFlowError, ModelSpecificationError
from econflow.logging import get_logger

log = get_logger(__name__)


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
# Estimation
# ---------------------------------------------------------------------------

def _run_model(panel_df: pd.DataFrame, spec: dict) -> object:
    """
    Estimate one model from its YAML specification dict.

    Supported estimators
    --------------------
    ``"OLS"``
        Pooled OLS via :class:`linearmodels.panel.PooledOLS`.
        Ignores entity and time effects.  Covariance type: robust.
    ``"FE"`` (default)
        Within estimator via :class:`linearmodels.panel.PanelOLS`.
        Respects ``entity_effects``, ``time_effects``, and ``cluster``.

    Parameters
    ----------
    panel_df:
        DataFrame with a (entity, time) MultiIndex.
    spec:
        Model specification dict as parsed from models.yaml.  Keys:

        - ``id`` (str) — unique model identifier
        - ``estimator`` (str) — ``"OLS"`` or ``"FE"``
        - ``dependent`` (str) — dependent variable column name
        - ``regressors`` (list[str]) — regressor column names
        - ``entity_effects`` (bool, default False)
        - ``time_effects`` (bool, default False)
        - ``cluster`` (str | None) — ``"entity"`` or ``"time"`` or None

    Returns
    -------
    linearmodels result object
    """
    estimator = spec.get("estimator", "FE").upper()
    model_id = spec.get("id", spec.get("dependent", "model"))
    dependent = spec["dependent"]
    regressors = list(spec["regressors"])
    entity_effects = spec.get("entity_effects", False)
    time_effects = spec.get("time_effects", False)
    cluster = spec.get("cluster", None)

    needed = [dependent] + regressors
    model_df = panel_df[needed].dropna()

    n_entities = model_df.index.get_level_values(0).nunique()
    log.info(
        "Estimating %-20s  estimator=%-3s  obs=%d  entities=%d  "
        "entity_fe=%s  time_fe=%s  cluster=%s",
        model_id, estimator, len(model_df), n_entities,
        entity_effects, time_effects, cluster,
    )

    y = model_df[dependent]
    X = sm.add_constant(model_df[regressors])

    try:
        if estimator == "OLS":
            # Use classic (unadjusted) SEs for pooled OLS — matches standard
            # textbook presentation and avoids overstating SE robustness.
            model = PooledOLS(y, X)
            result = model.fit(cov_type="unadjusted")
        else:
            model = PanelOLS(
                y,
                X,
                entity_effects=entity_effects,
                time_effects=time_effects,
                drop_absorbed=True,
            )
            if cluster == "entity":
                result = model.fit(cov_type="clustered", cluster_entity=True)
            elif cluster == "time":
                result = model.fit(cov_type="clustered", cluster_time=True)
            else:
                result = model.fit(cov_type="robust")

        # Quick sanity log
        for reg in regressors[:2]:
            if reg in result.params.index:
                log.info(
                    "    %-12s  coef=%+.4f  p=%.4f",
                    reg, result.params[reg], result.pvalues[reg],
                )

        return result

    except Exception as exc:
        raise ModelSpecificationError(
            f"Model '{model_id}' estimation failed: {exc}"
        ) from exc


# ---------------------------------------------------------------------------
# Table formatting
# ---------------------------------------------------------------------------

_STARS_THRESHOLDS = [(0.01, "***"), (0.05, "**"), (0.10, "*")]


def _stars(pval: float) -> str:
    for threshold, star in _STARS_THRESHOLDS:
        if pval < threshold:
            return star
    return ""


def _fmt_coef(val: float, pval: float) -> str:
    return f"{val:.4f}{_stars(pval)}"


def _fmt_se(val: float) -> str:
    return f"({val:.3f})"


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


def _build_comparison_table(
    results: dict,
    model_specs: list[dict],
    regressors: list[str],
    table_cfg: dict,
) -> pd.DataFrame:
    """
    Build a wide-format comparison table DataFrame.

    Rows: coefficient / SE for each regressor, then FE indicators, N, R² within.
    Columns: one per model in the order specified by ``comparison_table.models``.
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
                coef_row.append(_fmt_coef(res.params[reg], res.pvalues[reg]))
                se_row.append(_fmt_se(res.std_errors[reg]))
            else:
                coef_row.append("—")
                se_row.append("—")
        rows.append(coef_row)
        rows.append(se_row)

    # Fixed effects indicator rows
    entity_row: list = ["Firm FE"]
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

    # R² within — only meaningful for PanelOLS (within estimator).
    # PooledOLS exposes rsquared_within but it conflates within/between
    # variation; suppress it with em dash to avoid misinterpretation.
    r2_row: list = ["R² within"]
    id_to_spec = {s["id"]: s for s in model_specs}
    for mid in model_ids:
        spec = id_to_spec.get(mid, {})
        is_fe = spec.get("estimator", "FE").upper() != "OLS"
        if not is_fe:
            r2_row.append("—")
        else:
            val = getattr(results[mid], "rsquared_within", None)
            r2_row.append(_fmt_r2(val))
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
        return (
            s.replace("R² within", "$R^2$ within")
             .replace("***", "$^{***}$")
             .replace("**", "$^{**}$")
             .replace("*", "$^{*}$")
             .replace("—", "---")
        )

    lines = [
        "\\begin{table}[htbp]",
        "\\centering",
        f"\\caption{{{caption}}}",
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
        "\\end{table}",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")
    log.info("LaTeX table written: %s", path)


# ---------------------------------------------------------------------------
# Provenance
# ---------------------------------------------------------------------------

def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _record_provenance(
    config_path: Path,
    models_path: Path,
    outputs_path: Path,
    data_path: Path,
    model_ids: list[str],
    out_dir: Path,
) -> None:
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

def run_from_config(
    config_path: Path,
    models_path: Path,
    outputs_path: Path,
) -> None:
    """
    Execute the generic config-driven panel pipeline.

    Parameters
    ----------
    config_path:
        Path to ``config.yaml``.  Must contain ``data.path``,
        ``data.entity_col``, ``data.time_col``, ``variables.dependent``,
        and ``variables.regressors``.
    models_path:
        Path to ``models.yaml``.  Must contain a ``models`` list, each
        entry being a model specification dict.
    outputs_path:
        Path to ``outputs.yaml``.  Must contain ``outputs.base_dir`` and
        ``outputs.tables.comparison_table.filename``.
    """
    # ------------------------------------------------------------------ Load
    log.info("Reading configuration from %s", config_path)
    cfg = _load_yaml(config_path)
    models_cfg = _load_yaml(models_path)
    out_cfg = _load_yaml(outputs_path)

    data_cfg = cfg["data"]
    data_path = Path(data_cfg["path"])
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

    # Check for missing values in analysis columns
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
    for spec in model_specs:
        mid = spec["id"]
        results[mid] = _run_model(panel_df, spec)

    # --------------------------------------------------------------- [4/5] Export tables
    log.info("[4/5] Exporting tables")
    out_section = out_cfg["outputs"]
    base_dir = Path(out_section["base_dir"])
    tables_section = out_section["tables"]
    tables_dir = base_dir / "tables"
    table_filename = tables_section["comparison_table"]["filename"]
    formats = tables_section.get("formats", ["csv"])

    table_df = _build_comparison_table(
        results,
        model_specs,
        regressors,
        tables_section,
    )

    if "csv" in formats:
        _write_csv(table_df, tables_dir / f"{table_filename}.csv")
    if "latex" in formats:
        project_name = cfg.get("project", {}).get("name", "panel regression")
        _write_latex(
            table_df,
            tables_dir / f"{table_filename}.tex",
            regressors,
            caption=f"Panel regression results -- {project_name}",
        )

    # --------------------------------------------------------- [5/5] Record provenance
    log.info("[5/5] Recording provenance")
    _record_provenance(
        config_path, models_path, outputs_path,
        data_path,
        [s["id"] for s in model_specs],
        base_dir,
    )

    log.info("Pipeline complete.")
