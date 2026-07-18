"""
Sample-selection and coverage diagnostics.

These functions compare the sub-sample of observations with non-missing values
for a given indicator against the rest of the panel — useful for assessing
selection bias in any panel study.

Note: This module was originally written for the AI & Productivity paper
(indicator_col defaults historically assumed ``"ln_ai"``).  All paper-specific
defaults have been removed; callers must pass ``indicator_col`` explicitly.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pandas as pd

if TYPE_CHECKING:
    from econflow.datasets.types import SelectionSummary

from econflow.logging import get_logger

log = get_logger(__name__)


def sample_selection_summary(
    df: pd.DataFrame,
    indicator_col: str,
    compare_cols: list[str] | None = None,
    entity_col: str = "entity",
) -> pd.DataFrame:
    """Compare observations with vs. without a given indicator across a panel.

    Parameters
    ----------
    df:
        Panel DataFrame (entity × time rows, not yet multi-indexed).
    indicator_col:
        The variable whose missingness defines in- vs. out-of-sample.
        **Required** — must be passed explicitly (no default).
    compare_cols:
        Columns to compare across groups.  Defaults to all numeric columns
        present in the DataFrame other than ``indicator_col``.
    entity_col:
        Name of the cross-sectional identifier column (default: ``"entity"``).

    Returns
    -------
    pd.DataFrame
        One row per ``compare_col`` with columns:
        ``variable``, ``in_sample_mean``, ``out_of_sample_mean``,
        ``in_sample_n``, ``out_of_sample_n``.

        DataFrame-level ``.attrs`` carries aggregate counts:
        ``in_sample_rows``, ``out_of_sample_rows``,
        ``in_sample_entities``, ``out_of_sample_entities``.
    """
    if compare_cols is None:
        compare_cols = [
            c for c in df.select_dtypes("number").columns
            if c != indicator_col
        ]
    compare_cols = [c for c in compare_cols if c in df.columns]

    in_sample = df[df[indicator_col].notna()]
    out_sample = df[df[indicator_col].isna()]

    log.info(
        "Sample split on '%s': in=%d rows (%d entities), out=%d rows (%d entities)",
        indicator_col,
        len(in_sample),
        in_sample[entity_col].nunique() if entity_col in in_sample.columns else 0,
        len(out_sample),
        out_sample[entity_col].nunique() if entity_col in out_sample.columns else 0,
    )

    rows = []
    for col in compare_cols:
        in_col = pd.to_numeric(in_sample[col], errors="coerce")
        out_col = pd.to_numeric(out_sample[col], errors="coerce")
        rows.append(
            {
                "variable": col,
                "in_sample_mean": in_col.mean(),
                "out_of_sample_mean": out_col.mean(),
                "in_sample_n": int(in_col.notna().sum()),
                "out_of_sample_n": int(out_col.notna().sum()),
            }
        )

    summary = pd.DataFrame(rows)
    summary.attrs["in_sample_rows"] = int(len(in_sample))
    summary.attrs["out_of_sample_rows"] = int(len(out_sample))
    # Generic entity count — use entity_col, not hardcoded "country"
    summary.attrs["in_sample_entities"] = (
        int(in_sample[entity_col].nunique()) if entity_col in in_sample.columns else 0
    )
    summary.attrs["out_of_sample_entities"] = (
        int(out_sample[entity_col].nunique()) if entity_col in out_sample.columns else 0
    )
    # Legacy keys kept for backward compatibility with code reading "in_sample_countries"
    summary.attrs["in_sample_countries"] = summary.attrs["in_sample_entities"]
    summary.attrs["out_of_sample_countries"] = summary.attrs["out_of_sample_entities"]
    return summary


def sample_selection_summary_typed(
    df: pd.DataFrame,
    indicator_col: str,
    compare_cols: list[str] | None = None,
    entity_col: str = "entity",
) -> tuple[pd.DataFrame, SelectionSummary]:
    """Like :func:`sample_selection_summary` but also returns a typed
    :class:`~econflow.datasets.types.SelectionSummary`.

    The ``pd.DataFrame`` return value is byte-for-byte identical to what
    :func:`sample_selection_summary` returns (P0 safe).  The
    ``SelectionSummary`` carries the same aggregate counts without relying
    on ``.attrs``, which can be silently dropped by pandas operations.

    Returns
    -------
    tuple[pd.DataFrame, SelectionSummary]
    """
    from econflow.datasets.types import SelectionSummary  # noqa: PLC0415

    summary_df = sample_selection_summary(
        df, indicator_col=indicator_col, compare_cols=compare_cols, entity_col=entity_col
    )
    sel = SelectionSummary(
        in_sample_rows=int(summary_df.attrs.get("in_sample_rows", 0)),
        out_of_sample_rows=int(summary_df.attrs.get("out_of_sample_rows", 0)),
        in_sample_countries=int(summary_df.attrs.get("in_sample_countries", 0)),
        out_of_sample_countries=int(summary_df.attrs.get("out_of_sample_countries", 0)),
        comparison_frame=summary_df.copy(),
    )
    return summary_df, sel

