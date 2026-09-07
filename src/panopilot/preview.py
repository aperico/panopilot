"""
Short panoramic preview-video pipeline.

This is still an architecture-validation implementation:

OSV
 ↓
one FFmpeg decode/filter graph for both synchronized lens streams
 ↓
factory calibrated OpenCV stitch
 ↓
DJI IMU horizon correction per output frame
 ↓
H.264 panoramic preview + source audio

Important:
- Both lenses are decoded in ONE FFmpeg process and hstacked before entering
  Python. This avoids drift caused by two independent decoder processes.
- IMU metadata is loaded ONCE for the clip and interpolated at each output
  Source Time.
- Horizon correction remains a second spherical resample in v0.8. Correctness
  is intentionally preferred over optimization at this stage.
"""
from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

import numpy as np

from .attitude import (
    gravity_equirectangular,
    rotate_equirectangular,
    smooth_unit_vectors_centered,
    stabilized_horizon_rotation,
)
from .stabilization import (
    build_adaptive_trajectory,
    sample_trajectory,
)
from .dji import (
    extract_calibration,
    extract_orientation_data,
    orientation_from_samples,
)
from .factory import FactoryCalibratedMapper
from .source import (
    lens_streams,
    preview_exposure_times,
    probe_source,
    source_frame_times,
)


def _read_exact(pipe, byte_count):
    chunks = []
    remaining = byte_count

    while remaining:
        chunk = pipe.read(remaining)
        if not chunk:
            return None

        chunks.append(chunk)
        remaining -= len(chunk)

    return b"".join(chunks)


def _decoder_command(
    source,
    stream0,
    stream1,
    source_width,
    source_height,
    fps,
    start,
    duration,
):
    # One graph => the two lens outputs use the same clock / fps selection.
    filter_graph = (
        f"[0:{stream0}]fps={fps},format=bgr24[l0];"
        f"[0:{stream1}]fps={fps},format=bgr24[l1];"
        "[l0][l1]hstack=inputs=2[out]"
    )

    cmd = [
        "ffmpeg",
        "-v", "error",
        "-ss", f"{float(start):.6f}",
        "-i", str(source),
        "-filter_complex", filter_graph,
        "-map", "[out]",
        "-t", f"{float(duration):.6f}",
        "-pix_fmt", "bgr24",
        "-f", "rawvideo",
        "pipe:1",
    ]

    return cmd


def _encoder_command(
    source,
    output,
    width,
    height,
    fps,
    start,
    duration,
    crf,
    preset,
    with_audio,
):
    cmd = [
        "ffmpeg",
        "-y",
        "-v", "error",
        "-f", "rawvideo",
        "-pix_fmt", "bgr24",
        "-s:v", f"{int(width)}x{int(height)}",
        "-r", f"{float(fps):.6f}",
        "-i", "pipe:0",
    ]

    if with_audio:
        cmd += [
            "-ss", f"{float(start):.6f}",
            "-t", f"{float(duration):.6f}",
            "-i", str(source),
            "-map", "0:v:0",
            "-map", "1:a:0?",
        ]
    else:
        cmd += [
            "-map", "0:v:0",
        ]

    cmd += [
        "-c:v", "libx264",
        "-preset", str(preset),
        "-crf", str(int(crf)),
        "-pix_fmt", "yuv420p",
    ]

    if with_audio:
        cmd += [
            "-c:a", "aac",
            "-b:a", "192k",
            "-af", "aresample=async=1:first_pts=0",
            "-shortest",
        ]
    else:
        cmd += ["-an"]

    cmd += [
        "-movflags", "+faststart",
        str(output),
    ]

    return cmd


