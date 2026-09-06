from __future__ import annotations

import json
from pathlib import Path

from .preview import render_preview


def _offset_label(value):
    value = int(round(float(value)))
    return f"p{value:03d}" if value >= 0 else f"m{abs(value):03d}"


def render_imu_offset_sweep(
    source,
    output_dir,
    *,
    offsets_ms,
    start=0.0,
    duration=3.0,
    fps=15.0,
    width=1280,
    height=640,
    smoothing_ms=100.0,
    imu_source="highrate",
    with_audio=False,
):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    summaries = []

    for offset in offsets_ms:
        label = _offset_label(offset)
        output = output_dir / f"imu_{label}.mp4"

        summary = render_preview(
            source,
            output,
            start=start,
            duration=duration,
            fps=fps,
            width=width,
            height=height,
            level_horizon=True,
            level_strength=1.0,
            level_smoothing_ms=smoothing_ms,
            imu_source=imu_source,
            imu_offset_ms=float(offset),
            use_actual_video_pts=True,
            with_audio=with_audio,
            crf=22,
            preset="veryfast",
        )

        summaries.append(summary)

    manifest = {
        "source": str(source),
        "offsets_ms": [float(v) for v in offsets_ms],
        "start": float(start),
        "duration": float(duration),
        "fps": float(fps),
        "width": int(width),
        "height": int(height),
        "smoothing_ms": float(smoothing_ms),
        "imu_source": str(imu_source),
        "outputs": [
            {
                "offset_ms": item["imu_offset_ms"],
                "file": item["output"],
                "processing_fps": item["processing_fps"],
                "gravity_step_smoothed_mean_deg": (
                    item["gravity_step_smoothed_mean_deg"]
                ),
            }
            for item in summaries
        ],
    }

    manifest_path = output_dir / "imu_offset_sweep.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )

    return manifest
