#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RESULTS="$ROOT/results"
mkdir -p "$RESULTS"

OUT="$RESULTS/environment.txt"

{
  echo "PanoPilot SPIKE-01 Environment"
  echo "Captured: $(date --iso-8601=seconds)"
  echo
  echo "== OS =="
  cat /etc/os-release 2>/dev/null || true
  echo
  echo "== Kernel =="
  uname -a
  echo
  echo "== CPU =="
  lscpu 2>/dev/null || true
  echo
  echo "== Memory =="
  free -h 2>/dev/null || true
  echo
  echo "== GPU / PCI =="
  lspci 2>/dev/null | grep -Ei 'vga|3d|display' || true
  echo
  echo "== FFmpeg =="
  ffmpeg -version 2>/dev/null | head -n 8 || echo "ffmpeg not found"
  echo
  echo "== ffprobe =="
  ffprobe -version 2>/dev/null | head -n 5 || echo "ffprobe not found"
  echo
  echo "== Python =="
  python3 --version 2>/dev/null || true
  echo
  echo "== VAAPI =="
  vainfo 2>/dev/null | head -n 80 || echo "vainfo unavailable or VAAPI not configured"
} > "$OUT"

echo "Wrote $OUT"
