"""
econflow.core.registry — Project registry.

Responsibilities
----------------
* Discover APRP projects on the filesystem by scanning for ``config.yaml``
  files under a root projects directory.
* Load and return :class:`~econflow.core.config.Settings` objects on demand.

Usage (once implemented)
-------------------------
    from econflow.core.registry import ProjectRegistry
    reg = ProjectRegistry("projects/")
    names = reg.discover()           # ["econflow", ...]
    cfg   = reg.get("econflow")
"""

from __future__ import annotations

from pathlib import Path

from econflow.core.config import Settings


class ProjectRegistry:
    """
    Discovers and loads APRP projects rooted at a given directory.

    Parameters
    ----------
    root:
        Base directory containing per-project sub-directories, each with
        a ``config.yaml``.
    """

    def __init__(self, root: str | Path) -> None:
        self._root = Path(root)

    # ------------------------------------------------------------------
    # Discovery
    # ------------------------------------------------------------------

    def discover(self) -> list[str]:
        """
        Scan *root* for project directories and return their names.

        Returns
        -------
        list[str]
            Sorted list of project identifiers (directory names that
            contain a ``config.yaml``).
        """
        raise NotImplementedError

    # ------------------------------------------------------------------
    # Lookup
    # ------------------------------------------------------------------

    def get(self, project_id: str) -> Settings:
        """
        Load and return :class:`~econflow.core.config.Settings`
        for *project_id*.

        Raises
        ------
        econflow.core.exceptions.ProjectNotFoundError
            If no project with that identifier exists under *root*.
        econflow.core.exceptions.ConfigurationError
            If the project's ``config.yaml`` is invalid.
        """
        raise NotImplementedError
