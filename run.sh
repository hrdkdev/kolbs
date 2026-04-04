#!/usr/bin/env bash
# Run the Kolb's Learning Cycle app with uv

set -e

if ! command -v uv &> /dev/null; then
    echo "Error: uv is not installed."
    echo "Install it with: curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
fi

echo "Syncing dependencies with uv..."
uv sync

echo "Starting Kolb's Learning Cycle app on http://127.0.0.1:7123"
uv run python app.py
