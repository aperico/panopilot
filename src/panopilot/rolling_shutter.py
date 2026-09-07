"""
Gyro-backed rolling-shutter rectification for PanoPilot's direct renderer.

The source lens streams are rolling-shutter images: different sensor rows are
captured at different times. A frame-level quaternion can stabilize inter-frame
rotation but cannot undo this intra-frame time skew.

For one desired direction d_ref in PanoPilot's factory-equirectangular frame:

    world_direction = R_ref @ A.T @ d_ref

A source row captured at R_row must instead sample:

    d_row = A @ R_row.T @ R_ref @ A.T @ d_ref

where:
    R_* = DJI BODY->WORLD rotation
    A   = DJI IMU BODY -> PanoPilot factory-equirectangular frame

This module evaluates that row-time rotation from the ~1 kHz DJI trajectory.
The direct renderer uses the actual source-lens Y coordinate to determine the
row exposure time, samples eleven row-time orientations by default, and iterates the mapping twice because correcting the ray can
slightly change the source row itself.

The readout duration is signed:
    positive -> top-to-bottom
    negative -> bottom-to-top

No third-party source code is copied or translated.
"""
from __future__ import annotations

from dataclasses import dataclass
import math

import cv2
import numpy as np

from .attitude import (
    IMU_TO_FACTORY_EQUIRECT,
    quat_to_matrix,
)
from .stabilization import (
    sample_trajectory,
)


@dataclass(frozen=True)
class RollingShutterFrameCorrection:
    signed_readout_ms: float
    reference_source_time: float
    reference_offset_ms: float
    top_rotation_vector: np.ndarray
    bottom_rotation_vector: np.ndarray
    row_fractions: np.ndarray | None = None
    row_rotation_vectors: np.ndarray | None = None
    iterations: int = 2

    @property
    def enabled(self):
        return abs(float(self.signed_readout_ms)) > 1e-9


@dataclass(frozen=True)
class RollingShutterCalibration:
    mode: str
    signed_readout_ms: float
    reference_offset_ms: float
    direction: str
    source_frame_period_ms: float | None
    baseline_score: float | None
    selected_score: float | None
    improvement_fraction: float | None
    sample_pair_count: int
    candidate_scores: tuple
    reason: str

    def to_dict(self):
        return {
            "mode": str(self.mode),
            "signed_readout_ms": float(self.signed_readout_ms),
            "readout_ms": abs(float(self.signed_readout_ms)),
            "reference_offset_ms": float(
                self.reference_offset_ms
            ),
            "direction": str(self.direction),
            "source_frame_period_ms": (
                float(self.source_frame_period_ms)
                if self.source_frame_period_ms is not None
                else None
            ),
            "baseline_score": (
                float(self.baseline_score)
                if self.baseline_score is not None
                else None
            ),
            "selected_score": (
                float(self.selected_score)
                if self.selected_score is not None
                else None
            ),
            "improvement_fraction": (
                float(self.improvement_fraction)
                if self.improvement_fraction is not None
                else None
            ),
            "sample_pair_count": int(self.sample_pair_count),
            "candidate_scores": [
                (
                    {
                        "signed_readout_ms": float(item[0]),
                        "reference_offset_ms": float(item[1]),
                        "score": float(item[2]),
                    }
                    if len(item) >= 3
                    else {
                        "signed_readout_ms": float(item[0]),
                        "reference_offset_ms": 0.0,
                        "score": float(item[1]),
                    }
                )
                for item in self.candidate_scores
            ],
            "reason": str(self.reason),
        }


def _matrix_to_rotvec(matrix):
    vector, _jacobian = cv2.Rodrigues(
        np.asarray(
            matrix,
            dtype=np.float64,
        )
    )
    return vector.reshape(3).astype(
        np.float64
    )


