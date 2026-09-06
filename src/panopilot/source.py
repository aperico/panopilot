from __future__ import annotations

import json
import subprocess

import cv2
import numpy as np


def probe_source(path):
    cmd = [
        "ffprobe",
        "-v", "error",
        "-show_streams",
        "-show_format",
        "-print_format", "json",
        str(path),
    ]

    try:
        result = subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as exc:
        raise RuntimeError(
            "ffprobe was not found. Install a full FFmpeg/ffprobe build first."
        ) from exc
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(
            f"ffprobe could not inspect the source:\n{exc.stderr}"
        ) from exc

    return json.loads(result.stdout)


def lens_streams(probe):
    candidates = []

    for stream in probe.get("streams", []):
        if stream.get("codec_type") != "video":
            continue

        if stream.get("disposition", {}).get("attached_pic"):
            continue

        width = stream.get("width")
        height = stream.get("height")

        # Current Osmo 360 lens streams are square. Keeping this criterion here
        # makes source-specific stream discovery explicit and easy to replace.
        if width and height and abs(int(width) - int(height)) <= 4:
            candidates.append(stream)

    if len(candidates) < 2:
        raise RuntimeError(
            "Could not identify two square panoramic lens video streams"
        )

    return candidates[:2]


def audio_streams(probe):
    return [
        stream
        for stream in probe.get("streams", [])
        if stream.get("codec_type") == "audio"
    ]


def _decode_png(path, stream_index, source_time):
    # Accurate output seeking: decode from the input and select the requested
    # output timestamp. This is slower than keyframe-only seeking but is better
    # for our single-frame validation path.
    cmd = [
        "ffmpeg",
        "-v", "error",
        "-i", str(path),
        "-ss", f"{float(source_time):.6f}",
        "-map", f"0:{int(stream_index)}",
        "-frames:v", "1",
        "-f", "image2pipe",
        "-vcodec", "png",
        "pipe:1",
    ]

    try:
        result = subprocess.run(
            cmd,
            check=True,
            capture_output=True,
        )
    except FileNotFoundError as exc:
        raise RuntimeError(
            "ffmpeg was not found. Install a full FFmpeg build with HEVC "
            "decoding support first."
        ) from exc
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.decode("utf-8", "replace")
        raise RuntimeError(
            f"FFmpeg could not decode lens stream {stream_index}:\n{stderr}"
        ) from exc

    if not result.stdout:
        raise RuntimeError(
            f"FFmpeg produced no frame for lens stream {stream_index} "
            f"at Source Time {source_time:.3f}s"
        )

    image = cv2.imdecode(
        np.frombuffer(result.stdout, dtype=np.uint8),
        cv2.IMREAD_COLOR,
    )

    if image is None:
        raise RuntimeError(
            f"Could not decode FFmpeg PNG output for lens stream {stream_index}"
        )

    return image


def decode_lens_pair(path, source_time=0.0, probe=None):
    probe = probe or probe_source(path)
    lenses = lens_streams(probe)

    frame0 = _decode_png(path, lenses[0]["index"], source_time)
    frame1 = _decode_png(path, lenses[1]["index"], source_time)

    if frame0.shape[:2] != frame1.shape[:2]:
        raise RuntimeError(
            f"Decoded lens dimensions differ: "
            f"{frame0.shape[:2]} vs {frame1.shape[:2]}"
        )

    return frame0, frame1, lenses


def source_frame_times(path, stream_index, start, duration):
    """
    Return actual source-frame PTS values (seconds) for a small interval.

    This is used to align horizon correction to the exposure time of the frame
    that the preview cadence is expected to select.
    """
    interval_start = max(0.0, float(start) - 0.1)
    interval_duration = max(0.2, float(duration) + 0.2)

    cmd = [
        "ffprobe",
        "-v", "error",
        "-read_intervals",
        f"{interval_start}%+{interval_duration}",
        "-select_streams", str(int(stream_index)),
        "-show_entries",
        "frame=best_effort_timestamp_time",
        "-of", "json",
        str(path),
    ]

    try:
        result = subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            text=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return []

    payload = json.loads(result.stdout)
    times = []

    for frame in payload.get("frames", []):
        value = frame.get("best_effort_timestamp_time")
        if value is None:
            continue

        try:
            t = float(value)
        except (TypeError, ValueError):
            continue

        if start - 0.1 <= t <= start + duration + 0.1:
            times.append(t)

    return sorted(times)


def preview_exposure_times(
    source_times,
    *,
    start,
    duration,
    output_fps,
):
    """
    Map each uniform preview output time to the nearest actual source-frame PTS.

    The FFmpeg fps filter uses timestamp-based frame selection. Nearest-source
    PTS is a close deterministic model of that selection and avoids applying
    IMU orientation at a synthetic time that falls between exposures.
    """
    count = max(1, int(round(float(duration) * float(output_fps))))

    targets = [
        float(start) + index / float(output_fps)
        for index in range(count)
    ]

    if not source_times:
        return targets, {
            "used_actual_pts": False,
            "mean_abs_mapping_error_ms": 0.0,
            "max_abs_mapping_error_ms": 0.0,
        }

    mapped = []
    errors = []
    cursor = 0

    for target in targets:
        while (
            cursor + 1 < len(source_times)
            and abs(source_times[cursor + 1] - target)
            <= abs(source_times[cursor] - target)
        ):
            cursor += 1

        chosen = source_times[cursor]
        mapped.append(chosen)
        errors.append(abs(chosen - target) * 1000.0)

    return mapped, {
        "used_actual_pts": True,
        "mean_abs_mapping_error_ms": (
            sum(errors) / len(errors)
            if errors else 0.0
        ),
        "max_abs_mapping_error_ms": max(errors) if errors else 0.0,
    }
