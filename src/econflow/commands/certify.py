"""
econflow.commands.certify — Implementation of ``econflow certify``.
"""

from __future__ import annotations

from pathlib import Path

from rich.console import Console


def run_certify(
    *,
    project_name: str,
    data_paths: list[Path],
    config_path: Path | None,
    output_path: Path,
    run_checks: bool,
    estimator_results: list | None,
    repo_root: Path | None,
    console: Console,
) -> int:
    """
    Build a :class:`~econflow.integrity.ReproducibilityCertificate` and
    write it to *output_path*.

    Parameters
    ----------
    project_name:
        Human-readable project identifier.
    data_paths:
        Input dataset paths to fingerprint.
    config_path:
        Project configuration YAML (optional).
    output_path:
        Destination for the JSON certificate.
    run_checks:
        If ``True``, run all registered integrity checks on every supplied
        *estimator_results* entry.
    estimator_results:
        List of :class:`~econflow.estimation.result.EstimationResult`
        objects.  Required when *run_checks* is ``True``.
    repo_root:
        Git repository root.  Defaults to CWD.
    console:
        Rich :class:`~rich.console.Console` for output.

    Returns
    -------
    int
        Exit code — 0 on success, 1 on failure.
    """
    from econflow.integrity import ReproducibilityCertificate
    from econflow.integrity.checks.base import IntegrityCheckResult

    console.print()
    console.rule("[bold]EconFlow certify[/bold]")
    console.print()

    # ---- Auto-detect run context from provenance if not supplied ----------
    run_meta_path = Path("outputs/provenance/run_metadata.json")
    if run_meta_path.exists() and (not data_paths or not project_name):
        try:
            import json
            meta = json.loads(run_meta_path.read_text())
            if not project_name:
                project_name = meta.get("project_name") or project_name
            if not data_paths:
                raw_inputs = meta.get("inputs", {})
                detected = [
                    Path(v) for v in raw_inputs.values()
                    if isinstance(v, str) and v.endswith(".csv") and Path(v).exists()
                ]
                if detected:
                    data_paths = detected
                    console.print(
                        f"  [dim]Auto-detected {len(data_paths)} data file(s) "
                        f"from {run_meta_path}[/dim]"
                    )
            if config_path is None:
                detected_cfg = meta.get("config_path")
                if detected_cfg and Path(detected_cfg).exists():
                    config_path = Path(detected_cfg)
        except Exception:
            pass  # silently skip — user can supply flags manually

    # ---- Fingerprint data paths ------------------------------------------
    missing = [str(p) for p in data_paths if not p.exists()]
    if missing:
        console.print("[bold yellow]⚠ Warning:[/bold yellow] data paths not found:")
        for m in missing:
            console.print(f"  [dim]{m}[/dim]")

    # ---- Run integrity checks --------------------------------------------
    check_results: list[IntegrityCheckResult] = []

    if run_checks and estimator_results:
        from econflow.integrity.checks import get_check
        from econflow.integrity.checks import list_checks as _lc

        check_metas = _lc()
        implemented = [m for m in check_metas if m["status"] == "implemented"]
        console.print(
            f"[dim]Running {len(implemented)} integrity check(s) on "
            f"{len(estimator_results)} estimator result(s)…[/dim]"
        )
        for meta in implemented:
            check_cls = get_check(meta["id"])
            check = check_cls()
            for er in estimator_results:
                try:
                    result = check.run(er)
                    check_results.append(result)
                except Exception as exc:
                    check_results.append(
                        IntegrityCheckResult(
                            check_id=meta["id"],
                            name=meta["label"],
                            status="fail",
                            message=f"Check raised an exception: {exc}",
                        )
                    )
    elif run_checks:
        console.print(
            "[dim]No estimator results supplied; skipping integrity checks.[/dim]"
        )

    # ---- Build certificate -----------------------------------------------
    try:
        cert = ReproducibilityCertificate.build(
            project_name=project_name,
            data_paths=[str(p) for p in data_paths],
            config_path=config_path,
            check_results=check_results,
            repo_root=repo_root,
        )
    except Exception as exc:
        console.print(f"[bold red]✘ Failed to build certificate:[/bold red] {exc}")
        return 1

    # ---- Write certificate -----------------------------------------------
    try:
        cert.save(output_path)
    except Exception as exc:
        console.print(f"[bold red]✘ Failed to write certificate:[/bold red] {exc}")
        return 1

    # ---- Summary ---------------------------------------------------------
    status_fmt = {
        "pass": "[bold green]✔ PASS[/bold green]",
        "warn": "[bold yellow]⚠ WARN[/bold yellow]",
        "fail": "[bold red]✘ FAIL[/bold red]",
    }.get(cert.overall_status, cert.overall_status)

    console.print(f"  Project:    [bold]{cert.project_name or '(unnamed)'}[/bold]")
    console.print(f"  Status:     {status_fmt}")
    console.print(f"  Cert ID:    [dim]{cert.certificate_id}[/dim]")
    git_commit = cert.environment.git.get("commit") or "(none)"
    git_dirty = cert.environment.git.get("dirty", False)
    console.print(f"  Git commit: [dim]{git_commit[:12]}[/dim]")
    if git_dirty:
        console.print(
            "  [bold yellow]⚠  Dirty working tree:[/bold yellow] your working directory\n"
            "     has uncommitted changes.  For a fully reproducible certificate,\n"
            "     commit or stash all changes before running [bold]econflow certify[/bold].\n"
            "     This flag is recorded in the certificate so reviewers are aware."
        )
    console.print(f"  Data files: {len(cert.data)}")
    console.print(f"  Checks run: {len(cert.check_results)}")
    console.print()
    console.print(f"  [bold]Certificate written to:[/bold] {output_path}")
    console.print()

    if check_results:
        _print_check_summary(check_results, console)

    return 0 if cert.overall_status in ("pass", "warn") else 1


def _print_check_summary(
    results: list,
    console: Console,
) -> None:
    """Print a compact check results table."""
    from rich.table import Table

    table = Table(show_header=True, header_style="bold", box=None, padding=(0, 1))
    table.add_column("Check")