def _row_sampling_rotation(
    reference_quaternion,
    row_quaternion,
):
    """
    Desired reference-time factory-equirect direction -> source-row direction.
    """
    reference = quat_to_matrix(
        reference_quaternion
    )
    row = quat_to_matrix(
        row_quaternion
    )

    return (
        IMU_TO_FACTORY_EQUIRECT
        @ row.T
        @ reference
        @ IMU_TO_FACTORY_EQUIRECT.T
    )


def build_frame_correction(
    trajectory,
    reference_source_time,
    signed_readout_ms,
    *,
    reference_offset_ms=0.0,
    imu_offset_ms=0.0,
    subdivisions=11,
    iterations=2,
):
    signed_readout_ms = float(
        signed_readout_ms
    )
    reference_source_time = float(
        reference_source_time
    )

    if abs(signed_readout_ms) <= 1e-9:
        zero = np.zeros(
            3,
            dtype=np.float64,
        )
        return RollingShutterFrameCorrection(
            signed_readout_ms=0.0,
            reference_source_time=(
                reference_source_time
            ),
            reference_offset_ms=float(
                reference_offset_ms
            ),
            top_rotation_vector=zero.copy(),
            bottom_rotation_vector=zero.copy(),
            row_fractions=np.linspace(
                0.0,
                1.0,
                max(
                    2,
                    min(
                        33,
                        int(
                            subdivisions
                        ),
                    ),
                ),
                dtype=np.float64,
            ),
            row_rotation_vectors=np.zeros(
                (
                    max(
                        2,
                        min(
                            33,
                            int(
                                subdivisions
                            ),
                        ),
                    ),
                    3,
                ),
                dtype=np.float64,
            ),
            iterations=max(
                1,
                int(iterations),
            ),
        )

    subdivisions = max(
        2,
        min(
            33,
            int(
                subdivisions
            ),
        ),
    )
    row_fractions = np.linspace(
        0.0,
        1.0,
        subdivisions,
        dtype=np.float64,
    )
    center_offset_s = (
        float(
            reference_offset_ms
        )
        / 1000.0
    )
    readout_s = (
        signed_readout_ms
        / 1000.0
    )

    # Sample the exact high-rate trajectory at multiple sensor-row times.
    # Walking steps can contain noticeable angular acceleration inside one
    # rolling-shutter interval; a top/bottom-only linear model is insufficient
    # in precisely those cases.
    row_times = (
        reference_source_time
        + center_offset_s
        + (
            row_fractions
            - 0.5
        )
        * readout_s
    )
    all_times = np.concatenate(
        (
            np.asarray(
                [
                    reference_source_time
                ],
                dtype=np.float64,
            ),
            row_times,
        )
    )
    raw, _stable = sample_trajectory(
        trajectory,
        all_times,
        imu_offset_ms=(
            imu_offset_ms
        ),
    )
    q_ref = raw[
        0
    ]
    row_quaternions = raw[
        1:
    ]
    rotation_vectors = np.asarray(
        [
            _matrix_to_rotvec(
                _row_sampling_rotation(
                    q_ref,
                    quaternion,
                )
            )
            for quaternion in row_quaternions
        ],
        dtype=np.float64,
    )
    top_rotation_vector = (
        rotation_vectors[
            0
        ]
    )
    bottom_rotation_vector = (
        rotation_vectors[
            -1
        ]
    )

    return RollingShutterFrameCorrection(
        signed_readout_ms=(
            signed_readout_ms
        ),
        reference_source_time=(
            reference_source_time
        ),
        reference_offset_ms=float(
            reference_offset_ms
        ),
        top_rotation_vector=(
            top_rotation_vector.copy()
        ),
        bottom_rotation_vector=(
            bottom_rotation_vector.copy()
        ),
        row_fractions=(
            row_fractions.copy()
        ),
        row_rotation_vectors=(
            rotation_vectors.copy()
        ),
        iterations=max(
            1,
            min(
                3,
                int(
                    iterations
                ),
            ),
        ),
    )


