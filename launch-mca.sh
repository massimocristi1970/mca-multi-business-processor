#!/usr/bin/env bash
# Opens a terminal and runs the app (for .desktop launcher when Terminal=true doesn't work well)

APP_DIR="$(cd "$(dirname "$0")" && pwd)"

# Try common terminal emulators (one will usually be available)
if command -v gnome-terminal &>/dev/null; then
    gnome-terminal -- bash -c "cd \"$APP_DIR\" && ./run.sh; echo ''; echo 'Press Enter to close'; read -r"
elif command -v kgx &>/dev/null; then
    kgx -e bash -c "cd \"$APP_DIR\" && ./run.sh; echo ''; echo 'Press Enter to close'; read -r"
elif command -v konsole &>/dev/null; then
    konsole -e bash -c "cd \"$APP_DIR\" && ./run.sh; echo ''; echo 'Press Enter to close'; read -r"
elif command -v xterm &>/dev/null; then
    xterm -e bash -c "cd \"$APP_DIR\" && ./run.sh; echo ''; echo 'Press Enter to close'; read -r"
else
    # Fallback: run in background and hope a terminal is already open, or show error in notify
    notify-send "MCA Multi-Business Processor" "No terminal found. Run from a terminal: $APP_DIR/run.sh" 2>/dev/null || true
    "$APP_DIR/run.sh"
fi
