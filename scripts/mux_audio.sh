#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 3 ]]; then
  echo "Usage: $0 input.OSV stitched_preview.mp4 final_with_audio.mp4" >&2
  exit 2
fi

INPUT="$1"
VIDEO="$2"
OUTPUT="$3"

ffmpeg -y \
  -i "$VIDEO" \
  -i "$INPUT" \
  -map 0:v:0 \
  -map 1:a:0? \
  -c:v copy \
  -c:a aac -b:a 192k \
  -shortest \
  "$OUTPUT"

echo "Wrote $OUTPUT"