def panorama_map_to_directions(
    map_x,
    map_y,
    panorama_width,
    panorama_height,
):
    map_x = np.asarray(
        map_x,
        dtype=np.float32,
    )
    map_y = np.asarray(
        map_y,
        dtype=np.float32,
    )
    width = np.float32(
        panorama_width
    )
    height = np.float32(
        panorama_height
    )

    longitude = (
        (
            map_x
            + np.float32(
                0.5
            )
        )
        / width
        * np.float32(
            2.0
            * math.pi
        )
        - np.float32(
            math.pi
        )
    )
    latitude = (
        np.float32(
            math.pi
            / 2.0
        )
        - (
            (
                map_y
                + np.float32(
                    0.5
                )
            )
            / height
            * np.float32(
                math.pi
            )
        )
    )

    cos_lat = np.cos(
        latitude
    )
    directions = np.empty(
        map_x.shape
        + (
            3,
        ),
        dtype=np.float32,
    )
    directions[
        ...,
        0
    ] = (
        cos_lat
        * np.sin(
            longitude
        )
    )
    directions[
        ...,
        1
    ] = np.sin(
        latitude
    )
    directions[
        ...,
        2
    ] = (
        cos_lat
        * np.cos(
            longitude
        )
    )

    return directions


def directions_to_panorama_map(
    directions,
    panorama_width,
    panorama_height,
):
    directions = np.asarray(
        directions,
        dtype=np.float32,
    )
    x = directions[
        ...,
        0
    ]
    y = np.clip(
        directions[
            ...,
            1
        ],
        np.float32(
            -1.0
        ),
        np.float32(
            1.0
        ),
    )
    z = directions[
        ...,
        2
    ]

    longitude = np.arctan2(
        x,
        z,
    )
    latitude = np.arcsin(
        y
    )

    width = np.float32(
        panorama_width
    )
    height = np.float32(
        panorama_height
    )
    map_x = (
        (
            longitude
            + np.float32(
                math.pi
            )
        )
        / np.float32(
            2.0
            * math.pi
        )
        * width
        - np.float32(
            0.5
        )
    )
    map_y = (
        (
            np.float32(
                math.pi
                / 2.0
            )
            - latitude
        )
        / np.float32(
            math.pi
        )
        * height
        - np.float32(
            0.5
        )
    )

    # The direction -> longitude conversion is bounded to one period.
    map_x = np.where(
        map_x
        < 0.0,
        map_x
        + width,
        map_x,
    )
    map_x = np.where(
        map_x
        >= width,
        map_x
        - width,
        map_x,
    )
    map_y = np.clip(
        map_y,
        0.0,
        float(
            panorama_height
            - 1
        ),
    )

    return (
        map_x.astype(
            np.float32
        ),
        map_y.astype(
            np.float32
        ),
    )


