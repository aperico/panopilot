from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

import cv2

from .attitude import horizon_correction, rotate_equirectangular
from .dji import extract_calibration, orientation_at_source_time
from .factory import FactoryCalibratedMapper
from .source import decode_lens_pair, probe_source


def render_osv_panorama_frame(
    source_path,
    *,
    source_time=0.0,
    width=1920,
    height=960,
    level_horizon=False,
    level_strength=1.0,
    imu_source="highrate",
    imu_offset_ms=0.0,
):
    source_path = Path(source_path)

    if not source_path.is_file():
        raise FileNotFoundError(f"Source does not exist: {source_path}")

    probe = probe_source(source_path)
    calibration = extract_calibration(source_path)

    lens0, lens1, lens_streams = decode_lens_pair(
        source_path,
        source_time=source_time,
        probe=probe,
    )

    src_h, src_w = lens0.shape[:2]

    mapper = FactoryCalibratedMapper(
        calibration,
        src_w,
        src_h,
        out_w=width,
        out_h=height,
    )

    panorama = mapper.stitch(lens0, lens1)

    leveling = {"enabled": False}

    if level_horizon:
        orientation = orientation_at_source_time(
            source_path,
            source_time,
            source=imu_source,
            imu_offset_ms=imu_offset_ms,
        )

        rotation, diagnostics = horizon_correction(
            orientation["quat"],
            strength=level_strength,
        )

        panorama = rotate_equirectangular(
            panorama,
            rotation.T,
        )

        leveling = {
            "enabled": True,
            "source_time": float(source_time),
            "imu_source": str(imu_source),
            "imu_offset_ms": float(imu_offset_ms),
            "interpolated": bool(orientation.get("interpolated")),
            "frame_index": orientation.get("frame_index"),
            "next_frame_index": orientation.get("next_frame_index"),
            "alpha": orientation.get("alpha"),
            "quaternion": [float(v) for v in orientation["quat"]],
            **diagnostics,
        }

    fmt = probe.get("format", {})

    diagnostics = {
        "source": str(source_path),
        "source_time": float(source_time),
        "source_duration": (
            float(fmt["duration"])
            if fmt.get("duration") is not None
            else None
        ),
        "lens_stream_indexes": [int(s["index"]) for s in lens_streams],
        "decoded_lens_size": [src_w, src_h],
        "camera_model": calibration.get("model"),
        "camera_firmware": calibration.get("fw_b") or calibration.get("fw_a"),
        "calibration_lens_blocks": len(calibration.get("lenses", [])),
        "mapping": asdict(mapper.diagnostics),
        "horizon_leveling": leveling,
    }

    return panorama, diagnostics


def stitch_osv_frame(
    source_path,
    output_path,
    *,
    source_time=0.0,
    width=1920,
    height=960,
    level_horizon=False,
    level_strength=1.0,
    imu_source="highrate",
    imu_offset_ms=0.0,
):
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    panorama, diagnostics = render_osv_panorama_frame(
        source_path,
        source_time=source_time,
        width=width,
        height=height,
        level_horizon=level_horizon,
        level_strength=level_strength,
        imu_source=imu_source,
        imu_offset_ms=imu_offset_ms,
    )

    if not cv2.imwrite(str(output_path), panorama):
        raise RuntimeError(f"Could not write output image: {output_path}")

    return {
        **diagnostics,
        "output": str(output_path),
    }
