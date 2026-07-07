"""
econflow.config.docs — Auto-generated configuration reference.

Generates human-readable documentation for all EconFlow configuration files
directly from the Pydantic v2 model definitions in
:mod:`econflow.config.models`.  The output is always in sync with the schema
because it reads ``model_fields``, ``Field(description=...)``,
``Field(examples=...)``, and field metadata (Literal args, constraints) at
runtime.

Two output formats are supported:

``markdown``
    A GitHub-flavoured Markdown document written to
    ``docs/reference/configuration.md`` by default.

``text``
    Plain text for terminal display.

Usage
-----
::

    from econflow.config.docs import generate_config_reference

    md = generate_config_reference(format="markdown")
    print(md)

Or via the CLI::

    econflow docs config                     # write docs/reference/configuration.md
    econflow docs config --stdout            # print markdown to stdout
    econflow docs config --text              # print plain text to stdout
    econflow docs config --output path.md   # write to a custom path

Or programmatically::

    from econflow.config.docs import write_config_reference
    write_config_reference("docs/reference/configuration.md")
"""

from __future__ import annotations

import textwrap
from pathlib import Path
from typing import Any, Literal, get_args, get_origin

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Canonical output path for the generated reference.
DEFAULT_OUTPUT_PATH: str = "docs/reference/configuration.md"

_HR_MD = "\n---\n"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _type_name(annotation: Any) -> str:
    """Return a concise human-readable type annotation string."""
    if annotation is None:
        return "any"
    origin = get_origin(annotation)
    if origin is Literal:  # type: ignore[comparison-overlap]
        return "string"
    if origin is list:
        args = get_args(annotation)
        inner = _type_name(args[0]) if args else "any"
        return f"list[{inner}]"
    if hasattr(annotation, "__name__"):
        return annotation.__name__
    s = str(annotation)
    s = s.replace("typing.", "").replace("Optional[", "").rstrip("]")
    return s


def _default_str(field_info: Any) -> str:
    """Return the default value as a display string."""
    from pydantic_core import PydanticUndefined  # type: ignore[import]

    dv = field_info.default
    if dv is PydanticUndefined:
        df = field_info.default_factory
        if df is None:
            return "*(required)*"
        return f"`{df()!r}`"
    if dv is None:
        return "`null`"
    if isinstance(dv, bool):
        return f"`{'true' if dv else 'false'}`"
    if isinstance(dv, str):
        return '`"' + dv + '"`'
    return f"`{dv!r}`"


def _allowed_values_str(field_info: Any) -> str:
    """Extract allowed-value constraints from a field.

    Sources checked:
    - ``Literal[...]`` annotation -> enumerated values
    - annotated-types metadata -> Ge, Le, Gt, Lt, MinLen, MaxLen, Pattern
    """
    ann = field_info.annotation
    origin = get_origin(ann)

    if origin is Literal:  # type: ignore[comparison-overlap]
        values = get_args(ann)
        return " | ".join(f"`{v!r}`" for v in values)

    parts: list[str] = []
    for meta in getattr(field_info, "metadata", []):
        cls_name = type(meta).__name__
        if cls_name == "Ge":
            parts.append(f">= `{meta.ge}`")
        elif cls_name == "Le":
            parts.append(f"<= `{meta.le}`")
        elif cls_name == "Gt":
            parts.append(f"> `{meta.gt}`")
        elif cls_name == "Lt":
            parts.append(f"< `{meta.lt}`")
        elif cls_name == "MinLen":
            parts.append(f"min len `{meta.min_length}`")
        elif cls_name == "MaxLen":
            parts.append(f"max len `{meta.max_length}`")
        elif cls_name in ("Pattern", "Regex"):
            pattern = getattr(meta, "pattern", getattr(meta, "regex", ""))
            parts.append(f"pattern `{pattern}`")
    return ", ".join(parts) if parts else ""


def _examples_str(field_info: Any, format: str = "markdown") -> str:
    """Return a formatted examples block, or empty string if no examples."""
    ex = getattr(field_info, "examples", None)
    if not ex:
        return ""
    if format == "markdown":
        items = "\n".join(f"    - `{e!r}`" for e in ex)
        return f"\n  *Examples:*\n{items}"
    else:
        items = ", ".join(repr(e) for e in ex)
        return f"  (examples: {items})"


# ---------------------------------------------------------------------------
# Core rendering
# ---------------------------------------------------------------------------

def _document_model(
    model_class: Any,
    heading_level: int = 3,
    format: str = "markdown",
    yaml_key: str = "",
) -> str:
    """Render documentation for a single Pydantic model.

    Every field is rendered with: type, default, allowed values,
    description, and examples.
    """
    lines: list[str] = []
    docstring = (model_class.__doc__ or "").strip()
    short_doc = docstring.split("\n\n")[0].strip()

    if format == "markdown":
        prefix = "#" * heading_level
        title = yaml_key or model_class.__name__
        lines.append(f"{prefix} `{title}`\n")
        if short_doc:
            lines.append(f"{short_doc}\n")
        lines.append("")
        lines.append("| Field | Type | Default | Allowed | Description |")
        lines.append("|-------|------|---------|---------|-------------|")
        for field_name, field_info in model_class.model_fields.items():
            ftype = _type_name(field_info.annotation)
            default = _default_str(field_info)
            allowed = _allowed_values_str(field_info)
            desc = field_info.description or ""
            ex = _examples_str(field_info, format="markdown")
            if ex:
                desc = f"{desc} {ex}"
            lines.append(
                f"| `{field_name}` | `{ftype}` | {default} | {allowed} | {desc} |"
            )
        lines.append("")
    else:
        title = yaml_key or model_class.__name__
        lines.append(f"[{title.upper()}]")
        if short_doc:
            for ln in textwrap.wrap(short_doc, 76):
                lines.append(f"  {ln}")
            lines.append("")
        for field_name, field_info in model_class.model_fields.items():
            ftype = _type_name(field_info.annotation)
            default = _default_str(field_info)
            allowed = _allowed_values_str(field_info)
            desc = field_info.description or ""
            ex = _examples_str(field_info, format="text")
            lines.append(f"  {field_name} ({ftype}, default {default})")
            if allowed:
                lines.append(f"    allowed: {allowed}")
            if desc:
                for ln in textwrap.wrap(f"    {desc}", 78):
                    lines.append(ln)
            if ex:
                lines.append(f"  {ex.strip()}")
            lines.append("")

    return "\n".join(lines)


