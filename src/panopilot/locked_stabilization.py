"""
Locked crop-backed residual stabilization for conventional PanoPilot output.

This mode is intentionally designed to remove wobble introduced by aggressive
per-frame similarity corrections.

Design rules:
- gyro remains authoritative for 3-axis rotation;
- the visual residual stage corrects TRANSLATION ONLY;
- no visual scale correction, so there is no zoom breathing;
- no visual rotation correction, so parallax cannot be misfit as image roll;
- each Clip gets one globally smooth polynomial camera path;
- crop feasibility is enforced with one temporally constant gain per Clip/pass,
  never per-frame clipping;
- two optional residual passes re-measure translation after the preceding
  correction, but all transforms remain translations and are composed before a
  single final full-resolution warp.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import subprocess
import time

import cv2
import numpy as np

from .extreme_stabilization import (
    _analyze_pass,
    _fill_invalid,
)


@dataclass(frozen=True)
class LockedStabilizationPlan:
    matrices: np.ndarray
    crop_percent: float
    diagnostics: dict


def _moving_median(values, radius=2):
    values = np.asarray(values, dtype=np.float64)
    if len(values) == 0 or radius <= 0:
        return values.copy()

    padded = np.pad(
        values,
        (radius, radius),
        mode="edge",
    )
    out = np.empty_like(values)

    for index in range(len(values)):
        out[index] = np.median(
            padded[index:index + 2 * radius + 1]
        )

    return out


def _robust_polynomial_target(path, degree=2):
    """Return a very smooth target path with robust outlier rejection."""
    path = np.asarray(path, dtype=np.float64)
    count = len(path)

    if count <= 1:
        return path.copy()

    degree = max(0, min(int(degree), count - 1))
    x = np.linspace(-1.0, 1.0, count, dtype=np.float64)
    keep = np.ones(count, dtype=bool)

    coefficients = np.polyfit(x, path, degree)

    # Two robust refinement rounds are enough for the occasional residual KLT
    # jump without turning this into an iterative image-deformation solver.
    for _ in range(2):
        predicted = np.polyval(coefficients, x)
        residual = path - predicted
        median = float(np.median(residual[keep]))
        mad = float(
            np.median(
                np.abs(residual[keep] - median)
            )
        )

        if mad <= 1e-9:
            break

        sigma = 1.4826 * mad
        new_keep = np.abs(residual - median) <= (3.5 * sigma)

        if int(new_keep.sum()) <= degree:
            break

        keep = new_keep
        coefficients = np.polyfit(
            x[keep],
            path[keep],
            degree,
        )

    return np.polyval(coefficients, x)


def _translation_correction(
    motion,
    frame_segments,
    *,
    amount,
):
    frame_count = len(motion["dx"])
    correction_dx = np.zeros(frame_count, dtype=np.float64)
    correction_dy = np.zeros(frame_count, dtype=np.float64)

    # Strong response at the upper end, but without altering the transform
    # model itself.
    amount = max(0.0, min(1.0, float(amount)))
    gain = 1.0 - (1.0 - amount) ** 3

    for start, count in frame_segments:
        start = int(start)
        count = int(count)
        end = start + count

        if count <= 0:
            continue

        local_dx = motion["dx"][start:end].copy()
        local_dy = motion["dy"][start:end].copy()

        local_dx = _fill_invalid(local_dx, np.isfinite(local_dx))
        local_dy = _fill_invalid(local_dy, np.isfinite(local_dy))

        # Suppress sub-frame tracking noise before integration. We still retain
        # genuine short-period camera movement because the final path target,
        # not this median, provides the strong stabilization.
        local_dx = _moving_median(local_dx, radius=2)
        local_dy = _moving_median(local_dy, radius=2)
        local_dx[0] = 0.0
        local_dy[0] = 0.0

        path_x = np.cumsum(local_dx)
        path_y = np.cumsum(local_dy)

        target_x = _robust_polynomial_target(path_x, degree=2)
        target_y = _robust_polynomial_target(path_y, degree=2)

        correction_x = (target_x - path_x) * gain
        correction_y = (target_y - path_y) * gain

        # Do not change framing at the exact hard-cut boundary. Subtracting a
        # constant does not affect stabilization smoothness.
        correction_x -= correction_x[0]
        correction_y -= correction_y[0]

        correction_dx[start:end] = correction_x
        correction_dy[start:end] = correction_y

    # Analysis coordinates -> delivery coordinates.
    correction_dx *= (
        float(motion["full_width"])
        / float(motion["analysis_width"])
    )
    correction_dy *= (
        float(motion["full_height"])
        / float(motion["analysis_height"])
    )

    return correction_dx, correction_dy, gain


def _segment_feasible_gain(
    accumulated_dx,
    accumulated_dy,
    new_dx,
    new_dy,
    start,
    end,
    *,
    margin_x,
    margin_y,
):
    """
    One gain for the entire segment.

    This is the key anti-wobble difference from 0.32: crop limits never change
    correction strength on adjacent frames independently.
    """
    if end <= start:
        return 1.0

    def fits(alpha):
        x = accumulated_dx[start:end] + alpha * new_dx[start:end]
        y = accumulated_dy[start:end] + alpha * new_dy[start:end]
        return (
            float(np.max(np.abs(x))) <= margin_x
            and float(np.max(np.abs(y))) <= margin_y
        )

    if fits(1.0):
        return 1.0

    if not fits(0.0):
        return 0.0

    lo = 0.0
    hi = 1.0

    for _ in range(30):
        mid = (lo + hi) / 2.0
        if fits(mid):
            lo = mid
        else:
            hi = mid

    return lo


def _translation_matrices(dx, dy):
    frame_count = len(dx)
    matrices = np.repeat(
        np.eye(3, dtype=np.float64)[None, ...],
        frame_count,
        axis=0,
    )
    matrices[:, 0, 2] = dx
    matrices[:, 1, 2] = dy
    return matrices


def analyze_locked_stabilization(
    input_video,
    frame_segments,
    *,
    amount,
    crop_percent=45.0,
    analysis_width=960,
    passes=2,
):
    input_video = Path(input_video)
    crop_percent = float(crop_percent)

    if not 0.0 <= crop_percent <= 60.0:
        raise ValueError(
            "crop_percent must be between 0 and 60 for locked stabilization"
        )

    cap = cv2.VideoCapture(str(input_video))
    if not cap.isOpened():
        raise RuntimeError(
            f"Could not open video for locked stabilization: {input_video}"
        )

    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
    cap.release()

    if frame_count <= 0 or width <= 0 or height <= 0 or fps <= 0.0:
        raise RuntimeError("Rendered video metadata is invalid")

    analysis_width = max(640, min(int(analysis_width), width))
    passes = max(1, min(3, int(passes)))

    accumulated_dx = np.zeros(frame_count, dtype=np.float64)
    accumulated_dy = np.zeros(frame_count, dtype=np.float64)

    # A fixed center crop creates a hard translation budget. Keep 96% of that
    # mathematical budget as a safety reserve for bilinear interpolation and
    # integer crop rounding.
    margin_x = float(width) * crop_percent / 200.0 * 0.96
    margin_y = float(height) * crop_percent / 200.0 * 0.96

    pass_diagnostics = []

    for pass_index in range(1, passes + 1):
        accumulated_matrices = _translation_matrices(
            accumulated_dx,
            accumulated_dy,
        )

        motion = _analyze_pass(
            input_video,
            frame_segments,
            accumulated_matrices if pass_index > 1 else None,
            analysis_width=analysis_width,
        )

        new_dx, new_dy, amount_gain = _translation_correction(
            motion,
            frame_segments,
            amount=amount,
        )

        segment_gains = []

        for start, count in frame_segments:
            start = int(start)
            end = start + int(count)

            segment_gain = _segment_feasible_gain(
                accumulated_dx,
                accumulated_dy,
                new_dx,
                new_dy,
                start,
                end,
                margin_x=margin_x,
                margin_y=margin_y,
            )
            segment_gains.append(float(segment_gain))
            accumulated_dx[start:end] += segment_gain * new_dx[start:end]
            accumulated_dy[start:end] += segment_gain * new_dy[start:end]

        translation = np.sqrt(
            motion["dx"] ** 2
            + motion["dy"] ** 2
        )
        finite = translation[np.isfinite(translation)]

        pass_diagnostics.append(
            {
                "pass": int(pass_index),
                "valid_motion_ratio": float(motion["valid_ratio"]),
                "mean_inlier_ratio": float(motion["mean_inlier_ratio"]),
                "median_fit_residual_px": float(
                    motion["median_fit_residual_px"]
                ),
                "median_input_translation_px_analysis": (
                    float(np.median(finite)) if len(finite) else 0.0
                ),
                "p95_input_translation_px_analysis": (
                    float(np.percentile(finite, 95)) if len(finite) else 0.0
                ),
                "amount_gain": float(amount_gain),
                "segment_crop_gains": segment_gains,
                "min_segment_crop_gain": (
                    float(min(segment_gains)) if segment_gains else 1.0
                ),
                "per_frame_crop_clipping": False,
                "visual_rotation_correction": False,
                "visual_scale_correction": False,
            }
        )

    matrices = _translation_matrices(
        accumulated_dx,
        accumulated_dy,
    )

    diagnostics = {
        "algorithm": "locked-translation-polynomial-v1",
        "mode": "locked",
        "fps": float(fps),
        "frame_count": int(frame_count),
        "width": int(width),
        "height": int(height),
        "analysis_width": int(analysis_width),
        "passes": int(passes),
        "amount": float(amount),
        "crop_percent": float(crop_percent),
        "retained_linear_fraction": float(1.0 - crop_percent / 100.0),
        "output_zoom": float(1.0 / max(1e-9, 1.0 - crop_percent / 100.0)),
        "transform_model": "translation-only-after-gyro",
        "visual_rotation_correction": False,
        "visual_scale_correction": False,
        "per_frame_crop_clipping": False,
        "crop_policy": "one-global-gain-per-clip-pass",
        "path_model": "robust-quadratic-per-clip",
        "single_final_image_warp": True,
        "max_translation_x_px": float(np.max(np.abs(accumulated_dx))),
        "max_translation_y_px": float(np.max(np.abs(accumulated_dy))),
        "translation_budget_x_px": float(margin_x),
        "translation_budget_y_px": float(margin_y),
        "pass_diagnostics": pass_diagnostics,
    }

    return LockedStabilizationPlan(
        matrices=matrices,
        crop_percent=float(crop_percent),
        diagnostics=diagnostics,
    )


def render_locked_stabilization(
    input_video,
    output_video,
    plan,
    *,
    crf=18,
    preset="medium",
    progress_callback=None,
):
    input_video = Path(input_video)
    output_video = Path(output_video)

    cap = cv2.VideoCapture(str(input_video))
    if not cap.isOpened():
        raise RuntimeError(f"Could not open locked stabilization input: {input_video}")

    fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)

    if frame_count != len(plan.matrices):
        cap.release()
        raise RuntimeError("Locked stabilization plan frame count does not match video")

    retain = 1.0 - plan.crop_percent / 100.0
    crop_width = max(2, int(round(width * retain)))
    crop_height = max(2, int(round(height * retain)))
    crop_width -= crop_width % 2
    crop_height -= crop_height % 2
    x0 = (width - crop_width) // 2
    y0 = (height - crop_height) // 2

    command = [
        "ffmpeg", "-y", "-v", "error",
        "-f", "rawvideo", "-pix_fmt", "bgr24",
        "-s", f"{width}x{height}", "-r", f"{fps:.9f}",
        "-i", "-", "-an",
        "-c:v", "libx264", "-preset", str(preset),
        "-crf", str(int(crf)), "-pix_fmt", "yuv420p",
        "-movflags", "+faststart", str(output_video),
    ]

    try:
        encoder = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except FileNotFoundError as exc:
        cap.release()
        raise RuntimeError("ffmpeg was not found") from exc

    started = time.perf_counter()

    try:
        for index in range(frame_count):
            ok, frame = cap.read()
            if not ok:
                raise RuntimeError(
                    "Locked stabilization render ended before expected frame "
                    f"{index}/{frame_count}"
                )

            warped = cv2.warpAffine(
                frame,
                plan.matrices[index][:2, :],
                (width, height),
                flags=cv2.INTER_LINEAR,
                borderMode=cv2.BORDER_REFLECT_101,
            )
            cropped = warped[
                y0:y0 + crop_height,
                x0:x0 + crop_width,
            ]
            stabilized = cv2.resize(
                cropped,
                (width, height),
                interpolation=cv2.INTER_LANCZOS4,
            )

            try:
                encoder.stdin.write(stabilized.tobytes())
            except BrokenPipeError as exc:
                raise RuntimeError(
                    "Locked stabilization H.264 encoder stopped unexpectedly"
                ) from exc

            if (
                progress_callback
                and (
                    index == 0
                    or index + 1 == frame_count
                    or (index + 1) % 15 == 0
                )
            ):
                progress_callback(
                    {
                        "stage": "locked-visual-stabilization",
                        "message": (
                            "Locked stabilization — "
                            f"{index + 1}/{frame_count} frames "
                            f"({100.0 * (index + 1) / frame_count:.1f}%)"
                        ),
                        "frame": index + 1,
                        "total_frames": frame_count,
                    }
                )
    finally:
        cap.release()
        if encoder.stdin:
            encoder.stdin.close()
        stderr = (
            encoder.stderr.read().decode("utf-8", "replace")
            if encoder.stderr
            else ""
        )
        encoder.wait()

    if encoder.returncode != 0:
        raise RuntimeError(
            "Locked stabilization H.264 encoding failed:\n" + stderr
        )

    return {
        **plan.diagnostics,
        "processing_seconds": float(time.perf_counter() - started),
        "encoder_crf": int(crf),
        "encoder_preset": str(preset),
    }


def stabilize_rendered_video_locked(
    input_video,
    output_video,
    frame_segments,
    *,
    amount,
    crop_percent=45.0,
    analysis_width=960,
    passes=2,
    crf=18,
    preset="medium",
    progress_callback=None,
):
    if progress_callback:
        progress_callback(
            {
                "stage": "locked-visual-analysis",
                "message": (
                    "Analyzing wobble-free locked stabilization "
                    f"({passes} translation-only pass{'es' if passes != 1 else ''})"
                ),
            }
        )

    analysis_started = time.perf_counter()
    plan = analyze_locked_stabilization(
        input_video,
        frame_segments,
        amount=amount,
        crop_percent=crop_percent,
        analysis_width=analysis_width,
        passes=passes,
    )
    analysis_seconds = time.perf_counter() - analysis_started

    if progress_callback:
        progress_callback(
            {
                "stage": "locked-visual-stabilization",
                "message": (
                    "Applying locked translation stabilization with "
                    f"{crop_percent:.0f}% crop reserve"
                ),
            }
        )

    result = render_locked_stabilization(
        input_video,
        output_video,
        plan,
        crf=crf,
        preset=preset,
        progress_callback=progress_callback,
    )
    result["analysis_seconds"] = float(analysis_seconds)
    result["total_seconds"] = float(
        analysis_seconds + result["processing_seconds"]
    )
    return result
