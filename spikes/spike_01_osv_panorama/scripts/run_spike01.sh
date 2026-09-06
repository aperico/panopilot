#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "Usage: $0 /path/to/file.OSV" >&2
  exit 2
fi

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

"$ROOT/capture_environment.sh"
"$ROOT/inspect_osv.sh" "$1"

echo
echo "SPIKE-01 inspection phase complete."
echo "Review results/stream_summary.txt and results/ffprobe.json next."