def _walk_model(
    model_class: Any,
    heading_level: int = 3,
    format: str = "markdown",
    yaml_key: str = "",
    visited: set | None = None,
) -> list[str]:
    """Recursively document *model_class* and all nested Pydantic models."""
    from pydantic import BaseModel  # type: ignore[import]

    if visited is None:
        visited = set()
    cls_id = id(model_class)
    if cls_id in visited:
        return []
    visited.add(cls_id)

    sections: list[str] = []
    sections.append(_document_model(model_class, heading_level, format, yaml_key))

    for field_name, field_info in model_class.model_fields.items():
        ann = field_info.annotation
        if get_origin(ann) is list:
            args = get_args(ann)
            ann = args[0] if args else None
        if ann is None:
            continue
        try:
            if isinstance(ann, type) and issubclass(ann, BaseModel):
                child_key = f"{yaml_key}.{field_name}" if yaml_key else field_name
                sections.extend(
                    _walk_model(
                        ann,
                        heading_level=heading_level + 1,
                        format=format,
                        yaml_key=child_key,
                        visited=visited,
                    )
                )
        except TypeError:
            pass

    return sections


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_config_reference(format: str = "markdown") -> str:
    """Generate a complete configuration reference document.

    Reads the Pydantic models in :mod:`econflow.config.models` and renders
    every field with its type, default value, allowed values, description,
    and examples.

    Parameters
    ----------
    format:
        ``"markdown"`` (default) or ``"text"``.

    Returns
    -------
    str
        The rendered reference document.
    """
    from econflow.config.models import (  # type: ignore[import]
        ModelsConfig,
        OutputsConfig,
        ProjectConfig,
    )

    if format == "markdown":
        header = (
            "# EconFlow Configuration Reference\n\n"
            "> **Auto-generated** from `src/econflow/config/models.py`.\n"
            "> Do not edit this file manually"
            " -- run `econflow docs config` to regenerate.\n\n"
            "EconFlow projects are configured through three YAML files:\n\n"
            "| File | Purpose |\n"
            "|------|---------|\n"
            "| `config.yaml` | Project metadata, data source,"
            " sample period, variable names |\n"
            "| `models.yaml` | Estimator specifications"
            " (one entry per regression) |\n"
            "| `outputs.yaml` | Table and figure output settings |\n\n"
            "All files use strict validation -- unknown keys are rejected.\n"
            "Run `econflow validate config/` to check all three files at once.\n"
            "Run `econflow validate --data` to also verify the data CSV.\n\n"
            "> **Tip:** Error messages from `econflow validate` and"
            " `econflow run` include a fix hint and reference this document.\n\n"
        )
        separator = _HR_MD
    else:
        header = (
            "ECONFLOW CONFIGURATION REFERENCE\n"
            "=================================\n"
            "Auto-generated from src/econflow/config/models.py.\n\n"
            "Three YAML files configure an EconFlow project:\n"
            "  config.yaml  -- project metadata, data source, sample, variables\n"
            "  models.yaml  -- estimator specs (one per regression)\n"
            "  outputs.yaml -- table and figure output settings\n\n"
            "Unknown keys are rejected.  Run: econflow validate config/\n\n"
        )
        separator = "\n" + "=" * 72 + "\n\n"

    parts: list[str] = [header]

    if format == "markdown":
        parts.append("## `config.yaml`\n")
    else:
        parts.append("config.yaml\n-----------\n")
    parts.extend(_walk_model(ProjectConfig, heading_level=3, format=format, yaml_key=""))
    parts.append(separator)

    if format == "markdown":
        parts.append("## `models.yaml`\n")
    else:
        parts.append("models.yaml\n-----------\n")
    parts.extend(_walk_model(ModelsConfig, heading_level=3, format=format, yaml_key=""))
    parts.append(separator)

    if format == "markdown":
        parts.append("## `outputs.yaml`\n")
    else:
        parts.append("outputs.yaml\n------------\n")
    parts.extend(_walk_model(OutputsConfig, heading_level=3, format=format, yaml_key=""))

    return "\n".join(parts)


def write_config_reference(
    path: str | Path | None = None,
    format: str = "markdown",
) -> Path:
    """Write the configuration reference to *path*.

    Parameters
    ----------
    path:
        Destination file path.  Defaults to ``docs/reference/configuration.md``.
    format:
        ``"markdown"`` (default) or ``"text"``.

    Returns
    -------
    Path
        Absolute path of the written file.
    """
    dest = Path(path or DEFAULT_OUTPUT_PATH).expanduser().resolve()
    dest.parent.mkdir(parents=True, exist_ok=True)
    content = generate_config_reference(format=format)
    dest.write_text(content, encoding="utf-8")
    return dest
