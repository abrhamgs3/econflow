"""
econflow.datasets.migration — Compatibility layer between DataFrames and Datasets.

This module provides the adapters needed during the migration from raw
``pd.DataFrame`` throughout the codebase to typed ``Dataset`` objects.

Functions
---------
from_dataframe(df, ...)     Convert a raw DataFrame to a typed Dataset.
to_dataframe(ds_or_df)      Extract a ``pd.DataFrame`` from a Dataset or pass through.
accepts_dataset(func)       Decorator: unwraps ``PanelDataset`` before calling func.

All three utilities follow the principle that **existing callers do not need
to change** — wrapping a function with ``@accepts_dataset`` allows it to
silently accept either a plain DataFrame or a PanelDataset without the caller
needing to know which type is passed.

Column-name reconciliation
--------------------------
The ingestion layer uses ``"iso3"`` as the entity column; the econometrics
layer uses ``"country"``.  Use :func:`rename_entity_col` to reconcile::

    ds = from_dataframe(df, entity_col="iso3")
    ds = rename_entity_col(ds, "country")   # now safe to pass to panel.py
"""

from __future__ import annotations

import functools
from collections.abc import Callable
from typing import TYPE_CHECKING, Any, TypeVar

import pandas as pd

from econflow.datasets.panel import PanelDataset
from econflow.datasets.types import DatasetMetadata, ProvenanceRecord

if TYPE_CHECKING:
    pass

F = TypeVar("F", bound=Callable[..., Any])


# ---------------------------------------------------------------------------
# Conversion helpers
# ---------------------------------------------------------------------------


def from_dataframe(
    df: pd.DataFrame,
    entity_col: str = "country",
    time_col: str = "year",
    title: str = "",
    source: str = "",
    origin: str = "from_dataframe",
) -> PanelDataset:
    """
    Convert a raw ``pd.DataFrame`` to a :class:`~econflow.datasets.panel.PanelDataset`.

    Parameters
    ----------
    df:
        Source DataFrame (wide-format panel).
    entity_col:
        Name of the entity/cross-section column.
    time_col:
        Name of the time period column.
    title / source:
        Metadata strings stored on the returned Dataset.
    origin:
        Provenance origin label (e.g. ``"loaded_from_csv"``).

    Returns
    -------
    PanelDataset
        A new ``PanelDataset`` wrapping a copy of *df*.

    Examples
    --------
    >>> import pandas as pd
    >>> from econflow.datasets.migration import from_dataframe
    >>> df = pd.DataFrame({"country": ["A", "B"], "year": [2020, 2020], "gdp": [1.0, 2.0]})
    >>> ds = from_dataframe(df)
    >>> ds.entity_identifier
    'country'
    """
    return PanelDataset(
        df=df,
        entity_col=entity_col,
        time_col=time_col,
        metadata=DatasetMetadata(title=title, source=source),
        provenance=ProvenanceRecord(origin=origin),
    )


def to_dataframe(ds_or_df: pd.DataFrame | PanelDataset | Any) -> pd.DataFrame:
    """
    Extract a ``pd.DataFrame`` from a Dataset or pass through a plain DataFrame.

    This is the central passthrough function used by functions that were
    written for raw DataFrames but now also accept Datasets.

    Parameters
    ----------
    ds_or_df:
        A ``PanelDataset``, any other ``Dataset`` subclass, or a plain
        ``pd.DataFrame``.

    Returns
    -------
    pd.DataFrame
        The underlying DataFrame (a copy).

    Raises
    ------
    TypeError
        If *ds_or_df* is neither a ``pd.DataFrame`` nor a ``Dataset``.

    Examples
    --------
    >>> from econflow.datasets.migration import to_dataframe
    >>> df = pd.DataFrame({"a": [1, 2]})
    >>> to_dataframe(df) is df
    False   # always returns a copy
    >>> to_dataframe(df).equals(df)
    True
    """
    # Lazy import to avoid circular dependency at module level
    from econflow.datasets.base import Dataset as _Dataset

    if isinstance(ds_or_df, pd.DataFrame):
        return ds_or_df.copy()
    if isinstance(ds_or_df, PanelDataset):
        return ds_or_df.to_dataframe()
    if isinstance(ds_or_df, _Dataset):
        return ds_or_df.dataframe
    raise TypeError(
        f"Expected pd.DataFrame or Dataset; got {type(ds_or_df).__name__!r}. "
        "Pass a pd.DataFrame or a Dataset subclass."
    )


def rename_entity_col(ds: PanelDataset, new_name: str) -> PanelDataset:
    """
    Return a new :class:`PanelDataset` with the entity column renamed.

    Convenience wrapper around :meth:`PanelDataset.rename_entity_col` for
    use in function pipelines.

    Parameters
    ----------
    ds:
        Source PanelDataset.
    new_name:
        New entity column name (e.g. ``"country"``).
    """
    return ds.rename_entity_col(new_name)


# ---------------------------------------------------------------------------
# Decorator
# ---------------------------------------------------------------------------


def accepts_dataset(func: F) -> F:
    """
    Decorator that allows a function expecting ``pd.DataFrame`` to also accept
    a :class:`~econflow.datasets.panel.PanelDataset` or any
    :class:`~econflow.datasets.base.Dataset`.

    The decorator inspects the **first positional argument** of the function.
    If it is a Dataset, the underlying DataFrame is extracted and passed
    instead.  All other arguments are forwarded unchanged.

    Usage
    -----
    Decorate existing DataFrame-accepting functions to make them Dataset-aware
    without changing their internals::

        @accepts_dataset
        def run_robustness_suite(df: pd.DataFrame) -> dict:
            # ... existing code, no changes needed
            pass

        # Now works with both:
        run_robustness_suite(raw_df)
        run_robustness_suite(panel_dataset)

    P0 safety
    ---------
    The extracted DataFrame is a copy identical to the original.  No sorting,
    reindexing, or column manipulation is performed by this decorator.
    """
    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        from econflow.datasets.base import Dataset as _Dataset

        if args and isinstance(args[0], _Dataset):
            # Replace first arg with the flat DataFrame
            args = (to_dataframe(args[0]), *args[1:])
        return func(*args, **kwargs)

    return wrapper  # type: ignore[return-value]
