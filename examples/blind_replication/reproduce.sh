#!/usr/bin/env bash
# reproduce.sh — Blind replication demonstration
#
# Runs the full replication engine workflow for this example project.
# Usage: bash examples/blind_replication/reproduce.sh
#
# From the repository root:
#   pip install -e ".[dev]"
#   bash examples/blind_replication/reproduce.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$SCRIPT_DIR"

echo "========================================================"
echo "  EconFlow Blind Replication Example"
echo "========================================================"
echo ""
echo "Project: $PROJECT_DIR"
echo ""

# Step 1: Pre-flight inspection
echo "--- Step 1: Inspect ---"
econflow inspect "$PROJECT_DIR"

# Step 2: Reproduce
echo ""
echo "--- Step 2: Reproduce ---"
econflow reproduce "$PROJECT_DIR" \
  --output-dir "$PROJECT_DIR/replication_outputs" \
  --tolerance 1e-6

# Step 3: Manual comparison (redundant with reproduce but demonstrates the command)
echo ""
echo "--- Step 3: Compare (manual) ---"
econflow compare \
  "$PROJECT_DIR/original_outputs/" \
  "$PROJECT_DIR/replication_outputs/tables/" \
  --tolerance 1e-6

echo ""
echo "========================================================"
echo "  Blind replication complete."
echo "  Report: $PROJECT_DIR/replication_outputs/replication_report.md"
echo "========================================================"
