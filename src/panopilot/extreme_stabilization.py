"""
Extreme crop-backed residual stabilization for conventional PanoPilot output.

This is deliberately stronger than the 0.31 single-pass similarity smoother.

Key changes:
- high-resolution KLT analysis with forward/backward consistency rejection;
- robust RANSAC similarity estimation;
- three offline residual-analysis passes;
- each pass re-analyzes the virtually corrected image, so remaining jitter is
  measured rather than assumed removed;
- translation, rotation, and short-term scale jitter are stabilized;
- all pass corrections are composed and the source image is warped only once;
- the full accumulated correction is constrained by the requested crop reserve.

The accepted gyro/direct rendering stages remain unchanged.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import math
import subprocess
import time

import cv2
import numpy as np

from .video_encoding import video_encoder_command


@dataclass(frozen=True)
class ExtremeStabilizationPlan:
    matrices: np.ndarray
    crop_percent: float
    analysis_width: int
    analysis_height: int
    diagnostics: dict


def _gaussian_smooth(values, sigma_frames):
    values = np.asarray(
        values,
        dtype=np.float64,
    )
    sigma = float(
        sigma_frames
    )

    if (
        len(values) == 0
        or sigma <= 1e-9
    ):
        return values.copy()

    radius = max(
        1,
        int(
            math.ceil(
                3.0 * sigma
            )
        ),
    )
    x = np.arange(
        -radius,
        radius + 1,
        dtype=np.float64,
    )
    kernel = np.exp(
        -0.5
        * (
            x / sigma
        ) ** 2
    )
    kernel /= kernel.sum()

    padded = np.pad(
        values,
        (
            radius,
            radius,
        ),
        mode="edge",
    )

    return np.convolve(
        padded,
        kernel,
        mode="valid",
    )


def _fill_invalid(values, valid):
    values = np.asarray(
        values,
        dtype=np.float64,
    )
    valid = np.asarray(
        valid,
        dtype=bool,
    )

    if len(values) == 0:
        return values.copy()

    indices = np.arange(
        len(values),
        dtype=np.float64,
    )
    good = np.flatnonzero(
        valid
        & np.isfinite(
            values
        )
    )

    if len(good) == 0:
        return np.zeros_like(
            values
        )

    if len(good) == 1:
        return np.full_like(
            values,
            float(
                values[
                    good[
                        0
                    ]
                ]
            ),
        )

    return np.interp(
        indices,
        good.astype(
            np.float64
        ),
        values[
            good
        ],
    )


def _estimate_similarity_motion(
    previous_gray,
    current_gray,
):
    height, width = (
        previous_gray.shape[
            :2
        ]
    )

    mask = np.zeros_like(
        previous_gray,
        dtype=np.uint8,
    )
    border_x = max(
        10,
        int(
            round(
                width * 0.04
            )
        ),
    )
    border_y = max(
        10,
        int(
            round(
                height * 0.04
            )
        ),
    )
    mask[
        border_y:height-border_y,
        border_x:width-border_x,
    ] = 255

    points = cv2.goodFeaturesToTrack(
        previous_gray,
        maxCorners=1400,
        qualityLevel=0.006,
        minDistance=5,
        blockSize=7,
        mask=mask,
    )

    if (
        points is None
        or len(points) < 30
    ):
        return None

    next_points, status, _error = (
        cv2.calcOpticalFlowPyrLK(
            previous_gray,
            current_gray,
            points,
            None,
            winSize=(
                31,
                31,
            ),
            maxLevel=4,
            criteria=(
                cv2.TERM_CRITERIA_EPS
                | cv2.TERM_CRITERIA_COUNT,
                40,
                0.005,
            ),
        )
    )

    if (
        next_points is None
        or status is None
    ):
        return None

    # Forward/backward consistency is important in water, foliage, walking
    # footage, and scenes with independently moving objects.
    back_points, back_status, _back_error = (
        cv2.calcOpticalFlowPyrLK(
            current_gray,
            previous_gray,
            next_points,
            None,
            winSize=(
                31,
                31,
            ),
            maxLevel=4,
            criteria=(
                cv2.TERM_CRITERIA_EPS
                | cv2.TERM_CRITERIA_COUNT,
                40,
                0.005,
            ),
        )
    )

    if (
        back_points is None
        or back_status is None
    ):
        return None

    p0 = points.reshape(
        -1,
        2,
    )
    p1 = next_points.reshape(
        -1,
        2,
    )
    pb = back_points.reshape(
        -1,
        2,
    )

    forward_ok = (
        status.reshape(
            -1
        )
        == 1
    )
    backward_ok = (
        back_status.reshape(
            -1
        )
        == 1
    )
    round_trip = np.linalg.norm(
        pb - p0,
        axis=1,
    )

    keep = (
        forward_ok
        & backward_ok
        & (
            round_trip
            <= 0.9
        )
    )
    p0 = p0[
        keep
    ]
    p1 = p1[
        keep
    ]

    if len(p0) < 30:
        return None

    matrix, inliers = (
        cv2.estimateAffinePartial2D(
            p0,
            p1,
            method=cv2.RANSAC,
            ransacReprojThreshold=1.2,
            maxIters=5000,
            confidence=0.999,
            refineIters=20,
        )
    )

    if matrix is None:
        return None

    if inliers is None:
        inlier_mask = np.ones(
            len(p0),
            dtype=bool,
        )
    else:
        inlier_mask = (
            inliers.reshape(
                -1
            )
            == 1
        )

    inlier_count = int(
        inlier_mask.sum()
    )
    inlier_ratio = float(
        inlier_count
        / max(
            1,
            len(p0),
        )
    )

    if (
        inlier_count < 25
        or inlier_ratio < 0.20
    ):
        return None

    a = float(
        matrix[
            0,
            0,
        ]
    )
    b = float(
        matrix[
            1,
            0,
        ]
    )
    scale = math.sqrt(
        a * a
        + b * b
    )
    angle_deg = math.degrees(
        math.atan2(
            b,
            a,
        )
    )

    if (
        not 0.88
        <= scale
        <= 1.12
        or abs(
            angle_deg
        )
        > 12.0
    ):
        return None

    p0_h = np.column_stack(
        (
            p0,
            np.ones(
                len(p0),
                dtype=np.float64,
            ),
        )
    )
    predicted = (
        matrix
        @ p0_h.T
    ).T
    median_residual = float(
        np.median(
            np.linalg.norm(
                predicted[
                    inlier_mask
                ]
                - p1[
                    inlier_mask
                ],
                axis=1,
            )
        )
    )

    if median_residual > 1.6:
        return None

    center = np.array(
        [
            width / 2.0,
            height / 2.0,
            1.0,
        ],
        dtype=np.float64,
    )
    moved = (
        matrix
        @ center
    )

    return {
        "dx": float(
            moved[
                0
            ]
            - center[
                0
            ]
        ),
        "dy": float(
            moved[
                1
            ]
            - center[
                1
            ]
        ),
        "angle_deg": float(
            angle_deg
        ),
        "log_scale": float(
            math.log(
                max(
                    scale,
                    1e-9,
                )
            )
        ),
        "inlier_ratio": float(
            inlier_ratio
        ),
        "median_residual_px": float(
            median_residual
        ),
    }


def _correction_matrix(
    width,
    height,
    dx,
    dy,
    angle_deg,
    log_scale=0.0,
    *,
    alpha=1.0,
):
    alpha = float(
        alpha
    )
    scale = math.exp(
        float(
            log_scale
        )
        * alpha
    )

    matrix = (
        cv2.getRotationMatrix2D(
            (
                width / 2.0,
                height / 2.0,
            ),
            -float(
                angle_deg
            )
            * alpha,
            scale,
        )
    )
    matrix[
        0,
        2,
    ] += float(
        dx
    ) * alpha
    matrix[
        1,
        2,
    ] += float(
        dy
    ) * alpha

    homogeneous = np.eye(
        3,
        dtype=np.float64,
    )
    homogeneous[
        :2,
        :
    ] = matrix

    return homogeneous


def _crop_corners(
    width,
    height,
    crop_percent,
):
    retain = (
        1.0
        - float(
            crop_percent
        )
        / 100.0
    )
    crop_width = (
        float(
            width
        )
        * retain
    )
    crop_height = (
        float(
            height
        )
        * retain
    )
    x0 = (
        float(
            width
        )
        - crop_width
    ) / 2.0
    y0 = (
        float(
            height
        )
        - crop_height
    ) / 2.0

    return np.array(
        [
            [
                x0,
                y0,
            ],
            [
                x0 + crop_width,
                y0,
            ],
            [
                x0 + crop_width,
                y0 + crop_height,
            ],
            [
                x0,
                y0 + crop_height,
            ],
        ],
        dtype=np.float32,
    )


def _matrix_fits_crop(
    matrix,
    width,
    height,
    crop_percent,
):
    source = np.array(
        [
            [
                0.0,
                0.0,
                1.0,
            ],
            [
                float(
                    width
                ),
                0.0,
                1.0,
            ],
            [
                float(
                    width
                ),
                float(
                    height
                ),
                1.0,
            ],
            [
                0.0,
                float(
                    height
                ),
                1.0,
            ],
        ],
        dtype=np.float64,
    )
    polygon = (
        matrix
        @ source.T
    ).T[
        :,
        :2
    ].astype(
        np.float32
    )
    crop = _crop_corners(
        width,
        height,
        crop_percent,
    )

    return all(
        cv2.pointPolygonTest(
            polygon,
            tuple(
                map(
                    float,
                    point,
                )
            ),
            False,
        )
        >= -1e-4
        for point in crop
    )


def _scaled_for_analysis(
    matrix,
    full_width,
    analysis_width,
):
    scale = (
        float(
            analysis_width
        )
        / float(
            full_width
        )
    )
    to_analysis = np.array(
        [
            [
                scale,
                0.0,
                0.0,
            ],
            [
                0.0,
                scale,
                0.0,
            ],
            [
                0.0,
                0.0,
                1.0,
            ],
        ],
        dtype=np.float64,
    )
    to_full = np.array(
        [
            [
                1.0 / scale,
                0.0,
                0.0,
            ],
            [
                0.0,
                1.0 / scale,
                0.0,
            ],
            [
                0.0,
                0.0,
                1.0,
            ],
        ],
        dtype=np.float64,
    )

    return (
        to_analysis
        @ matrix
        @ to_full
    )


def _analyze_pass(
    input_video,
    frame_segments,
    accumulated,
    *,
    analysis_width,
):
    cap = cv2.VideoCapture(
        str(
            input_video
        )
    )

    if not cap.isOpened():
        raise RuntimeError(
            f"Could not open video for extreme stabilization: {input_video}"
        )

    frame_count = int(
        cap.get(
            cv2.CAP_PROP_FRAME_COUNT
        )
        or 0
    )
    full_width = int(
        cap.get(
            cv2.CAP_PROP_FRAME_WIDTH
        )
        or 0
    )
    full_height = int(
        cap.get(
            cv2.CAP_PROP_FRAME_HEIGHT
        )
        or 0
    )
    analysis_width = max(
        320,
        min(
            int(
                analysis_width
            ),
            full_width,
        ),
    )
    analysis_height = max(
        180,
        int(
            round(
                full_height
                * analysis_width
                / full_width
            )
        ),
    )

    segment_starts = {
        int(
            start
        )
        for start, _count
        in frame_segments
    }

    dx = np.full(
        frame_count,
        np.nan,
        dtype=np.float64,
    )
    dy = np.full_like(
        dx,
        np.nan,
    )
    angle = np.full_like(
        dx,
        np.nan,
    )
    log_scale = np.full_like(
        dx,
        np.nan,
    )
    inlier_ratios = []
    residuals = []

    previous_gray = None

    for frame_index in range(
        frame_count
    ):
        ok, frame = cap.read()

        if not ok:
            cap.release()
            raise RuntimeError(
                "Extreme visual analysis ended before expected frame "
                f"{frame_index}/{frame_count}"
            )

        small = cv2.resize(
            frame,
            (
                analysis_width,
                analysis_height,
            ),
            interpolation=cv2.INTER_AREA,
        )

        if accumulated is not None:
            analysis_matrix = (
                _scaled_for_analysis(
                    accumulated[
                        frame_index
                    ],
                    full_width,
                    analysis_width,
                )
            )
            small = cv2.warpAffine(
                small,
                analysis_matrix[
                    :2,
                    :
                ],
                (
                    analysis_width,
                    analysis_height,
                ),
                flags=cv2.INTER_LINEAR,
                borderMode=cv2.BORDER_REFLECT_101,
            )

        gray = cv2.cvtColor(
            small,
            cv2.COLOR_BGR2GRAY,
        )

        if frame_index in segment_starts:
            previous_gray = gray
            dx[
                frame_index
            ] = 0.0
            dy[
                frame_index
            ] = 0.0
            angle[
                frame_index
            ] = 0.0
            log_scale[
                frame_index
            ] = 0.0
            continue

        estimate = (
            _estimate_similarity_motion(
                previous_gray,
                gray,
            )
            if previous_gray is not None
            else None
        )

        if estimate is not None:
            dx[
                frame_index
            ] = estimate[
                "dx"
            ]
            dy[
                frame_index
            ] = estimate[
                "dy"
            ]
            angle[
                frame_index
            ] = estimate[
                "angle_deg"
            ]
            log_scale[
                frame_index
            ] = estimate[
                "log_scale"
            ]
            inlier_ratios.append(
                estimate[
                    "inlier_ratio"
                ]
            )
            residuals.append(
                estimate[
                    "median_residual_px"
                ]
            )

        previous_gray = gray

    cap.release()

    return {
        "dx": dx,
        "dy": dy,
        "angle_deg": angle,
        "log_scale": log_scale,
        "analysis_width": int(
            analysis_width
        ),
        "analysis_height": int(
            analysis_height
        ),
        "full_width": int(
            full_width
        ),
        "full_height": int(
            full_height
        ),
        "valid_ratio": float(
            np.mean(
                np.isfinite(
                    dx
                )
            )
        ),
        "mean_inlier_ratio": (
            float(
                np.mean(
                    inlier_ratios
                )
            )
            if inlier_ratios
            else 0.0
        ),
        "median_fit_residual_px": (
            float(
                np.median(
                    residuals
                )
            )
            if residuals
            else 0.0
        ),
    }


def _pass_parameters(
    motion,
    frame_segments,
    *,
    fps,
    amount,
    sigma_seconds,
):
    frame_count = len(
        motion[
            "dx"
        ]
    )
    correction_dx = np.zeros(
        frame_count,
        dtype=np.float64,
    )
    correction_dy = np.zeros_like(
        correction_dx
    )
    correction_angle = np.zeros_like(
        correction_dx
    )
    correction_log_scale = np.zeros_like(
        correction_dx
    )

    sigma_frames = max(
        0.5,
        float(
            sigma_seconds
        )
        * float(
            fps
        ),
    )
    gain = (
        1.0
        - (
            1.0
            - max(
                0.0,
                min(
                    1.0,
                    float(
                        amount
                    ),
                ),
            )
        ) ** 3
    )

    for start, count in frame_segments:
        start = int(
            start
        )
        count = int(
            count
        )
        end = (
            start
            + count
        )

        if count <= 0:
            continue

        channels = (
            (
                motion[
                    "dx"
                ],
                correction_dx,
            ),
            (
                motion[
                    "dy"
                ],
                correction_dy,
            ),
            (
                motion[
                    "angle_deg"
                ],
                correction_angle,
            ),
            (
                motion[
                    "log_scale"
                ],
                correction_log_scale,
            ),
        )

        for source, destination in channels:
            local = source[
                start:end
            ].copy()
            valid = np.isfinite(
                local
            )
            local = _fill_invalid(
                local,
                valid,
            )
            local[
                0
            ] = 0.0

            path = np.cumsum(
                local
            )
            smooth = (
                _gaussian_smooth(
                    path,
                    sigma_frames,
                )
            )

            destination[
                start:end
            ] = (
                smooth
                - path
            ) * gain

    # Convert translation from analysis coordinates to delivery coordinates.
    x_scale = (
        float(
            motion[
                "full_width"
            ]
        )
        / float(
            motion[
                "analysis_width"
            ]
        )
    )
    y_scale = (
        float(
            motion[
                "full_height"
            ]
        )
        / float(
            motion[
                "analysis_height"
            ]
        )
    )
    correction_dx *= x_scale
    correction_dy *= y_scale

    # We want to remove high-frequency zoom jitter, not rewrite deliberate
    # framing. Limit one pass to +/- 7.5% scale correction.
    max_log_scale = math.log(
        1.075
    )
    np.clip(
        correction_log_scale,
        -max_log_scale,
        max_log_scale,
        out=(
            correction_log_scale
        ),
    )

    return {
        "dx": correction_dx,
        "dy": correction_dy,
        "angle_deg": (
            correction_angle
        ),
        "log_scale": (
            correction_log_scale
        ),
        "sigma_seconds": float(
            sigma_seconds
        ),
        "sigma_frames": float(
            sigma_frames
        ),
        "gain": float(
            gain
        ),
    }


def _compose_pass(
    accumulated,
    parameters,
    *,
    width,
    height,
    crop_percent,
):
    frame_count = len(
        parameters[
            "dx"
        ]
    )
    if accumulated is None:
        accumulated = np.repeat(
            np.eye(
                3,
                dtype=np.float64,
            )[
                None,
                ...,
            ],
            frame_count,
            axis=0,
        )

    output = np.empty_like(
        accumulated
    )
    applied = np.ones(
        frame_count,
        dtype=np.float64,
    )

    for index in range(
        frame_count
    ):
        def candidate(alpha):
            delta = _correction_matrix(
                width,
                height,
                parameters[
                    "dx"
                ][
                    index
                ],
                parameters[
                    "dy"
                ][
                    index
                ],
                parameters[
                    "angle_deg"
                ][
                    index
                ],
                parameters[
                    "log_scale"
                ][
                    index
                ],
                alpha=alpha,
            )
            return (
                delta
                @ accumulated[
                    index
                ]
            )

        full = candidate(
            1.0
        )

        if _matrix_fits_crop(
            full,
            width,
            height,
            crop_percent,
        ):
            output[
                index
            ] = full
            continue

        # Keep all previous-pass stabilization and only reduce the new residual
        # correction until the full composed transform fits the crop.
        if not _matrix_fits_crop(
            accumulated[
                index
            ],
            width,
            height,
            crop_percent,
        ):
            # Defensive fallback. Previous pass should already be feasible.
            output[
                index
            ] = accumulated[
                index
            ]
            applied[
                index
            ] = 0.0
            continue

        lo = 0.0
        hi = 1.0

        for _ in range(
            16
        ):
            mid = (
                lo
                + hi
            ) / 2.0

            if _matrix_fits_crop(
                candidate(
                    mid
                ),
                width,
                height,
                crop_percent,
            ):
                lo = mid
            else:
                hi = mid

        applied[
            index
        ] = lo
        output[
            index
        ] = candidate(
            lo
        )

    return (
        output,
        applied,
    )


def analyze_extreme_stabilization(
    input_video,
    frame_segments,
    *,
    amount,
    crop_percent=45.0,
    analysis_width=960,
    passes=3,
):
    input_video = Path(
        input_video
    )
    amount = max(
        0.0,
        min(
            1.0,
            float(
                amount
            ),
        ),
    )
    crop_percent = float(
        crop_percent
    )

    if not 0.0 <= crop_percent <= 60.0:
        raise ValueError(
            "crop_percent must be between 0 and 60 for extreme stabilization"
        )

    cap = cv2.VideoCapture(
        str(
            input_video
        )
    )

    if not cap.isOpened():
        raise RuntimeError(
            f"Could not open rendered video for extreme stabilization: {input_video}"
        )

    fps = float(
        cap.get(
            cv2.CAP_PROP_FPS
        )
        or 0.0
    )
    frame_count = int(
        cap.get(
            cv2.CAP_PROP_FRAME_COUNT
        )
        or 0
    )
    width = int(
        cap.get(
            cv2.CAP_PROP_FRAME_WIDTH
        )
        or 0
    )
    height = int(
        cap.get(
            cv2.CAP_PROP_FRAME_HEIGHT
        )
        or 0
    )
    cap.release()

    if (
        fps <= 0.0
        or frame_count <= 0
        or width <= 0
        or height <= 0
    ):
        raise RuntimeError(
            "Rendered video metadata is invalid for extreme stabilization"
        )

    passes = max(
        1,
        min(
            4,
            int(
                passes
            ),
        ),
    )
    analysis_width = max(
        640,
        min(
            int(
                analysis_width
            ),
            width,
        ),
    )

    # Long first pass removes low-frequency walking/bobbing; later passes are
    # residual refinements. At lower User amounts, shorten all windows.
    full_schedule = (
        1.80,
        1.05,
        0.60,
        0.35,
    )
    amount_scale = (
        0.35
        + 0.65
        * amount
    )
    schedule = [
        full_schedule[
            index
        ]
        * amount_scale
        for index in range(
            passes
        )
    ]

    accumulated = None
    pass_diagnostics = []

    for pass_index, sigma_seconds in enumerate(
        schedule,
        start=1,
    ):
        motion = _analyze_pass(
            input_video,
            frame_segments,
            accumulated,
            analysis_width=(
                analysis_width
            ),
        )

        parameters = _pass_parameters(
            motion,
            frame_segments,
            fps=fps,
            amount=amount,
            sigma_seconds=(
                sigma_seconds
            ),
        )

        accumulated, applied = (
            _compose_pass(
                accumulated,
                parameters,
                width=width,
                height=height,
                crop_percent=(
                    crop_percent
                ),
            )
        )

        translation = np.sqrt(
            motion[
                "dx"
            ] ** 2
            + motion[
                "dy"
            ] ** 2
        )
        finite_translation = translation[
            np.isfinite(
                translation
            )
        ]
        finite_angle = np.abs(
            motion[
                "angle_deg"
            ][
                np.isfinite(
                    motion[
                        "angle_deg"
                    ]
                )
            ]
        )
        finite_scale = np.abs(
            np.exp(
                motion[
                    "log_scale"
                ][
                    np.isfinite(
                        motion[
                            "log_scale"
                        ]
                    )
                ]
            )
            - 1.0
        )

        pass_diagnostics.append(
            {
                "pass": int(
                    pass_index
                ),
                "sigma_seconds": float(
                    sigma_seconds
                ),
                "valid_motion_ratio": float(
                    motion[
                        "valid_ratio"
                    ]
                ),
                "mean_inlier_ratio": float(
                    motion[
                        "mean_inlier_ratio"
                    ]
                ),
                "median_fit_residual_px": float(
                    motion[
                        "median_fit_residual_px"
                    ]
                ),
                "median_input_translation_px_analysis": (
                    float(
                        np.median(
                            finite_translation
                        )
                    )
                    if len(
                        finite_translation
                    )
                    else 0.0
                ),
                "p95_input_translation_px_analysis": (
                    float(
                        np.percentile(
                            finite_translation,
                            95,
                        )
                    )
                    if len(
                        finite_translation
                    )
                    else 0.0
                ),
                "p95_input_rotation_deg": (
                    float(
                        np.percentile(
                            finite_angle,
                            95,
                        )
                    )
                    if len(
                        finite_angle
                    )
                    else 0.0
                ),
                "p95_input_scale_change": (
                    float(
                        np.percentile(
                            finite_scale,
                            95,
                        )
                    )
                    if len(
                        finite_scale
                    )
                    else 0.0
                ),
                "mean_applied_ratio": float(
                    np.mean(
                        applied
                    )
                ),
                "p05_applied_ratio": float(
                    np.percentile(
                        applied,
                        5,
                    )
                ),
                "crop_limited_frames": int(
                    np.sum(
                        applied
                        < 0.999
                    )
                ),
            }
        )

    if accumulated is None:
        accumulated = np.repeat(
            np.eye(
                3,
                dtype=np.float64,
            )[
                None,
                ...,
            ],
            frame_count,
            axis=0,
        )

    diagnostics = {
        "algorithm": (
            "extreme-iterative-klt-fb-ransac-similarity-v2"
        ),
        "mode": "extreme",
        "fps": float(
            fps
        ),
        "frame_count": int(
            frame_count
        ),
        "width": int(
            width
        ),
        "height": int(
            height
        ),
        "analysis_width": int(
            analysis_width
        ),
        "analysis_height": int(
            round(
                height
                * analysis_width
                / width
            )
        ),
        "passes": int(
            passes
        ),
        "amount": float(
            amount
        ),
        "crop_percent": float(
            crop_percent
        ),
        "retained_linear_fraction": float(
            1.0
            - crop_percent
            / 100.0
        ),
        "output_zoom": float(
            1.0
            / max(
                1e-9,
                1.0
                - crop_percent
                / 100.0,
            )
        ),
        "single_final_image_warp": True,
        "pass_diagnostics": (
            pass_diagnostics
        ),
    }

    return ExtremeStabilizationPlan(
        matrices=accumulated,
        crop_percent=float(
            crop_percent
        ),
        analysis_width=int(
            analysis_width
        ),
        analysis_height=int(
            diagnostics[
                "analysis_height"
            ]
        ),
        diagnostics=diagnostics,
    )


def render_extreme_stabilization(
    input_video,
    output_video,
    plan,
    *,
    crf=18,
    preset="medium",
    progress_callback=None,
):
    input_video = Path(
        input_video
    )
    output_video = Path(
        output_video
    )

    cap = cv2.VideoCapture(
        str(
            input_video
        )
    )

    if not cap.isOpened():
        raise RuntimeError(
            f"Could not open extreme stabilization input: {input_video}"
        )

    fps = float(
        cap.get(
            cv2.CAP_PROP_FPS
        )
        or 0.0
    )
    frame_count = int(
        cap.get(
            cv2.CAP_PROP_FRAME_COUNT
        )
        or 0
    )
    width = int(
        cap.get(
            cv2.CAP_PROP_FRAME_WIDTH
        )
        or 0
    )
    height = int(
        cap.get(
            cv2.CAP_PROP_FRAME_HEIGHT
        )
        or 0
    )

    if frame_count != len(
        plan.matrices
    ):
        cap.release()
        raise RuntimeError(
            "Extreme stabilization plan frame count does not match video"
        )

    retain = (
        1.0
        - plan.crop_percent
        / 100.0
    )
    crop_width = max(
        2,
        int(
            round(
                width
                * retain
            )
        ),
    )
    crop_height = max(
        2,
        int(
            round(
                height
                * retain
            )
        ),
    )
    crop_width -= (
        crop_width
        % 2
    )
    crop_height -= (
        crop_height
        % 2
    )
    x0 = (
        width
        - crop_width
    ) // 2
    y0 = (
        height
        - crop_height
    ) // 2

    command = video_encoder_command(
        output_video, width=width, height=height, fps=fps,
        crf=crf, preset=preset,
    )

    try:
        encoder = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except FileNotFoundError as exc:
        cap.release()
        raise RuntimeError(
            "ffmpeg was not found"
        ) from exc

    started = time.perf_counter()

    try:
        for index in range(
            frame_count
        ):
            ok, frame = cap.read()

            if not ok:
                raise RuntimeError(
                    "Extreme stabilization render ended before expected frame "
                    f"{index}/{frame_count}"
                )

            warped = cv2.warpAffine(
                frame,
                plan.matrices[
                    index
                ][
                    :2,
                    :
                ],
                (
                    width,
                    height,
                ),
                flags=cv2.INTER_LINEAR,
                borderMode=(
                    cv2.BORDER_REFLECT_101
                ),
            )
            cropped = warped[
                y0:y0+crop_height,
                x0:x0+crop_width,
            ]
            stabilized = cv2.resize(
                cropped,
                (
                    width,
                    height,
                ),
                interpolation=(
                    cv2.INTER_LANCZOS4
                ),
            )

            try:
                encoder.stdin.write(
                    stabilized.tobytes()
                )
            except BrokenPipeError as exc:
                raise RuntimeError(
                    "Extreme stabilization H.264 encoder stopped unexpectedly"
                ) from exc

            if (
                progress_callback
                and (
                    index == 0
                    or index + 1
                    == frame_count
                    or (
                        index + 1
                    ) % 15
                    == 0
                )
            ):
                progress_callback(
                    {
                        "stage": (
                            "extreme-visual-stabilization"
                        ),
                        "message": (
                            "Extreme stabilization — "
                            f"{index+1}/{frame_count} frames "
                            f"({100.0*(index+1)/frame_count:.1f}%)"
                        ),
                        "frame": (
                            index + 1
                        ),
                        "total_frames": (
                            frame_count
                        ),
                    }
                )

    finally:
        cap.release()

        if encoder.stdin:
            encoder.stdin.close()

        stderr = (
            encoder.stderr.read().decode(
                "utf-8",
                "replace",
            )
            if encoder.stderr
            else ""
        )
        encoder.wait()

    if encoder.returncode != 0:
        raise RuntimeError(
            "Extreme stabilization H.264 encoding failed:\n"
            + stderr
        )

    return {
        **plan.diagnostics,
        "processing_seconds": float(
            time.perf_counter()
            - started
        ),
        "encoder_crf": int(
            crf
        ),
        "encoder_preset": str(
            preset
        ),
    }


def stabilize_rendered_video_extreme(
    input_video,
    output_video,
    frame_segments,
    *,
    amount,
    crop_percent=45.0,
    analysis_width=960,
    passes=3,
    crf=18,
    preset="medium",
    progress_callback=None,
):
    if progress_callback:
        progress_callback(
            {
                "stage": (
                    "extreme-visual-analysis"
                ),
                "message": (
                    "Analyzing extreme residual stabilization "
                    f"({passes} iterative passes)"
                ),
            }
        )

    analysis_started = (
        time.perf_counter()
    )

    plan = analyze_extreme_stabilization(
        input_video,
        frame_segments,
        amount=amount,
        crop_percent=crop_percent,
        analysis_width=(
            analysis_width
        ),
        passes=passes,
    )

    analysis_seconds = (
        time.perf_counter()
        - analysis_started
    )

    if progress_callback:
        progress_callback(
            {
                "stage": (
                    "extreme-visual-stabilization"
                ),
                "message": (
                    "Applying extreme stabilization with "
                    f"{crop_percent:.0f}% crop reserve"
                ),
            }
        )

    result = render_extreme_stabilization(
        input_video,
        output_video,
        plan,
        crf=crf,
        preset=preset,
        progress_callback=(
            progress_callback
        ),
    )
    result[
        "analysis_seconds"
    ] = float(
        analysis_seconds
    )
    result[
        "total_seconds"
    ] = float(
        analysis_seconds
        + result[
            "processing_seconds"
        ]
    )

    return result
