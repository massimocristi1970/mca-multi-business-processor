#!/usr/bin/env bash
# Simple run script for MCA Multi-Business Processor (Linux)

APP_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$APP_DIR"

echo "Starting MCA Multi-Business Processor..."
echo "Directory: $APP_DIR"

# Prefer venv in project if it exists
if [ -f "$APP_DIR/venv/bin/activate" ]; then
    source "$APP_DIR/venv/bin/activate"
fi

# Find streamlit: venv, then PATH, then python3 -m
RUN_STREAMLIT=""
if command -v streamlit &>/dev/null; then
    RUN_STREAMLIT="streamlit run \"$APP_DIR/app.py\""
elif python3 -c "import streamlit" 2>/dev/null; then
    RUN_STREAMLIT="python3 -m streamlit run \"$APP_DIR/app.py\""
else
    # No streamlit: try to create venv and install deps (one-time setup)
    echo "Streamlit not found. Creating project venv and installing dependencies..."
    python3 -m venv "$APP_DIR/venv" 2>/dev/null || { echo "Error: could not create venv. Install python3-venv."; echo ""; echo "Press Enter to close."; read -r; exit 1; }
    "$APP_DIR/venv/bin/pip" install -q -r "$APP_DIR/requirements.txt" 2>/dev/null || { echo "Error: pip install failed."; echo ""; echo "Press Enter to close."; read -r; exit 1; }
    RUN_STREAMLIT="\"$APP_DIR/venv/bin/python\" -m streamlit run \"$APP_DIR/app.py\""
fi

if eval $RUN_STREAMLIT; then
    :
else
    echo ""
    echo "App exited. Press Enter to close this window."
    read -r
fi
