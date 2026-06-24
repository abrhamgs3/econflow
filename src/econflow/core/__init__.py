"""
ai_productivity.core — Cross-cutting infrastructure for the APRP platform.

Sub-modules
-----------
config      : Pydantic-based settings loader.
registry    : Project registry for discovering and managing APRP projects.
pipeline    : Sequential pipeline orchestrator (declaration-order, no DAG).
provenance  : Run snapshot and lineage recording.
exceptions  : Platform-wide exception hierarchy rooted at APRPError.
"""
