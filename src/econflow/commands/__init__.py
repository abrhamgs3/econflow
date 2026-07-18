"""
econflow.commands — Project lifecycle command implementations.

Each sub-module exposes a single ``run_*`` function that contains the
full implementation logic.  The CLI wiring (typer decorators, option
parsing) lives in :mod:`econflow.cli` so that command logic can be unit-
tested independently of the CLI layer.

Sub-modules
-----------
init        Create a new project skeleton.
validate    Validate configuration files and directory structure.
doctor      Inspect the Python environment and external tools.
info        Display project metadata and platform capabilities.
"""
