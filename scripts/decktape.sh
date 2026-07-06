#!/usr/bin/env bash
set -euo pipefail
command -v decktape >/dev/null 2>&1 || { echo "decktape is required for PDF generation." >&2; exit 127; }
decktape reveal "$1" "$2"
