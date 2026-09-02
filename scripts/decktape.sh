#!/usr/bin/env bash
set -euo pipefail

if (( $# != 2 )); then
    echo "Usage: $0 HTML OUTPUT.pdf" >&2
    exit 2
fi

output=$2
uncompressed="${output%.pdf}.uncompressed.pdf"
server_root=$(dirname "$(dirname "$1")")
html=${1#"$server_root"/}
server_pid=""
mkdir -p "$(dirname "$output")"

cleanup() {
    status=$?
    if [[ -n $server_pid ]]; then
        kill "$server_pid" 2>/dev/null || true
        wait "$server_pid" 2>/dev/null || true
    fi
    rm -f "$uncompressed"
    exit "$status"
}
trap cleanup EXIT INT TERM

python3 -m http.server 8000 --bind 127.0.0.1 \
    --directory "$server_root" >/tmp/decktape-http.log 2>&1 &
server_pid=$!

server_ready=false
for _ in {1..100}; do
    if python3 -c 'import urllib.request; urllib.request.urlopen("http://127.0.0.1:8000", timeout=1)' \
        >/dev/null 2>&1; then
        server_ready=true
        break
    fi
    sleep 0.1
done
if [[ $server_ready != true ]]; then
    echo "Slide preview server failed to start" >&2
    exit 1
fi

decktape \
    --chrome-arg=--no-sandbox \
    --chrome-arg=--disable-gpu \
    -s 1600x900 \
    -p 2000 \
    reveal "http://127.0.0.1:8000/$html" "$uncompressed"
gs -sDEVICE=pdfwrite -dCompatibilityLevel=1.4 -dPDFSETTINGS=/ebook \
    -dNOPAUSE -dQUIET -dBATCH -sOutputFile="$output" "$uncompressed"
chown "${HOST_UID:?HOST_UID is required}:${HOST_GID:?HOST_GID is required}" "$output"
