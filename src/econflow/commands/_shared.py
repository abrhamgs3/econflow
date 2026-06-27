"""
econflow.commands._shared — shared utilities for CLI command modules.

This module provides constants and helpers that are used by two or more
command modules (doctor, validate, info, init).  Import from here to
keep a single source of truth.

Contents
--------
STATUS_ICONS : dict[str, str]
    Rich markup strings for each check status (pass/warn/fail/skip/info).

deep_get(data, *keys) -> object
    Navigate a nested dict safely; return None if any key is missing.

load_yaml_safe(path) -> tuple[dict | None, str]
    Load a YAML file and return (data, error_message).  Returns
    (None, error) if the file does not exist or cannot be parsed.
"""

from __future__ import annotations

from pathlib import Path

import yaml

# ---------------------------------------------------------------------------
# Status icons
# ---------------------------------------------------------------------------

#: Rich markup icon for each check status used across doctor, validate, init.
STATUS_ICONS: dict[str, str] = {
    "pass": "[bold green]✔[/bold green]",
    "warn": "[bold yellow]⚠[/bold yellow]",
    "fail": "[bold red]✘[/bold red]",
    "skip": "[dim]–[/dim]",
    "info": "[bold blue]ℹ[/bold blue]",
}


# ---------------------------------------------------------------------------
# YAML helpers
# ---------------------------------------------------------------------------

def load_yaml_safe(path: Path) -> tuple[dict | None, str]:
    """
    Try to load a YAML file.

    Parameters
    ----------
    path:
        Path to the YAML file.

    Returns
    -------
    tuple[dict | None, str]
        ``(data, "")`` on success, ``(None, error_message)`` on failure.
    """
    if not path.exists():
        return None, f"File not found: {path}"
    try:
        with path.open(encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
        if not isinstance(data, dict):
            return None, "YAML parsed but did not produce a mapping (dict)"
        return data, ""
    except yaml.YAMLError as exc:
        return None, f"YAML parse error: {exc}"


# ---------------------------------------------------------------------------
# Dict navigation
# ---------------------------------------------------------------------------

def deep_get(data: dict, *keys: str) -> object:
    """
    Navigate a nested dict using a sequence of keys.

    Returns ``None`` if any key is absent or if an intermediate value is
    not a dict (rather than raising ``KeyError`` or ``TypeError``).

    Parameters
    ----------
    data:
        The root dict.
    *keys:
        Sequence of string keys forming the navigation path.

    Examples
    --------
    >>> deep_get({"a": {"b": 1}}, "a", "b")
    1
    >>> deep_get({"a": {}}, "a", "missing") is None
    True
    """
    obj: object = data
    for key in keys:
        if not isinstance(obj, dict):
            return None
        obj = obj.get(key)  # type: ignore[union-attr]
    return obj