def apply_rotation_vector_field(
    directions,
    top_rotation_vector,
    bottom_rotation_vector,
    row_fraction,
    *,
    row_fractions=None,
    row_rotation_vectors=None,
):
    """
    Apply a continuously interpolated small SO(3) rotation to each direction.

    The rolling-shutter interval is only a few milliseconds. Interpolating the
    rotation vector in the Lie algebra between exact top/bottom IMU rotations
    is substantially more accurate than one global shear/homography and avoids
    materializing one 3x3 matrix per pixel.
    """
    directions = np.asarray(
        directions,
        dtype=np.float32,
    )
    row_fraction = np.asarray(
        row_fraction,
        dtype=np.float32,
    )
    top = np.asarray(
        top_rotation_vector,
        dtype=np.float32,
    )
    bottom = np.asarray(
        bottom_rotation_vector,
        dtype=np.float32,
    )

    table = (
        np.asarray(
            row_rotation_vectors,
            dtype=np.float32,
        )
        if row_rotation_vectors
        is not None
        else None
    )
    fractions = (
        np.asarray(
            row_fractions,
            dtype=np.float32,
        )
        if row_fractions
        is not None
        else None
    )

    if (
        table is not None
        and fractions is not None
        and len(table) >= 2
        and len(fractions) == len(table)
    ):
        # build_frame_correction uses a uniform row-fraction grid. Use direct
        # indexed interpolation between exact ~1 kHz orientation samples.
        scaled = (
            row_fraction
            * np.float32(
                len(table)
                - 1
            )
        )
        lower = np.floor(
            scaled
        ).astype(
            np.int32
        )
        lower = np.clip(
            lower,
            0,
            len(table)
            - 2,
        )
        alpha = (
            scaled
            - lower.astype(
                np.float32
            )
        )
        upper = (
            lower
            + 1
        )
        vector = (
            table[
                lower
            ]
            * (
                np.float32(
                    1.0
                )
                - alpha[
                    ...,
                    None
                ]
            )
            + table[
                upper
            ]
            * alpha[
                ...,
                None
            ]
        )
    else:
        vector = (
            top[
                None,
                None,
                :
            ]
            + row_fraction[
                ...,
                None
            ]
            * (
                bottom
                - top
            )[
                None,
                None,
                :
            ]
        )
    theta = np.linalg.norm(
        vector,
        axis=-1,
    ).astype(
        np.float32
    )
    safe_theta = np.where(
        theta
        > np.float32(
            1e-8
        ),
        theta,
        np.float32(
            1.0
        ),
    )
    axis = (
        vector
        / safe_theta[
            ...,
            None
        ]
    )

    cos_theta = np.cos(
        theta
    )
    sin_theta = np.sin(
        theta
    )
    cross = np.cross(
        axis,
        directions,
    )
    dot = np.sum(
        axis
        * directions,
        axis=-1,
    )

    rotated = (
        directions
        * cos_theta[
            ...,
            None
        ]
        + cross
        * sin_theta[
            ...,
            None
        ]
        + axis
        * dot[
            ...,
            None
        ]
        * (
            np.float32(
                1.0
            )
            - cos_theta
        )[
            ...,
            None
        ]
    )

    tiny = (
        theta
        <= np.float32(
            1e-8
        )
    )
    if np.any(
        tiny
    ):
        rotated[
            tiny
        ] = directions[
            tiny
        ]

    return rotated.astype(
        np.float32
    )


def corrected_panorama_map_for_lens(
    base_map_x,
    base_map_y,
    lens_y,
    *,
    source_height,
    panorama_width,
    panorama_height,
    correction,
    base_directions=None,
):
    if (
        correction is None
        or not correction.enabled
    ):
        return (
            np.asarray(
                base_map_x,
                dtype=np.float32,
            ),
            np.asarray(
                base_map_y,
                dtype=np.float32,
            ),
        )

    source_height = max(
        1,
        int(
            source_height
        ),
    )
    row_fraction = (
        (
            np.asarray(
                lens_y,
                dtype=np.float32,
            )
            + np.float32(
                0.5
            )
        )
        / np.float32(
            source_height
        )
    )
    row_fraction = np.clip(
        row_fraction,
        np.float32(
            0.0
        ),
        np.float32(
            1.0
        ),
    )

    directions = (
        np.asarray(
            base_directions,
            dtype=np.float32,
        )
        if base_directions
        is not None
        else panorama_map_to_directions(
            base_map_x,
            base_map_y,
            panorama_width,
            panorama_height,
        )
    )
    corrected = apply_rotation_vector_field(
        directions,
        correction.top_rotation_vector,
        correction.bottom_rotation_vector,
        row_fraction,
        row_fractions=(
            correction.row_fractions
        ),
        row_rotation_vectors=(
            correction.row_rotation_vectors
        ),
    )

    return directions_to_panorama_map(
        corrected,
        panorama_width,
        panorama_height,
    )


