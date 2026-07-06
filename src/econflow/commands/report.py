"""
econflow.commands.report — ``econflow report`` command implementation.

Renders a :class:`~econflow.outputs.bundle.PublicationBundle` from saved
pipeline results into a structured output directory.
"""

from __future__ import annotations

from pathlib import Path

from rich.console import Console

from econflow.commands._shared import STATUS_ICONS


def run_report(
    *,
    output_dir: Path,
    formats: str = "csv,latex,markdown,html",
    overwrite: bool = True,
    config_path: Path | None = None,
    console: Console | None = None,
) -> int:
    """
    Core logic for ``econflow report``.

    Parameters
    ----------
    output_dir:
        Root directory for the bundle.
    formats:
        Comma-separated renderer ids (e.g. ``"csv,latex,markdown,html"``).
    overwrite:
        Whether to overwrite an existing output directory.
    config_path:
        Optional path to project config.yaml.
    console:
        Rich console for output.  Creates a default console if omitted.

    Returns
    -------
    int
        Exit code: 0 on success, 1 on error.
    """
    if console is None:
        console = Console()

    OK   = STATUS_ICONS["pass"]
    WARN = STATUS_ICONS["warn"]
    FAIL = STATUS_ICONS["fail"]

    table_formats = [f.strip() for f in formats.split(",") if f.strip()]

    # Validate renderer ids ------------------------------------------------
    try:
        from econflow.outputs import list_renderers
        available = {r["id"] for r in list_renderers()}
        unknown = set(table_formats) - available
        if unknown:
            console.print(
                f"  {FAIL}  Unknown renderer(s): "
                f"{', '.join(sorted(unknown))}"
            )
            console.print(f"       Available: {', '.join(sorted(available))}")
            return 1
    except Exception as exc:
        console.print(f"  {FAIL}  Failed to load renderer registry: {exc}")
        return 1

    console.print()
    console.print("[bold]EconFlow — Reporting Engine[/bold]")
    console.print(f"  Output dir : {output_dir}")
    console.print(f"  Formats    : {', '.join(table_formats)}")
    console.print(f"  Overwrite  : {overwrite}")
    console.print()

    # Load saved results (placeholder until Reproducibility sprint) --------
    results_dir = Path.cwd() / "outputs" / "results"
    if not results_dir.exists():
        console.print(
            f"  {WARN}  No saved results found in [dim]{results_dir}[/dim]."
        )
        console.print(
            "       Run [bold]econflow run[/bold] first, "
            "then re-run [bold]econflow report[/bold]."
        )
        console.print()

    # Build and write bundle -----------------------------------------------
    try:
        from econflow.outputs import PublicationBundle

        bundle = PublicationBundle(
            output_dir,
            table_formats=table_formats,
            overwrite=overwrite,
        )

        # TODO (Reproducibility sprint): deserialise EstimationResult objects
        # and call table / figure builders here before writing the bundle:
        #
        #   reg_table = build_regression_table(results)
        #   bundle.add_table(reg_table)
        #   coef_plot = CoefficientPlot().build(results[0])
        #   bundle.add_figure(coef_plot)

        manifest = bundle.write()
        n_tables = len(manifest.get("tables", []))
        n_figures = len(manifest.get("figures", []))

        console.print(
            f"  {OK}  Bundle written — "
            f"{n_tables} table(s), {n_figures} figure(s)"
        )
        console.print(f"       Directory : {output_dir}")
        console.print(f"       Manifest  : {output_dir / 'manifest.json'}")
        return 0

    except FileExistsError as exc:
        console.print(f"  {FAIL}  {exc}")
        return 1
    except Exception as exc:
        console.print(f"  {FAIL}  Bundle write failed: {exc}")
        return 1
