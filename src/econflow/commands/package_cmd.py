"""
econflow.commands.package_cmd — Implementation of ``econflow package``.

Named ``package_cmd`` to avoid shadowing the stdlib ``package`` concept.
"""

from __future__ import annotations

from pathlib import Path

from rich.console import Console


def run_package(
    *,
    certificate_path: Path | None,
    config_paths: list[Path],
    script_paths: list[Path],
    output_dir: Path,
    overwrite: bool,
    data_readme: str,
    console: Console,
) -> int:
    """
    Build a :class:`~econflow.integrity.ReplicationPackage` and write it
    to *output_dir*.

    Parameters
    ----------
    certificate_path:
        Path to a :class:`~econflow.integrity.ReproducibilityCertificate`
        JSON file.  Optional — the package can be built without one.
    config_paths:
        Config files to copy into ``config/``.
    script_paths:
        Replication scripts to copy into ``scripts/``.
    output_dir:
        Destination directory.
    overwrite:
        Whether to overwrite an existing *output_dir*.
    data_readme:
        Data availability note for the README.
    console:
        Rich console for output.

    Returns
    -------
    int
        0 on success, 1 on failure.
    """
    from econflow.integrity import ReplicationPackage, ReproducibilityCertificate

    console.print()
    console.rule("[bold]EconFlow package[/bold]")
    console.print()

    pkg = ReplicationPackage(output_dir, overwrite=overwrite)

    # ---- Certificate ----------------------------------------------------
    if certificate_path is not None:
        if not certificate_path.exists():
            console.print(
                f"[bold red]✘ Certificate not found:[/bold red] {certificate_path}"
            )
            return 1
        try:
            cert = ReproducibilityCertificate.load(certificate_path)
            pkg.set_certificate(cert)
            console.print(
                f"  [dim]Certificate loaded: {cert.certificate_id[:12]}…[/dim]"
            )
        except Exception as exc:
            console.print(
                f"[bold red]✘ Could not load certificate:[/bold red] {exc}"
            )
            return 1

    # ---- Config files ---------------------------------------------------
    for cp in config_paths:
        pkg.add_config(cp)

    # ---- Scripts --------------------------------------------------------
    for sp in script_paths:
        pkg.add_script(sp)

    # ---- Data note ------------------------------------------------------
    if data_readme:
        pkg.set_data_readme(data_readme)

    # ---- Build ----------------------------------------------------------
    try:
        manifest = pkg.build()
    except FileExistsError as exc:
        console.print(f"[bold red]✘ {exc}[/bold red]")
        console.print("  Pass --overwrite to allow overwriting.")
        return 1
    except Exception as exc:
        console.print(
            f"[bold red]✘ Failed to build replication package:[/bold red] {exc}"
        )
        return 1

    # ---- Summary --------------------------------------------------------
    console.print(f"  Configs:  {len(manifest['configs'])}")
    console.print(f"  Scripts:  {len(manifest['scripts'])}")
    console.print(f"  Status:   {manifest.get('overall_status', 'n/a')}")
    console.print()
    console.print(f"  [bold]Package written to:[/bold] {output_dir}")
    console.print()
    return 0
