from __future__ import annotations

from pathlib import Path

import cv2

from .pipeline import render_osv_panorama_frame
from .virtual_camera import (
    VirtualCamera,
    aspect_dimensions,
    reframe_equirectangular,
)


def reframe_osv_frame(
    source,
    output,
    *,
    source_time=0.0,
    yaw_deg=0.0,
    pitch_deg=0.0,
    roll_deg=0.0,
    fov_deg=90.0,
    aspect="16:9",
    width=None,
    height=None,
    level_horizon=True,
    level_strength=1.0,
    imu_source="highrate",
    imu_offset_ms=0.0,
    panorama_width=1920,
    panorama_height=960,
):
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)

    out_width, out_height = aspect_dimensions(
        aspect,
        width=width,
        height=height,
    )

    camera = VirtualCamera(
        yaw_deg=float(yaw_deg),
        pitch_deg=float(pitch_deg),
        fov_deg=float(fov_deg),
        roll_deg=float(
            roll_deg
        ),
    )
    camera.validate()

    panorama, panorama_diagnostics = render_osv_panorama_frame(
        source,
        source_time=source_time,
        width=panorama_width,
        height=panorama_height,
        level_horizon=level_horizon,
        level_strength=level_strength,
        imu_source=imu_source,
        imu_offset_ms=imu_offset_ms,
    )

    frame = reframe_equirectangular(
        panorama,
        camera,
        out_width,
        out_height,
    )

    if not cv2.imwrite(str(output), frame):
        raise RuntimeError(f"Could not write output image: {output}")

    return {
        "source": str(source),
        "output": str(output),
        "source_time": float(source_time),
        "output_width": int(out_width),
        "output_height": int(out_height),
        "aspect": str(aspect),
        "virtual_camera": {
            "yaw_deg": float(camera.yaw_deg),
            "pitch_deg": float(camera.pitch_deg),
            "roll_deg": float(
                camera.roll_deg
            ),
            "horizontal_fov_deg": float(camera.fov_deg),
        },
        "panorama": panorama_diagnostics,
    }
