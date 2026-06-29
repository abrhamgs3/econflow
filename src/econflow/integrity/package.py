"""
econflow.integrity.package — Replication package builder.

A :class:`ReplicationPackage` collects a certificate, configuration files,
and entry-point scripts, then writes a self-contained directory suitable for
journal submission or archival.

Output layout::

    <output_dir>/
        README.md           — auto-generated replication instructions
        certificate.json    — ReproducibilityCertificate (JSON)
        environment.txt     — installed package versions (pip-freeze style)
        config/             — copies of all supplied config files
        scripts/            — copies of all supplied entry scripts
        manifest.json       — machine-readable bundle index

Usage
-----
::

    from econflow.integrity.package import ReplicationPackage
    from econflow.integrity.certificate import ReproducibilityCertificate

    cert = ReproducibilityCertificate.load("outputs/certificate.json")

    pkg = (
        ReplicationPackage("replication_package")
        .set_certificate(cert)
        .add_config(Path("config/config.yaml"))
        .add_script(Path("scripts/01_download.py"), label="Step 1: Download data")
        .add_script(Path("scripts/02_run.py"), label="Step 2: Run pipeline")
        .set_data_readme("Data must be downloaded separately; see README.md.")
    )
    manifest = pkg.build()
"""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from econflow.integrity.certificate import ReproducibilityCertificate

# ---------------------------------------------------------------------------
# Entry helpers
# ---------------------------------------------------------------------------


@dataclass
class _ConfigEntry:
    source: Path
    dest_name: str


@dataclass
class _ScriptEntry:
    source: Path
    dest_name: str
    label: str


# ---------------------------------------------------------------------------
# ReplicationPackage
# ---------------------------------------------------------------------------


class ReplicationPackage:
    """
    Builds a journal-ready replication package directory.

    Parameters
    ----------
    output_dir:
        Root directory for the package.  Created on :meth:`build`.
    overwrite:
        If ``False`` and *output_dir* already exists, :meth:`build` raises
        :class:`FileExistsError`.
    """

    def __init__(
        self,
        output_dir: str | Path,
        *,
        overwrite: bool = True,
    ) -> None:
        self.output_dir = Path(output_dir)
        self.overwrite = overwrite

        self._certificate: ReproducibilityCertificate | None = None
        self._configs: list[_ConfigEntry] = []
        self._scripts: list[_ScriptEntry] = []
        self._data_readme: str = ""

    # ------------------------------------------------------------------
    # Builder API
    # ------------------------------------------------------------------

    def set_certificate(
        self, cert: ReproducibilityCertificate
    ) -> ReplicationPackage:
        """Attach the :class:`ReproducibilityCertificate` to the package."""
        self._certificate = cert
        return self

    def add_config(
        self,
        path: str | Path,
        *,
        dest_name: str | None = None,
    ) -> ReplicationPackage:
        """
        Add a configuration file.

        Parameters
        ----------
        path:
            Source path of the config file.
        dest_name:
            Filename inside ``config/``.  Defaults to ``path.name``.
        """
        p = Path(path)
        self._configs.append(
            _ConfigEntry(source=p, dest_name=dest_name or p.name)
        )
        return self

    def add_script(
        self,
        path: str | Path,
        *,
        label: str = "",
        dest_name: str | None = None,
    ) -> ReplicationPackage:
        """
        Add a replication script.

        Parameters
        ----------
        path:
            Source path of the script.
        label:
            Human-readable description of what the script does.
        dest_name:
            Filename inside ``scripts/``.  Defaults to ``path.name``.
        """
        p = Path(path)
        self._scripts.append(
            _ScriptEntry(source=p, dest_name=dest_name or p.name, label=label)
        )
        return self

    def set_data_readme(self, text: str) -> ReplicationPackage:
        """
        Set the data availability note included in the README.

        Parameters
        ----------
        text:
            Free-text explanation of where / how to obtain the data.
        """
        self._data_readme = text
        return self

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def build(self) -> dict[str, Any]:
        """
        Write the replication package to ``output_dir``.

        Returns
        -------
        dict
            Manifest dict (also written as ``manifest.json``).

        Raises
        ------
        FileExistsError
            If ``output_dir`` already exists and ``overwrite=False``.
        """
        if self.output_dir.exists() and not self.overwrite:
            raise FileExistsError(
                f"output_dir already exists: {self.output_dir}. "
                "Pass overwrite=True to allow overwriting."
            )

        config_dir = self.output_dir / "config"
        scripts_dir = self.output_dir / "scripts"
        config_dir.mkdir(parents=True, exist_ok=True)
        scripts_dir.mkdir(parents=True, exist_ok=True)

        manifest: dict[str, Any] = {
            "econflow_replication_package": True,
            "created_utc": datetime.now(tz=timezone.utc).isoformat(),
            "certificate": None,
            "configs": [],
            "scripts": [],
            "environment_file": None,
        }

        # ---- Certificate ---------------------------------------------------
        cert_path = self.output_dir / "certificate.json"
        if self._certificate is not None:
            self._certificate.save(cert_path)
            manifest["certificate"] = "certificate.json"
            manifest["project_name"] = self._certificate.project_name
            manifest["overall_status"] = self._certificate.overall_status
        else:
            manifest["project_name"] = ""
            manifest["overall_status"] = "unknown"

        # ---- Environment file (pip-freeze style) ---------------------------
        env_lines = _build_env_file(self._certificate)
        env_path = self.output_dir / "environment.txt"
        env_path.write_text("\n".join(env_lines) + "\n", encoding="utf-8")
        manifest["environment_file"] = "environment.txt"

        # ---- Configs -------------------------------------------------------
        for entry in self._configs:
            dest = config_dir / entry.dest_name
            if entry.source.exists():
                shutil.copy2(entry.source, dest)
            manifest["configs"].append(
                {
                    "source": str(entry.source),
                    "dest": f"config/{entry.dest_name}",
                    "exists": entry.source.exists(),
                }
            )

        # ---- Scripts -------------------------------------------------------
        for entry in self._scripts:
            dest = scripts_dir / entry.dest_name
            if entry.source.exists():
                shutil.copy2(entry.source, dest)
            manifest["scripts"].append(
                {
                    "source": str(entry.source),
                    "dest": f"scripts/{entry.dest_name}",
                    "label": entry.label,
                    "exists": entry.source.exists(),
                }
            )

        # ---- README --------------------------------------------------------
        readme_path = self.output_dir / "README.md"
        readme_path.write_text(
            _build_readme(self, manifest), encoding="utf-8"
        )

        # ---- Manifest ------------------------------------------------------
        manifest_path = self.output_dir / "manifest.json"
        manifest_path.write_text(
            json.dumps(manifest, indent=2), encoding="utf-8"
        )

        return manifest

    # ------------------------------------------------------------------
    # Repr
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        return (
            f"ReplicationPackage("
            f"configs={len(self._configs)}, "
            f"scripts={len(self._scripts)}, "
            f"cert={'yes' if self._certificate else 'no'}, "
            f"output_dir={str(self.output_dir)!r})"
        )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _build_env_file(cert: ReproducibilityCertificate | None) -> list[str]:
    """Build pip-freeze style environment lines from a certificate."""
    lines = [
        "# EconFlow replication environment",
        f"# Generated: {datetime.now(tz=timezone.utc).isoformat()}",
        "#",
        "# Install with:  pip install -r environment.txt",
        "#",
    ]
    if cert is not None:
        pkgs = cert.environment.packages
        for name, version in sorted(pkgs.items()):
            if version is not None:
                lines.append(f"{name}=={version}")
    else:
        # Fall back to querying the live environment
        try:
            import importlib.metadata as meta

            for dist in sorted(
                meta.distributions(), key=lambda d: d.metadata["Name"].lower()
            ):
                pkg_name = dist.metadata["Name"]
                version = dist.metadata["Version"]
                lines.append(f"{pkg_name}=={version}")
        except Exception:
            lines.append("# Could not enumerate installed packages")
    return lines


