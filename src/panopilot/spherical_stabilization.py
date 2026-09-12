"""
360-aware visual camera-path stabilization.

PanoPilot 0.36 retains the dominant residual as a *rigid visual camera* problem
on the captured sphere, not as a crop/mesh problem on the finished 16:9 frame.

The 0.34 implementation only estimated image-space X/Y motion and therefore
threw away residual visual rotation. That omission is important on walking
footage: a 1–2 degree frame-to-frame roll oscillation is very visible even when
yaw/pitch translation is already improved.

The rigid visual pass estimates an image-plane transform (translation + roll,
explicitly discarding scale) from forward/backward-validated KLT tracks. The
high-frequency part of all three residual channels is then converted to
Virtual Camera yaw/pitch/roll correction and applied during a second render
from the original 360 source.

The flexible anchored mesh is no longer part of the default spherical mode. It
remains available explicitly because a spatially flexible model can help true
parallax/rolling-shutter residuals, but it can also re-introduce the very
rubber/rotation wobble we are trying to remove.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import math

import cv2
import numpy as np

from .anchored_stabilization import (
    _gaussian_smooth,
    _zero_endpoint_baseline,
)


@dataclass(frozen=True)
class SphericalCameraPlan:
    # Columns: delivery-pixel dx, delivery-pixel dy, roll correction in degrees.
    camera_corrections: np.ndarray
    diagnostics: dict

    @property
    def pixel_corrections(self):
        """Backward-compatible alias used by the 0.34 export orchestration."""
        return self.camera_corrections


def _fill_vector_series(values, valid):
    values = np.asarray(values, dtype=np.float64).copy()
    valid = np.asarray(valid, dtype=bool)
    count = len(values)
    x = np.arange(count, dtype=np.float64)

    if values.ndim != 2:
        raise ValueError("values must be an NxM array")

    for component in range(values.shape[1]):
        good = np.flatnonzero(
            valid & np.isfinite(values[:, component])
        )
        if len(good) >= 2:
            values[:, component] = np.interp(
                x,
                good.astype(np.float64),
                values[good, component],
            )
        elif len(good) == 1:
            values[:, component] = values[good[0], component]
        else:
            values[:, component] = 0.0

    return values


def _rotation_angle_deg(matrix):
    a = float(matrix[0, 0])
    b = float(matrix[1, 0])
    return math.degrees(
        math.atan2(
            b,
            a,
        )
    )


def _estimate_band_rotation(p0, p1, mask):
    if int(np.sum(mask)) < 18:
        return None

    matrix, inliers = cv2.estimateAffinePartial2D(
        p0[mask],
        p1[mask],
        method=cv2.RANSAC,
        ransacReprojThreshold=1.25,
        maxIters=2500,
        confidence=0.999,
        refineIters=10,
    )

    if matrix is None:
        return None

    if inliers is not None and int(np.sum(inliers)) < 12:
        return None

    return float(
        _rotation_angle_deg(
            matrix
        )
    )



def _roll_coherence_weight(
    top_bottom_difference,
    left_right_difference,
):
    """
    Reliability of a single global visual roll estimate.

    A rigid roll is trustworthy only when spatial bands agree. Large
    top/bottom or left/right disagreement is evidence for rolling shutter,
    parallax, stitching deformation, or local foreground motion. In those
    cases the high-rate gyro remains the safer orientation authority and the
    visual roll correction is smoothly attenuated instead of creating a
    frame-wide rocking wobble.
    """
    values = [
        abs(
            float(value)
        )
        for value in (
            top_bottom_difference,
            left_right_difference,
        )
        if value is not None
        and math.isfinite(
            float(value)
        )
    ]

    if not values:
        return 1.0

    disagreement = max(values)
    reference_deg = 0.55
    ratio = (
        disagreement
        / reference_deg
    )

    return float(
        1.0
        / (
            1.0
            + ratio ** 4
        )
    )


def _spatial_coverage(q0, width, height):
    """Return the fraction of a 3x3 image grid represented by inliers."""
    if len(q0) == 0:
        return 0.0
    columns = np.clip(
        (q0[:, 0] * 3.0 / max(float(width), 1.0)).astype(int),
        0,
        2,
    )
    rows = np.clip(
        (q0[:, 1] * 3.0 / max(float(height), 1.0)).astype(int),
        0,
        2,
    )
    return float(len(np.unique(rows * 3 + columns)) / 9.0)


def _suppress_pairwise_outliers(relative_motion):
    """Suppress isolated optical-flow spikes without flattening real motion."""
    motion = np.asarray(relative_motion, dtype=np.float64).copy()
    if len(motion) < 5:
        return motion, 0

    # A short robust window handles a moving foreground object or a transient
    # tracker failure. Floors retain deliberate camera moves in low-noise shots.
    floors = np.array([1.25, 1.25, 0.16], dtype=np.float64)
    rejected = 0
    for index in range(len(motion)):
        left = max(0, index - 3)
        right = min(len(motion), index + 4)
        neighborhood = motion[left:right]
        median = np.median(neighborhood, axis=0)
        mad = np.median(np.abs(neighborhood - median), axis=0)
        limit = np.maximum(floors, 4.0 * 1.4826 * mad)
        delta = motion[index] - median
        clipped = np.clip(delta, -limit, limit)
        if np.any(np.abs(delta) > limit):
            rejected += 1
        motion[index] = median + clipped
    return motion, rejected


def _estimate_rigid_motion(
    previous_gray,
    current_gray,
):
    """
    Estimate center translation and in-plane rotation between two rendered
    frames while intentionally *not* using the fitted scale as stabilization
    authority.

    A partial-affine RANSAC is useful as a robust estimator, but scale is a
    nuisance variable here: parallax, walking depth changes and previous local
    warps can make apparent scale fluctuate. After estimating the transform we
    normalize its 2x2 block to a pure rotation and recompute translation from
    the inlier correspondences around the image center.
    """
    height, width = previous_gray.shape[:2]

    mask = np.zeros_like(
        previous_gray,
        dtype=np.uint8,
    )
    border_x = max(
        12,
        int(round(width * 0.04)),
    )
    border_y = max(
        12,
        int(round(height * 0.04)),
    )
    mask[
        border_y:height-border_y,
        border_x:width-border_x,
    ] = 255

    points = cv2.goodFeaturesToTrack(
        previous_gray,
        maxCorners=1600,
        qualityLevel=0.006,
        minDistance=5,
        blockSize=7,
        mask=mask,
    )

    if points is None or len(points) < 35:
        return None

    next_points, status, _error = cv2.calcOpticalFlowPyrLK(
        previous_gray,
        current_gray,
        points,
        None,
        winSize=(31, 31),
        maxLevel=4,
        criteria=(
            cv2.TERM_CRITERIA_EPS
            | cv2.TERM_CRITERIA_COUNT,
            40,
            0.005,
        ),
    )

    if next_points is None or status is None:
        return None

    back_points, back_status, _back_error = cv2.calcOpticalFlowPyrLK(
        current_gray,
        previous_gray,
        next_points,
        None,
        winSize=(31, 31),
        maxLevel=4,
        criteria=(
            cv2.TERM_CRITERIA_EPS
            | cv2.TERM_CRITERIA_COUNT,
            40,
            0.005,
        ),
    )

    if back_points is None or back_status is None:
        return None

    p0 = points.reshape(-1, 2).astype(np.float64)
    p1 = next_points.reshape(-1, 2).astype(np.float64)
    pb = back_points.reshape(-1, 2).astype(np.float64)

    roundtrip = np.linalg.norm(
        pb - p0,
        axis=1,
    )
    keep = (
        (status.reshape(-1) == 1)
        & (back_status.reshape(-1) == 1)
        & (roundtrip <= 0.90)
    )
    p0 = p0[keep]
    p1 = p1[keep]
    roundtrip = roundtrip[keep]

    if len(p0) < 30:
        return None

    matrix, inliers = cv2.estimateAffinePartial2D(
        p0,
        p1,
        method=cv2.RANSAC,
        ransacReprojThreshold=1.35,
        maxIters=4000,
        confidence=0.999,
        refineIters=20,
    )

    if matrix is None:
        return None

    if inliers is None:
        inlier_mask = np.ones(len(p0), dtype=bool)
    else:
        inlier_mask = inliers.reshape(-1).astype(bool)

    inlier_count = int(np.sum(inlier_mask))
    inlier_ratio = float(
        inlier_count
        / max(1, len(p0))
    )

    if inlier_count < 25 or inlier_ratio < 0.22:
        return None

    a = float(matrix[0, 0])
    b = float(matrix[1, 0])
    scale = math.sqrt(
        a * a
        + b * b
    )

    if (
        not math.isfinite(scale)
        or scale < 0.82
        or scale > 1.18
    ):
        return None

    angle_deg = float(
        _rotation_angle_deg(
            matrix
        )
    )

    if abs(angle_deg) > 12.0:
        return None

    angle_rad = math.radians(angle_deg)
    c = math.cos(angle_rad)
    s = math.sin(angle_rad)
    rotation = np.array(
        [
            [c, -s],
            [s, c],
        ],
        dtype=np.float64,
    )
    center = np.array(
        [
            width / 2.0,
            height / 2.0,
        ],
        dtype=np.float64,
    )

    q0 = p0[inlier_mask]
    q1 = p1[inlier_mask]
    spatial_coverage = _spatial_coverage(q0, width, height)
    if spatial_coverage < 0.34:
        return None
    rotated = (
        (q0 - center[None, :])
        @ rotation.T
        + center[None, :]
    )
    residual_translation = q1 - rotated
    translation = np.median(
        residual_translation,
        axis=0,
    )

    predicted = rotated + translation[None, :]
    residual = np.linalg.norm(
        predicted - q1,
        axis=1,
    )
    median_residual = float(
        np.median(
            residual
        )
    )

    if median_residual > 2.0:
        return None

    # Spatial disagreement is diagnostic only. A large top/bottom difference
    # means a single global rotation is not the complete image-formation model
    # (rolling shutter, parallax, stitch deformation, or a previous mesh warp).
    top_angle = _estimate_band_rotation(
        p0,
        p1,
        p0[:, 1] < height / 3.0,
    )
    bottom_angle = _estimate_band_rotation(
        p0,
        p1,
        p0[:, 1] >= 2.0 * height / 3.0,
    )
    left_angle = _estimate_band_rotation(
        p0,
        p1,
        p0[:, 0] < width / 3.0,
    )
    right_angle = _estimate_band_rotation(
        p0,
        p1,
        p0[:, 0] >= 2.0 * width / 3.0,
    )

    top_bottom_difference = (
        float(top_angle - bottom_angle)
        if top_angle is not None
        and bottom_angle is not None
        else None
    )
    left_right_difference = (
        float(left_angle - right_angle)
        if left_angle is not None
        and right_angle is not None
        else None
    )

    return {
        "dx": float(translation[0]),
        "dy": float(translation[1]),
        "roll_deg": float(angle_deg),
        "nuisance_scale": float(scale),
        "inlier_ratio": float(inlier_ratio),
        "accepted_tracks": int(inlier_count),
        "spatial_coverage": float(spatial_coverage),
        "median_fit_residual_px": float(median_residual),
        "median_roundtrip_px": float(
            np.median(roundtrip)
        ),
        "top_bottom_rotation_difference_deg": (
            top_bottom_difference
        ),
        "left_right_rotation_difference_deg": (
            left_right_difference
        ),
    }


def _smooth_rejected_velocity(
    relative_motion,
    *,
    fps,
    amount,
):
    """Return integrated high-frequency correction in dx/dy/roll channels."""
    count = len(relative_motion)

    if count <= 1:
        return np.zeros_like(
            relative_motion
        ), {
            "translation_sigma_seconds": 0.0,
            "roll_sigma_seconds": 0.0,
            "amount_gain": 0.0,
        }

    amount = max(
        0.0,
        min(
            1.0,
            float(amount),
        ),
    )

    # Translation and roll have different perceptual bandwidths. Roll wobble is
    # especially objectionable, so the visual roll lock is intentionally a bit
    # stronger/longer than X/Y residual steering.
    translation_sigma_s = (
        0.16
        + 0.60 * amount
    )
    roll_sigma_s = (
        0.22
        + 0.78 * amount
    )

    desired = relative_motion.copy()
    desired[:, 0] = _gaussian_smooth(
        relative_motion[:, 0],
        translation_sigma_s * float(fps),
    )
    desired[:, 1] = _gaussian_smooth(
        relative_motion[:, 1],
        translation_sigma_s * float(fps),
    )
    desired[:, 2] = _gaussian_smooth(
        relative_motion[:, 2],
        roll_sigma_s * float(fps),
    )

    rejected_velocity = (
        desired
        - relative_motion
    )
    correction = np.cumsum(
        rejected_velocity,
        axis=0,
    )
    correction = _zero_endpoint_baseline(
        correction
    )

    # Light cleanup only. Large extra path smoothing caused previous PanoPilot
    # versions to drift and then over-correct at keyframes.
    correction = _gaussian_smooth(
        correction,
        max(
            0.5,
            0.025 * float(fps),
        ),
    )
    correction = _zero_endpoint_baseline(
        correction
    )

    gain = (
        1.0
        - (
            1.0
            - amount
        ) ** 3
    )
    correction *= gain

    return correction, {
        "translation_sigma_seconds": float(
            translation_sigma_s
        ),
        "roll_sigma_seconds": float(
            roll_sigma_s
        ),
        "amount_gain": float(gain),
    }


def analyze_spherical_camera_stabilization(
    input_video,
    frame_segments,
    *,
    amount,
    analysis_width=960,
):
    input_video = Path(input_video)
    amount = max(
        0.0,
        min(
            1.0,
            float(amount),
        ),
    )

    cap = cv2.VideoCapture(
        str(input_video)
    )
    if not cap.isOpened():
        raise RuntimeError(
            f"Could not open video for spherical stabilization: {input_video}"
        )

    fps = float(
        cap.get(cv2.CAP_PROP_FPS)
        or 0.0
    )
    frame_count = int(
        cap.get(cv2.CAP_PROP_FRAME_COUNT)
        or 0
    )
    width = int(
        cap.get(cv2.CAP_PROP_FRAME_WIDTH)
        or 0
    )
    height = int(
        cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
        or 0
    )

    if (
        fps <= 0.0
        or frame_count <= 0
        or width <= 0
        or height <= 0
    ):
        cap.release()
        raise RuntimeError(
            "Rendered video metadata is invalid"
        )

    analysis_width = max(
        640,
        min(
            int(analysis_width),
            width,
        ),
    )
    analysis_height = max(
        180,
        int(
            round(
                height
                * analysis_width
                / width
            )
        ),
    )

    segment_starts = {
        int(start)
        for start, _count
        in frame_segments
    }
    relative_motion = np.zeros(
        (frame_count, 3),
        dtype=np.float64,
    )
    valid = np.zeros(
        frame_count,
        dtype=bool,
    )
    valid[
        list(segment_starts)
    ] = True

    accepted_tracks = []
    inlier_ratios = []
    residuals = []
    roundtrip_errors = []
    nuisance_scales = []
    spatial_coverages = []
    top_bottom_rotation = []
    left_right_rotation = []
    roll_coherence_weights = []

    previous_gray = None

    for frame_index in range(
        frame_count
    ):
        ok, frame = cap.read()
        if not ok:
            cap.release()
            raise RuntimeError(
                "Spherical stabilization analysis ended before expected frame "
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
        gray = cv2.cvtColor(
            small,
            cv2.COLOR_BGR2GRAY,
        )

        if (
            frame_index in segment_starts
            or previous_gray is None
        ):
            previous_gray = gray
            relative_motion[
                frame_index
            ] = 0.0
            valid[
                frame_index
            ] = True
            continue

        estimate = _estimate_rigid_motion(
            previous_gray,
            gray,
        )
        previous_gray = gray

        if estimate is None:
            continue

        top_bottom_value = estimate.get(
            "top_bottom_rotation_difference_deg"
        )
        left_right_value = estimate.get(
            "left_right_rotation_difference_deg"
        )
        roll_weight = _roll_coherence_weight(
            top_bottom_value,
            left_right_value,
        )

        relative_motion[
            frame_index
        ] = [
            estimate["dx"],
            estimate["dy"],
            float(
                estimate["roll_deg"]
            )
            * roll_weight,
        ]
        roll_coherence_weights.append(
            float(
                roll_weight
            )
        )
        valid[
            frame_index
        ] = True
        accepted_tracks.append(
            int(
                estimate[
                    "accepted_tracks"
                ]
            )
        )
        inlier_ratios.append(
            float(
                estimate[
                    "inlier_ratio"
                ]
            )
        )
        residuals.append(
            float(
                estimate[
                    "median_fit_residual_px"
                ]
            )
        )
        roundtrip_errors.append(
            float(
                estimate[
                    "median_roundtrip_px"
                ]
            )
        )
        nuisance_scales.append(
            float(
                estimate[
                    "nuisance_scale"
                ]
            )
        )
        spatial_coverages.append(
            float(
                estimate[
                    "spatial_coverage"
                ]
            )
        )

        if top_bottom_value is not None:
            top_bottom_rotation.append(
                float(
                    top_bottom_value
                )
            )

        if left_right_value is not None:
            left_right_rotation.append(
                float(
                    left_right_value
                )
            )

    cap.release()

    relative_motion = _fill_vector_series(
        relative_motion,
        valid,
    )
    for start, _count in frame_segments:
        relative_motion[
            int(start)
        ] = 0.0

    corrections = np.zeros_like(
        relative_motion
    )
    segment_diagnostics = []

    for segment_index, (
        start,
        count,
    ) in enumerate(
        frame_segments
    ):
        start = int(start)
        count = int(count)
        end = start + count
        local = relative_motion[
            start:end
        ].copy()

        if count <= 1:
            continue

        local, rejected_outliers = (
            _suppress_pairwise_outliers(
                local
            )
        )
        correction, temporal = (
            _smooth_rejected_velocity(
                local,
                fps=fps,
                amount=amount,
            )
        )

        # X/Y were estimated at analysis resolution. Roll is already degrees.
        correction[:, 0] *= (
            float(width)
            / float(analysis_width)
        )
        correction[:, 1] *= (
            float(height)
            / float(analysis_height)
        )

        # Crop-free spherical steering can move far, but visual-flow failures
        # still need one constant Clip-level safety gain. Roll gets its own
        # safety ratio because mixing a bad roll estimate into yaw/pitch would
        # make the correction less predictable.
        max_x = float(
            np.max(
                np.abs(
                    correction[:, 0]
                )
            )
        )
        max_y = float(
            np.max(
                np.abs(
                    correction[:, 1]
                )
            )
        )
        max_roll = float(
            np.max(
                np.abs(
                    correction[:, 2]
                )
            )
        )
        translation_safety_gain = min(
            1.0,
            0.30 * float(width)
            / max(max_x, 1e-9),
            0.27 * float(height)
            / max(max_y, 1e-9),
        )
        roll_safety_gain = min(
            1.0,
            10.0
            / max(max_roll, 1e-9),
        )
        correction[:, 0:2] *= (
            translation_safety_gain
        )
        correction[:, 2] *= (
            roll_safety_gain
        )
        corrections[
            start:end
        ] = correction

        raw_roll = local[:, 2]
        segment_diagnostics.append(
            {
                "segment_index": int(
                    segment_index
                ),
                "first_frame": int(start),
                "frame_count": int(count),
                **temporal,
                "robust_pairwise_outliers_rejected": int(
                    rejected_outliers
                ),
                "translation_safety_gain": float(
                    translation_safety_gain
                ),
                "roll_safety_gain": float(
                    roll_safety_gain
                ),
                "raw_roll_p95_abs_deg_per_frame": float(
                    np.percentile(
                        np.abs(raw_roll),
                        95,
                    )
                ),
                "raw_roll_max_abs_deg_per_frame": float(
                    np.max(
                        np.abs(raw_roll)
                    )
                ),
                "max_correction_x_px": float(
                    np.max(
                        np.abs(
                            correction[:, 0]
                        )
                    )
                ),
                "max_correction_y_px": float(
                    np.max(
                        np.abs(
                            correction[:, 1]
                        )
                    )
                ),
                "max_roll_correction_deg": float(
                    np.max(
                        np.abs(
                            correction[:, 2]
                        )
                    )
                ),
            }
        )

    def p95_abs(values):
        if not values:
            return 0.0
        return float(
            np.percentile(
                np.abs(
                    np.asarray(
                        values,
                        dtype=np.float64,
                    )
                ),
                95,
            )
        )

    spatial_rotation_p95 = max(
        p95_abs(
            top_bottom_rotation
        ),
        p95_abs(
            left_right_rotation
        ),
    )

    diagnostics = {
        "algorithm": (
            "spherical-rigid-3axis-visual-lock-v2"
        ),
        "mode": "spherical",
        "correction_domain": (
            "virtual-camera-yaw-pitch-roll-before-final-360-reprojection"
        ),
        "crop_required_for_global_correction": False,
        "pairwise_motion_model": (
            "ransac-rigid-translation-plus-roll-scale-discarded-with-3x3-coverage-gate"
        ),
        "temporal_model": (
            "robust-median-mad-pairwise-velocity-gate-then-"
            "channel-aware-lowpass-pairwise-velocity-then-integrate-rejected-band"
        ),
        "analysis_width": int(
            analysis_width
        ),
        "analysis_height": int(
            analysis_height
        ),
        "amount": float(amount),
        "valid_motion_ratio": float(
            np.mean(valid)
        ),
        "mean_accepted_tracks": (
            float(
                np.mean(
                    accepted_tracks
                )
            )
            if accepted_tracks
            else 0.0
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
        "mean_inlier_spatial_coverage": (
            float(
                np.mean(
                    spatial_coverages
                )
            )
            if spatial_coverages
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
        "median_forward_backward_error_px": (
            float(
                np.median(
                    roundtrip_errors
                )
            )
            if roundtrip_errors
            else 0.0
        ),
        "nuisance_scale_p95_deviation_percent": (
            float(
                np.percentile(
                    np.abs(
                        np.asarray(
                            nuisance_scales
                        )
                        - 1.0
                    ),
                    95,
                )
                * 100.0
            )
            if nuisance_scales
            else 0.0
        ),
        "top_bottom_rotation_disagreement_p95_deg": (
            p95_abs(
                top_bottom_rotation
            )
        ),
        "left_right_rotation_disagreement_p95_deg": (
            p95_abs(
                left_right_rotation
            )
        ),
        "spatial_rotation_disagreement_p95_deg": float(
            spatial_rotation_p95
        ),
        "rolling_shutter_or_parallax_suspected": bool(
            spatial_rotation_p95
            >= 0.75
        ),
        "visual_roll_coherence_weight_mean": (
            float(
                np.mean(
                    roll_coherence_weights
                )
            )
            if roll_coherence_weights
            else 1.0
        ),
        "visual_roll_coherence_weight_p05": (
            float(
                np.percentile(
                    roll_coherence_weights,
                    5,
                )
            )
            if roll_coherence_weights
            else 1.0
        ),
        "visual_roll_policy": (
            "gyro-authoritative; visual roll attenuated when spatial bands disagree"
        ),
        "segments": segment_diagnostics,
    }

    return SphericalCameraPlan(
        camera_corrections=(
            corrections.astype(
                np.float32
            )
        ),
        diagnostics=diagnostics,
    )
