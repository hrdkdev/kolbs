#!/usr/bin/env bash
# Run the Kolb's Learning Cycle app with uv

set -e

# Check if uv is installed
if ! command -v uv &> /dev/null; then
    echo "Error: uv is not installed."
    echo "Install it with: curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
fi

# Install dependencies if needed
if [ ! -f ".venv/pyvenv.cfg" ]; then
    echo "Installing dependencies..."
    uv pip install -r requirements.txt
fi

# Run the app
echo "Starting Kolb's Learning Cycle app on http://127.0.0.1:7123"
uv run python app.py
