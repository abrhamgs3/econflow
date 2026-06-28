"""
econflow.outputs.base — BaseRenderer abstract class and RendererError.

Every renderer must:

1. Inherit from :class:`BaseRenderer`.
2. Implement :meth:`render` which converts a :class:`ReportTable` to a
   string in the renderer's format.
3. Register itself with ``@register_renderer("id")``.

:meth:`render_to_file` is provided as a concrete helper — subclasses
should not need to override it.
"""

from __future__ import annotations

import abc
from pathlib import Path
from typing import Any

from econflow.outputs.model import ReportTable


class RendererError(Exception):
    """Raised when a renderer fails to produce output."""

    def __init__(
        self,
        message: str,
        *,
        renderer_id: str = "",
        cause: Exception | None = None,
    ) -> None:
        super().__init__(message)
        self.renderer_id = renderer_id
        self.cause = cause

    def __str__(self) -> str:
        base = super().__str__()
        if self.renderer_id:
            base = f"[{self.renderer_id}] {base}"
        return base


class BaseRenderer(abc.ABC):
    """
    Abstract base class for all EconFlow table renderers.

    Subclasses implement :meth:`render` to convert a :class:`ReportTable`
    into a string.  The default :meth:`render_to_file` writes that string
    to disk.

    Class attributes
    ----------------
    renderer_id:
        Set automatically by ``@register_renderer()``.
    name:
        Human-readable renderer name.
    file_extension:
        Default output file extension (e.g. ``".csv"``).
    """

    renderer_id: str = "base"
    name: str = "BaseRenderer"
    file_extension: str = ".txt"

    # ------------------------------------------------------------------
    # Abstract interface
    # ------------------------------------------------------------------

    @abc.abstractmethod
    def render(self, table: ReportTable, **kwargs: Any) -> str:
        """
        Convert *table* to a formatted string.

        Parameters
        ----------
        table:
            The table to render.
        **kwargs:
            Renderer-specific options.

        Returns
        -------
        str
            The rendered table as a string in the renderer's format.

        Raises
        ------
        RendererError
            If rendering fails.
        """

    # ------------------------------------------------------------------
    # Concrete helpers
    # ------------------------------------------------------------------

    def render_to_file(
        self,
        table: ReportTable,
        path: Path,
        *,
        encoding: str = "utf-8",
        **kwargs: Any,
    ) -> Path:
        """
        Render *table* and write the result to *path*.

        Parameters
        ----------
        table:
            The table to render.
        path:
            Destination file path.  Parent directories are created if
            they do not exist.
        encoding:
            File encoding.  Default ``"utf-8"``.
        **kwargs:
            Passed through to :meth:`render`.

        Returns
        -------
        Path
            The resolved absolute path of the written file.
        """
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        content = self.render(table, **kwargs)
        path.write_text(content, encoding=encoding)
        return path.resolve()

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} id={self.renderer_id!r}>"
