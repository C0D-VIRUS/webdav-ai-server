#!/bin/bash
# ──────────────────────────────────────────────────────────────
#  Launch: WebDAV File Server + AI File Monitor
# ──────────────────────────────────────────────────────────────

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv"

echo "Starting WebDAV + AI File Monitor …"
echo

# Check Python 3
if ! command -v python3 &> /dev/null; then
    echo "Error: python3 not found. Please install Python 3."
    exit 1
fi

# Create venv if it doesn't exist
if [ ! -d "$VENV_DIR" ]; then
    echo "Creating virtual environment …"
    python3 -m venv "$VENV_DIR"
fi

# Activate venv
source "$VENV_DIR/bin/activate"

# Install/upgrade dependencies
echo "Checking dependencies …"
pip install --quiet --upgrade pip
pip install --quiet google-genai watchdog

# Run the server using the venv Python
python "$SCRIPT_DIR/server.py"