def _build_readme(
    pkg: ReplicationPackage,
    manifest: dict[str, Any],
) -> str:
    """Generate the README.md for the replication package."""
    project = manifest.get("project_name") or "EconFlow Project"
    status = manifest.get("overall_status", "unknown")
    status_badge = {"pass": "✅ PASS", "warn": "⚠️ WARN", "fail": "❌ FAIL"}.get(
        status, status
    )

    sections = [
        f"# Replication Package — {project}",
        "",
        f"**Reproducibility status:** {status_badge}",
        "",
        "## Contents",
        "",
        "| File / Directory | Description |",
        "| --- | --- |",
        "| `certificate.json` | Reproducibility certificate (environment + data fingerprints) |",
        "| `environment.txt` | Pinned package versions (`pip install -r environment.txt`) |",
    ]

    if manifest.get("configs"):
        sections.append("| `config/` | Configuration files used in this run |")
    if manifest.get("scripts"):
        sections.append("| `scripts/` | Replication scripts (run in order) |")

    sections += [
        "",
        "## How to Replicate",
        "",
        "1. Install the pinned environment:",
        "   ```bash",
        "   pip install -r environment.txt",
        "   ```",
    ]

    if manifest.get("scripts"):
        sections += [
            "",
            "2. Run the scripts in order:",
            "   ```bash",
        ]
        for entry in manifest["scripts"]:
            label = entry.get("label") or entry["dest"]
            sections.append(f"   # {label}")
            sections.append(f"   python {entry['dest']}")
        sections.append("   ```")

    sections += [
        "",
        "3. Verify against the certificate:",
        "   ```bash",
        "   econflow verify --baseline certificate.json",
        "   ```",
        "",
    ]

    if pkg._data_readme:
        sections += [
            "## Data Availability",
            "",
            pkg._data_readme,
            "",
        ]

    sections += [
        "## Certificate Details",
        "",
        "The `certificate.json` file contains:",
        "",
        "- Git commit hash and branch at run time",
        "- Python version and implementation",
        "- All package versions",
        "- SHA-256 fingerprints of input datasets",
        "- Configuration file SHA-256",
        "- Results of all automated integrity checks",
        "",
        "Generated by [EconFlow](https://github.com/econflow/econflow).",
        "",
    ]

    return "\n".join(sections)
