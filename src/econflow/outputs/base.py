"""
econflow.outputs.base — Abstract output renderer interface.

All APRP renderers subclass :class:`BaseRenderer` and implement
:meth:`render`.  This uniform interface allows the pipeline to drive output
generation without knowing the concrete renderer type.

Renderers receive typed inputs (DataFrames, EstimationResult objects) and
write artefacts (files) to a project output directory, returning the paths of
the files created.
"""

from __future__ import annotations

import abc
from pathlib import Path
from typing import Any


class BaseRenderer(abc.ABC):
    """
    Abstract base class for output renderers.

    Parameters
    ----------
    output_dir:
        Root directory for rendered output artefacts.
    overwrite:
        Whether to overwrite existing files.  Default ``True``.
    """

    #: Human-readable renderer name (set by subclasses).
    renderer_name: str = ""

    def __init__(self, output_dir: str | Path, overwrite: bool = True) -> None:
        self.output_dir = Path(output_dir)
        self.overwrite = overwrite

    # ------------------------------------------------------------------
    # Abstract interface
    # ------------------------------------------------------------------

    @abc.abstractmethod
    def render(self, data: Any, filename: str, **kwargs: Any) -> Path:
        """
        Render *data* and write to ``output_dir / filename``.

        Parameters
        ----------
        data:
            Input data to render (type depends on the concrete renderer).
        filename:
            Output filename (without directory prefix).
        **kwargs:
            Renderer-specific options.

        Returns
        -------
        Path
            Absolute path to the written artefact.

        Raises
        ------
        econflow.core.exceptions.OutputError
            If rendering or writing fails.
        FileExistsError
            If the file already exists and ``overwrite=False``.
        """

    # ------------------------------------------------------------------
    # Concrete helpers
    # ------------------------------------------------------------------

    def _resolve_path(self, filename: str) -> Path:
        """Return ``output_dir / filename``, creating parent directories."""
        path = self.output_dir / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} output_dir='{self.output_dir}'>"
