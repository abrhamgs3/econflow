"""
econflow.config.docs — Auto-generated configuration reference.

Architecture Stabilization Milestone 4.

Generates human-readable documentation for all EconFlow configuration files
directly from the Pydantic v2 model definitions in
:mod:`econflow.config.models`.  The output is always in sync with the schema
because it reads ``model_fields``, ``Field(description=...)`` and
``Field(examples=...)`` at runtime.

Two output formats are supported:

``markdown``
    A GitHub-flavoured Markdown document suitable for ``docs/`` directories
    and GitHub wikis.

``text``
    Plain text output for ``econflow validate --help`` and terminal display.

Usage
-----
::

    from econflow.config.docs import generate_config_reference

    md = generate_config_reference(format="markdown")
    print(md)

    txt = generate_config_reference(format="text")
    print(txt)

Or via the CLI::

    econflow docs config          # prints markdown to stdout
    econflow docs config --text   # prints plain text

Or to write a file::

    from econflow.config.docs import write_config_reference
    write_config_reference("docs/CONFIG_REFERENCE.md")
"""

from __future__ import annotations

import textwrap
from pathlib import Path
from typing import Any, Literal, get_args, get_origin

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_INDENT = "  "
_HR_MD = "\n---\n"


def _type_name(annotation: Any) -> str:
    """Return a concise human-readable type annotation string."""
    if annotation is None:
        return "any"
    origin = get_origin(annotation)
    if origin is Literal:  # type: ignore[comparison-overlap]
        return " | ".join(repr(a) for a in get_args(annotation))
    if origin is list:
        args = get_args(annotation)
        inner = _type_name(args[0]) if args else "any"
        return f"list[{inner}]"
    if hasattr(annotation, "__name__"):
        return annotation.__name__
    s = str(annotation)
    # clean up typing.Optional etc.
    s = s.replace("typing.", "").replace("Optional[", "").rstrip("]")
    return s


def _default_str(field_info: Any) -> str:
    """Return the default value as a string, or empty string if required."""
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
        return f'`"{dv}"`'
    return f"`{dv!r}`"


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
# Core doc generation
# ---------------------------------------------------------------------------

def _document_model(
    model_class: Any,
    heading_level: int = 3,
    format: str = "markdown",
    yaml_key: str = "",
) -> str:
    """
    Render documentation for a single Pydantic model.

    Parameters
    ----------
    model_class:
        The Pydantic BaseModel class to document.
    heading_level:
        Markdown heading level (2 = ``##``, 3 = ``###``).
    format:
        ``"markdown"`` or ``"text"``.
    yaml_key:
        The YAML key path under which this model sits, e.g. ``"project"``.
    """
    lines: list[str] = []

    docstring = (model_class.__doc__ or "").strip()
    # Only keep the first paragraph of the docstring
    short_doc = docstring.split("\n\n")[0].strip()

    if format == "markdown":
        prefix = "#" * heading_level
        title = yaml_key or model_class.__name__
        lines.append(f"{prefix} `{title}`\n")
        if short_doc:
            lines.append(f"{short_doc}\n")
        lines.append("")
        lines.append("| Field | Type | Default | Description |")
        lines.append("|-------|------|---------|-------------|")
        for field_name, field_info in model_class.model_fields.items():
            ftype = _type_name(field_info.annotation)
            default = _default_str(field_info)
            desc = field_info.description or ""
            ex = _examples_str(field_info, format="markdown")
            if ex:
                desc = f"{desc} {ex}"
            lines.append(f"| `{field_name}` | `{ftype}` | {default} | {desc} |")
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
            desc = field_info.description or ""
            ex = _examples_str(field_info, format="text")
            lines.append(f"  {field_name} ({ftype}, default {default})")
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
    """
    Recursively document *model_class* and all nested Pydantic models.

    Returns a list of rendered section strings.
    """
    from pydantic import BaseModel  # type: ignore[import]

    if visited is None:
        visited = set()
    cls_id = id(model_class)
    if cls_id in visited:
        return []
    visited.add(cls_id)

    sections: list[str] = []
    sections.append(_document_model(model_class, heading_level, format, yaml_key))

    # Recurse into nested BaseModel fields
    for field_name, field_info in model_class.model_fields.items():
        ann = field_info.annotation
        # unwrap list[X]
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
    """
    Generate a complete configuration reference document.

    Reads the Pydantic models in :mod:`econflow.config.models` and renders
    every field with its type, default value, and description.

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
        header = textwrap.dedent("""\
            # EconFlow Configuration Reference

            > **Auto-generated** from `src/econflow/config/models.py`.
            > Do not edit this file manually — run `econflow docs config` to regenerate.

            EconFlow projects are configured through three YAML files:

            | File | Purpose |
            |------|---------|
            | `config.yaml` | Project metadata, data source, sample period, variable names |
            | `models.yaml` | Estimator specifications (one entry per regression) |
            | `outputs.yaml` | Table and figure output settings |

            All files support strict validation.  Unknown keys cause an error.
            Run `econflow validate config/` to check all three files at once.

        """)
        separator = _HR_MD
    else:
        header = textwrap.dedent("""\
            ECONFLOW CONFIGURATION REFERENCE
            =================================
            Auto-generated from src/econflow/config/models.py.

            Three YAML files configure an EconFlow project:
              config.yaml  — project metadata, data source, sample, variables
              models.yaml  — estimator specs (one per regression)
              outputs.yaml — table and figure output settings

        """)
        separator = "\n" + "=" * 72 + "\n\n"

    parts: list[str] = [header]

    # config.yaml
    if format == "markdown":
        parts.append("## `config.yaml`\n")
    else:
        parts.append("config.yaml\n-----------\n")
    parts.extend(_walk_model(ProjectConfig, heading_level=3, format=format, yaml_key=""))
    parts.append(separator)

    # models.yaml
    if format == "markdown":
        parts.append("## `models.yaml`\n")
    else:
        parts.append("models.yaml\n-----------\n")
    parts.extend(_walk_model(ModelsConfig, heading_level=3, format=format, yaml_key=""))
    parts.append(separator)

    # outputs.yaml
    if format == "markdown":
        parts.append("## `outputs.yaml`\n")
    else:
        parts.append("outputs.yaml\n------------\n")
    parts.extend(_walk_model(OutputsConfig, heading_level=3, format=format, yaml_key=""))

    return "\n".join(parts)


def write_config_reference(
    path: str | Path,
    format: str = "markdown",
) -> Path:
    """
    Write the configuration reference to *path*.

    Parameters
    ----------
    path:
        Destination file path.
    format:
        ``"markdown"`` (default) or ``"text"``.

    Returns
    -------
    Path
        Absolute path of the written file.
    """
    dest = Path(path).expanduser().resolve()
    dest.parent.mkdir(parents=True, exist_ok=True)
    content = generate_config_reference(format=format)
    dest.write_text(content, encoding="utf-8")
    return dest