def render_preview(
    source,
    output,
    *,
    start=0.0,
    duration=3.0,
    fps=30.0,
    width=1920,
    height=960,
    level_horizon=True,
    level_strength=1.0,
    level_smoothing_ms=100.0,
    stabilization_amount=0.0,
    stabilization_smoothing_ms=400.0,
    imu_source="highrate",
    imu_offset_ms=0.0,
    use_actual_video_pts=True,
    with_audio=True,
    crf=20,
    preset="veryfast",
):
    source = Path(source)
    output = Path(output)

    if not source.is_file():
        raise FileNotFoundError(f"Source does not exist: {source}")

    if duration <= 0:
        raise ValueError("duration must be greater than zero")

    if fps <= 0:
        raise ValueError("fps must be greater than zero")

    if width <= 0 or height <= 0:
        raise ValueError("output dimensions must be positive")

    output.parent.mkdir(parents=True, exist_ok=True)

    probe = probe_source(source)
    lenses = lens_streams(probe)
    stream0 = int(lenses[0]["index"])
    stream1 = int(lenses[1]["index"])

    source_width = int(lenses[0]["width"])
    source_height = int(lenses[0]["height"])

    if (
        int(lenses[1]["width"]) != source_width
        or int(lenses[1]["height"]) != source_height
    ):
        raise RuntimeError("The two lens streams have different dimensions")

    calibration = extract_calibration(source)
    mapper = FactoryCalibratedMapper(
        calibration,
        source_width,
        source_height,
        out_w=width,
        out_h=height,
    )

    stabilization_amount = max(0.0, min(1.0, float(stabilization_amount)))
    imu_data = (
        extract_orientation_data(source)
        if (level_horizon or stabilization_amount > 1e-9)
        else None
    )

    orientation_samples = []

    if level_horizon or stabilization_amount > 1e-9:
        if imu_source == "highrate" and imu_data["highrate"]:
            orientation_samples = imu_data["highrate"]
        elif imu_source in ("highrate", "perframe"):
            orientation_samples = imu_data["perframe"]
        else:
            raise ValueError(
                "imu_source must be 'highrate' or 'perframe'"
            )

    expected_frames = max(1, int(round(float(duration) * float(fps))))

    source_pts = []

    if use_actual_video_pts:
        source_pts = source_frame_times(
            source,
            stream0,
            float(start),
            float(duration),
        )

    exposure_times, pts_diagnostics = preview_exposure_times(
        source_pts,
        start=float(start),
        duration=float(duration),
        output_fps=float(fps),
    )

    leveled_gravity = None
    raw_gravity = None
    raw_quaternions = None
    stabilized_quaternions = None
    stabilization_diagnostics = None

    if level_horizon or stabilization_amount > 1e-9:
        trajectory = build_adaptive_trajectory(
            orientation_samples, stabilization_amount
        )
        raw_quaternions, stabilized_quaternions = sample_trajectory(
            trajectory, exposure_times, imu_offset_ms=imu_offset_ms
        )
        stabilization_diagnostics = {
            **trajectory.diagnostics,
            "imu_source_used": (
                orientation_samples[0].get("source")
                if orientation_samples else None
            ),
            "sync_method": (
                "dji-perframe-highrate-anchor"
                if orientation_samples
                and orientation_samples[0].get("source") == "highrate"
                else "dji-perframe"
            ),
            "highrate_timeline": (
                imu_data.get("highrate_diagnostics")
                if imu_data else None
            ),
        }
        raw_gravity = np.asarray(
            [gravity_equirectangular(q) for q in raw_quaternions],
            dtype=np.float64,
        )
        if level_horizon:
            sigma_frames = (
                max(0.0, float(level_smoothing_ms))
                / 1000.0 * float(fps)
            )
            leveled_gravity = smooth_unit_vectors_centered(
                raw_gravity, sigma_frames
            )


    decoder = subprocess.Popen(
        _decoder_command(
            source,
            stream0,
            stream1,
            source_width,
            source_height,
            fps,
            start,
            duration,
        ),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        bufsize=16 * 1024 * 1024,
    )

    encoder = subprocess.Popen(
        _encoder_command(
            source,
            output,
            width,
            height,
            fps,
            start,
            duration,
            crf,
            preset,
            with_audio,
        ),
        stdin=subprocess.PIPE,
        stderr=subprocess.PIPE,
        bufsize=16 * 1024 * 1024,
    )

    stacked_width = source_width * 2
    frame_bytes = stacked_width * source_height * 3

    frame_index = 0
    started = time.perf_counter()
    tilts = []

    try:
        while True:
            raw = _read_exact(decoder.stdout, frame_bytes)

            if raw is None:
                break

            stacked = np.frombuffer(raw, dtype=np.uint8).reshape(
                source_height,
                stacked_width,
                3,
            )

            lens0 = stacked[:, :source_width]
            lens1 = stacked[:, source_width:]

            panorama = mapper.stitch(lens0, lens1)

            if level_horizon or stabilization_amount > 1e-9:
                orientation_index = min(frame_index, len(raw_quaternions) - 1)
                gravity = (
                    leveled_gravity[min(frame_index, len(leveled_gravity) - 1)]
                    if level_horizon else None
                )
                rotation, diagnostics = stabilized_horizon_rotation(
                    raw_quaternion=raw_quaternions[orientation_index],
                    smoothed_quaternion=stabilized_quaternions[orientation_index],
                    leveled_gravity=gravity,
                    stabilization_amount=stabilization_amount,
                    level_horizon=level_horizon,
                    level_strength=level_strength,
                )
                if level_horizon:
                    tilts.append(diagnostics["tilt_before_deg"])
                panorama = rotate_equirectangular(panorama, rotation)

            try:
                encoder.stdin.write(panorama.tobytes())
            except BrokenPipeError:
                break

            frame_index += 1

            if frame_index % 10 == 0:
                elapsed = time.perf_counter() - started
                throughput = frame_index / elapsed if elapsed else 0.0
                print(
                    f"\rframes={frame_index} "
                    f"processing_fps={throughput:.2f}",
                    end="",
                    file=sys.stderr,
                    flush=True,
                )

    finally:
        if decoder.stdout:
            decoder.stdout.close()

        if encoder.stdin:
            try:
                encoder.stdin.close()
            except BrokenPipeError:
                pass

        decoder_stderr = (
            decoder.stderr.read().decode("utf-8", "replace")
            if decoder.stderr
            else ""
        )

        encoder_stderr = (
            encoder.stderr.read().decode("utf-8", "replace")
            if encoder.stderr
            else ""
        )

        decoder.wait()
        encoder.wait()

    elapsed = time.perf_counter() - started
    throughput = frame_index / elapsed if elapsed else 0.0

    if decoder.returncode != 0:
        raise RuntimeError(
            "FFmpeg lens decode failed:\n" + decoder_stderr
        )

    if encoder.returncode != 0:
        raise RuntimeError(
            "FFmpeg preview encode failed:\n" + encoder_stderr
        )

    print(file=sys.stderr)

    gravity_raw_step = []
    gravity_smoothed_step = []

    if level_horizon and raw_gravity is not None and len(raw_gravity) > 1:
        raw_dots = np.sum(raw_gravity[:-1] * raw_gravity[1:], axis=1)
        raw_dots = np.clip(raw_dots, -1.0, 1.0)
        gravity_raw_step = np.degrees(np.arccos(raw_dots)).tolist()

        smooth_dots = np.sum(
            leveled_gravity[:-1] * leveled_gravity[1:],
            axis=1,
        )
        smooth_dots = np.clip(smooth_dots, -1.0, 1.0)
        gravity_smoothed_step = np.degrees(
            np.arccos(smooth_dots)
        ).tolist()

    summary = {
        "source": str(source),
        "output": str(output),
        "start": float(start),
        "duration_requested": float(duration),
        "fps": float(fps),
        "frames": int(frame_index),
        "processing_seconds": float(elapsed),
        "processing_fps": float(throughput),
        "output_width": int(width),
        "output_height": int(height),
        "level_horizon": bool(level_horizon),
        "level_strength": float(level_strength),
        "level_smoothing_ms": float(level_smoothing_ms),
        "stabilization_amount": float(stabilization_amount),
        "stabilization_algorithm": "adaptive-highrate-v1",
        "stabilization_diagnostics": stabilization_diagnostics,
        "imu_source_requested": str(imu_source),
        "imu_source_used": (
            orientation_samples[0].get("source")
            if orientation_samples else None
        ),
        "imu_offset_ms": float(imu_offset_ms),
        "actual_video_pts": pts_diagnostics,
        "highrate_imu": (
            imu_data["highrate_diagnostics"]
            if imu_data else None
        ),
        "with_audio": bool(with_audio),
        "tilt_min_deg": min(tilts) if tilts else None,
        "tilt_max_deg": max(tilts) if tilts else None,
        "tilt_mean_deg": (
            sum(tilts) / len(tilts)
            if tilts
            else None
        ),
        "gravity_step_raw_mean_deg": (
            sum(gravity_raw_step) / len(gravity_raw_step)
            if gravity_raw_step else None
        ),
        "gravity_step_smoothed_mean_deg": (
            sum(gravity_smoothed_step) / len(gravity_smoothed_step)
            if gravity_smoothed_step else None
        ),
        "gravity_step_raw_max_deg": (
            max(gravity_raw_step) if gravity_raw_step else None
        ),
        "gravity_step_smoothed_max_deg": (
            max(gravity_smoothed_step)
            if gravity_smoothed_step else None
        ),
        "factory_mapping": mapper.diagnostics.__dict__,
    }

    return summary
