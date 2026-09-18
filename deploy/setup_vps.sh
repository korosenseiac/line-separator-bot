#!/usr/bin/env bash
# Quick shortcut to execute the root install.sh
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." &>/dev/null && pwd)"

if [ -f "$SCRIPT_DIR/install.sh" ]; then
    bash "$SCRIPT_DIR/install.sh"
else
    echo "install.sh not found in parent directory."
    exit 1
fi
