#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "Usage: $0 /path/to/file.OSV" >&2
  exit 2
fi

INPUT="$(realpath "$1")"

if [[ ! -f "$INPUT" ]]; then
  echo "File not found: $INPUT" >&2
  exit 2
fi

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RESULTS="$ROOT/results"
mkdir -p "$RESULTS"

echo "Inspecting: $INPUT"

ffprobe \
  -v error \
  -show_format \
  -show_streams \
  -show_chapters \
  -print_format json \
  "$INPUT" > "$RESULTS/ffprobe.json"

ffmpeg -hide_banner -i "$INPUT" -f null - 2> "$RESULTS/ffmpeg_probe.txt" || true

python3 - "$RESULTS/ffprobe.json" "$INPUT" > "$RESULTS/stream_summary.txt" <<'PY'
import json, sys, os

probe_path, input_path = sys.argv[1], sys.argv[2]
with open(probe_path, "r", encoding="utf-8") as f:
    data = json.load(f)

fmt = data.get("format", {})
streams = data.get("streams", [])

print("PanoPilot SPIKE-01 Stream Summary")
print("=" * 60)
print(f"File: {input_path}")
print(f"Size bytes: {os.path.getsize(input_path)}")
print(f"Format: {fmt.get('format_name')}")
print(f"Duration: {fmt.get('duration')}")
print(f"Start time: {fmt.get('start_time')}")
print(f"Bit rate: {fmt.get('bit_rate')}")
print()

for st in streams:
    idx = st.get("index")
    typ = st.get("codec_type")
    print(f"Stream #{idx} [{typ}]")
    print(f"  codec:       {st.get('codec_name')}")
    print(f"  profile:     {st.get('profile')}")
    print(f"  pixel fmt:   {st.get('pix_fmt')}")
    print(f"  dimensions:  {st.get('width')}x{st.get('height')}")
    print(f"  frame rate:  {st.get('avg_frame_rate')}")
    print(f"  r_frame_rate:{st.get('r_frame_rate')}")
    print(f"  time base:   {st.get('time_base')}")
    print(f"  start time:  {st.get('start_time')}")
    print(f"  duration:    {st.get('duration')}")
    print(f"  channels:    {st.get('channels')}")
    print(f"  sample rate: {st.get('sample_rate')}")
    tags = st.get("tags") or {}
    if tags:
        print("  tags:")
        for k, v in sorted(tags.items()):
            print(f"    {k}: {v}")
    print()

counts = {}
for st in streams:
    counts[st.get("codec_type", "unknown")] = counts.get(st.get("codec_type", "unknown"), 0) + 1

print("Stream counts:")
for typ, count in sorted(counts.items()):
    print(f"  {typ}: {count}")
PY

echo
echo "Created:"
echo "  $RESULTS/ffprobe.json"
echo "  $RESULTS/ffmpeg_probe.txt"
echo "  $RESULTS/stream_summary.txt"
echo
echo "Next: review ffprobe.json before attempting reconstruction."