def candidate_signed_readouts(
    source_frame_period_ms,
):
    """
    Bounded clean-room calibration grid.

    Rolling-shutter readout must fit inside one source frame period. Search both
    directions and keep zero as the no-harm baseline.
    """
    period = max(
        0.1,
        float(
            source_frame_period_ms
        ),
    )
    fractions = (
        0.30,
        0.48,
        0.65,
        0.80,
        0.92,
    )
    values = [
        0.0
    ]

    for fraction in fractions:
        value = (
            period
            * fraction
        )
        values.extend(
            (
                -value,
                value,
            )
        )

    return tuple(
        sorted(
            values
        )
    )


def choose_calibration(
    scores,
    *,
    source_frame_period_ms,
    sample_pair_count,
    minimum_improvement_fraction=0.06,
):
    """
    Select signed readout + frame-reference offset only when the pair beats the
    zero-readout/zero-offset baseline by a material margin.

    ``scores`` keys may be:
        signed_readout_ms
    or:
        (signed_readout_ms, reference_offset_ms)
    """
    normalized = {}

    for candidate, score in scores.items():
        score = float(
            score
        )

        if not math.isfinite(
            score
        ):
            continue

        if isinstance(
            candidate,
            tuple,
        ):
            signed = float(
                candidate[
                    0
                ]
            )
            offset = float(
                candidate[
                    1
                ]
            )
        else:
            signed = float(
                candidate
            )
            offset = 0.0

        normalized[
            (
                signed,
                offset,
            )
        ] = score

    baseline = normalized.get(
        (
            0.0,
            0.0,
        )
    )

    if not normalized:
        return RollingShutterCalibration(
            mode="auto",
            signed_readout_ms=0.0,
            reference_offset_ms=0.0,
            direction="none",
            source_frame_period_ms=float(
                source_frame_period_ms
            ),
            baseline_score=None,
            selected_score=None,
            improvement_fraction=None,
            sample_pair_count=int(
                sample_pair_count
            ),
            candidate_scores=tuple(),
            reason=(
                "no valid visual calibration scores"
            ),
        )

    best_candidate = min(
        normalized,
        key=normalized.get,
    )
    best_score = normalized[
        best_candidate
    ]
    best_signed, best_offset = (
        best_candidate
    )

    if baseline is None:
        selected_signed = best_signed
        selected_offset = best_offset
        improvement = None
        reason = (
            "zero-readout baseline unavailable; selected lowest valid score"
        )
    else:
        improvement = (
            (
                baseline
                - best_score
            )
            / max(
                baseline,
                1e-9,
            )
        )

        if (
            abs(
                best_signed
            )
            <= 1e-9
            or improvement
            < float(
                minimum_improvement_fraction
            )
        ):
            selected_signed = 0.0
            selected_offset = 0.0
            best_score = baseline
            reason = (
                "non-zero readout did not materially beat the zero-readout baseline"
            )
        else:
            selected_signed = (
                best_signed
            )
            selected_offset = (
                best_offset
            )
            reason = (
                "signed readout and timing offset materially reduced calibrated residual wobble"
            )

    direction = (
        "top-to-bottom"
        if selected_signed > 0.0
        else (
            "bottom-to-top"
            if selected_signed < 0.0
            else "none"
        )
    )

    return RollingShutterCalibration(
        mode="auto",
        signed_readout_ms=float(
            selected_signed
        ),
        reference_offset_ms=float(
            selected_offset
        ),
        direction=direction,
        source_frame_period_ms=float(
            source_frame_period_ms
        ),
        baseline_score=(
            float(
                baseline
            )
            if baseline is not None
            else None
        ),
        selected_score=float(
            best_score
        ),
        improvement_fraction=(
            float(
                improvement
            )
            if improvement is not None
            else None
        ),
        sample_pair_count=int(
            sample_pair_count
        ),
        candidate_scores=tuple(
            (
                float(
                    candidate[
                        0
                    ]
                ),
                float(
                    candidate[
                        1
                    ]
                ),
                float(
                    score
                ),
            )
            for candidate, score in sorted(
                normalized.items()
            )
        ),
        reason=reason,
    )

