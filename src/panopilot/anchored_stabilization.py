"""
Anchored spatially-variant residual stabilization.

Why this exists
---------------
The earlier residual stabilizers used one global similarity/translation model.
That model is intrinsically wrong for walking footage: translation, parallax,
rolling-shutter skew, stitching residuals, and foreground/background depth
differences do not share one transform. Increasing a global correction makes
those disagreements visible as rubber/zoom wobble.

This implementation follows three clean-room principles supported by published
video-stabilization work:

1. represent residual motion spatially with a *coarse* mesh rather than one
   full-frame transform;
2. smooth the bundle of mesh-vertex paths in space and time;
3. periodically anchor local deformation to the gyro-backed image geometry so
   the flexible model cannot drift and create wobble.

The mesh is intentionally coarse and strongly regularized. Gyro stabilization
remains authoritative for 3-axis orientation. This stage only handles residual
image motion after the gyro/direct renderer.

No scale or per-frame zoom parameter is solved. The user's crop value is a
maximum budget; the actual fixed crop is the minimum required by the stabilized
mesh for each hard-cut Clip.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import math
import subprocess
import time

import cv2
import numpy as np


@dataclass(frozen=True)
class AnchoredMeshPlan:
    corrections: np.ndarray
    segment_crop_percent: tuple
    frame_segment_index: np.ndarray
    diagnostics: dict


def _gaussian_smooth(values, sigma_frames):
    values = np.asarray(
        values,
        dtype=np.float64,
    )

    if len(values) <= 1:
        return values.copy()

    sigma = float(
        sigma_frames
    )

    if sigma <= 1e-9:
        return values.copy()

    radius = max(
        1,
        int(
            math.ceil(
                3.0
                * sigma
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

    if values.ndim == 1:
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

    # Temporal axis is axis 0; flatten the remaining dimensions so all vertex
    # profiles use exactly the same zero-phase kernel.
    shape = values.shape
    flat = values.reshape(
        shape[
            0
        ],
        -1,
    )
    out = np.empty_like(
        flat
    )

    for column in range(
        flat.shape[
            1
        ]
    ):
        padded = np.pad(
            flat[
                :,
                column
            ],
            (
                radius,
                radius,
            ),
            mode="edge",
        )
        out[
            :,
            column
        ] = np.convolve(
            padded,
            kernel,
            mode="valid",
        )

    return out.reshape(
        shape
    )


def _weighted_median(values, weights):
    values = np.asarray(
        values,
        dtype=np.float64,
    )
    weights = np.asarray(
        weights,
        dtype=np.float64,
    )

    if len(values) == 0:
        return 0.0

    order = np.argsort(
        values
    )
    values = values[
        order
    ]
    weights = weights[
        order
    ]
    total = float(
        np.sum(
            weights
        )
    )

    if total <= 1e-12:
        return float(
            np.median(
                values
            )
        )

    cumulative = np.cumsum(
        weights
    )
    index = int(
        np.searchsorted(
            cumulative,
            0.5
            * total,
            side="left",
        )
    )
    index = min(
        max(
            index,
            0,
        ),
        len(values)
        - 1,
    )

    return float(
        values[
            index
        ]
    )


def _grid_coordinates(
    width,
    height,
    rows,
    cols,
):
    xs = np.linspace(
        0.0,
        float(
            width - 1
        ),
        int(
            cols
        ),
        dtype=np.float64,
    )
    ys = np.linspace(
        0.0,
        float(
            height - 1
        ),
        int(
            rows
        ),
        dtype=np.float64,
    )
    xx, yy = np.meshgrid(
        xs,
        ys,
    )

    return np.stack(
        (
            xx,
            yy,
        ),
        axis=-1,
    )


def _spatial_regularize(
    field,
    *,
    iterations=2,
    neighbor_strength=0.32,
):
    field = np.asarray(
        field,
        dtype=np.float64,
    ).copy()

    rows, cols = field.shape[
        :2
    ]

    for _ in range(
        int(
            iterations
        )
    ):
        updated = field.copy()

        for row in range(
            rows
        ):
            for col in range(
                cols
            ):
                neighbors = []

                for dr, dc in (
                    (
                        -1,
                        0,
                    ),
                    (
                        1,
                        0,
                    ),
                    (
                        0,
                        -1,
                    ),
                    (
                        0,
                        1,
                    ),
                ):
                    rr = (
                        row
                        + dr
                    )
                    cc = (
                        col
                        + dc
                    )

                    if (
                        0
                        <= rr
                        < rows
                        and 0
                        <= cc
                        < cols
                    ):
                        neighbors.append(
                            field[
                                rr,
                                cc,
                            ]
                        )

                if not neighbors:
                    continue

                average = np.mean(
                    np.asarray(
                        neighbors
                    ),
                    axis=0,
                )
                updated[
                    row,
                    col,
                ] = (
                    (
                        1.0
                        - neighbor_strength
                    )
                    * field[
                        row,
                        col,
                    ]
                    + neighbor_strength
                    * average
                )

        field = updated

    return field


def _estimate_mesh_motion(
    previous_gray,
    current_gray,
    *,
    grid_rows,
    grid_cols,
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
        12,
        int(
            round(
                width
                * 0.035
            )
        ),
    )
    border_y = max(
        12,
        int(
            round(
                height
                * 0.035
            )
        ),
    )
    mask[
        border_y:height-border_y,
        border_x:width-border_x,
    ] = 255

    points = cv2.goodFeaturesToTrack(
        previous_gray,
        maxCorners=1800,
        qualityLevel=0.006,
        minDistance=5,
        blockSize=7,
        mask=mask,
    )

    grid = np.zeros(
        (
            grid_rows,
            grid_cols,
            2,
        ),
        dtype=np.float64,
    )

    if (
        points is None
        or len(
            points
        )
        < 35
    ):
        return grid, {
            "valid": False,
            "track_count": 0,
            "accepted_tracks": 0,
            "median_roundtrip_px": None,
        }

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
        return grid, {
            "valid": False,
            "track_count": int(
                len(
                    points
                )
            ),
            "accepted_tracks": 0,
            "median_roundtrip_px": None,
        }

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
        return grid, {
            "valid": False,
            "track_count": int(
                len(
                    points
                )
            ),
            "accepted_tracks": 0,
            "median_roundtrip_px": None,
        }

    p0 = points.reshape(
        -1,
        2,
    ).astype(
        np.float64
    )
    p1 = next_points.reshape(
        -1,
        2,
    ).astype(
        np.float64
    )
    pb = back_points.reshape(
        -1,
        2,
    ).astype(
        np.float64
    )

    roundtrip = np.linalg.norm(
        pb
        - p0,
        axis=1,
    )
    keep = (
        (
            status.reshape(
                -1
            )
            == 1
        )
        & (
            back_status.reshape(
                -1
            )
            == 1
        )
        & (
            roundtrip
            <= 0.80
        )
    )

    p0 = p0[
        keep
    ]
    p1 = p1[
        keep
    ]
    roundtrip = roundtrip[
        keep
    ]

    if len(
        p0
    ) < 30:
        return grid, {
            "valid": False,
            "track_count": int(
                len(
                    points
                )
            ),
            "accepted_tracks": int(
                len(
                    p0
                )
            ),
            "median_roundtrip_px": (
                float(
                    np.median(
                        roundtrip
                    )
                )
                if len(
                    roundtrip
                )
                else None
            ),
        }

    displacement = (
        p1
        - p0
    )
    global_motion = np.median(
        displacement,
        axis=0,
    )
    deviation = np.linalg.norm(
        displacement
        - global_motion[
            None,
            :
        ],
        axis=1,
    )
    deviation_median = float(
        np.median(
            deviation
        )
    )
    deviation_mad = float(
        np.median(
            np.abs(
                deviation
                - deviation_median
            )
        )
    )
    robust_sigma = (
        1.4826
        * deviation_mad
    )
    threshold = max(
        5.0,
        deviation_median
        + 5.0
        * robust_sigma,
    )
    coherent = (
        deviation
        <= threshold
    )
    p0 = p0[
        coherent
    ]
    displacement = displacement[
        coherent
    ]

    if len(
        p0
    ) < 25:
        return grid, {
            "valid": False,
            "track_count": int(
                len(
                    points
                )
            ),
            "accepted_tracks": int(
                len(
                    p0
                )
            ),
            "median_roundtrip_px": (
                float(
                    np.median(
                        roundtrip
                    )
                )
                if len(
                    roundtrip
                )
                else None
            ),
        }

    global_motion = np.median(
        displacement,
        axis=0,
    )
    vertices = _grid_coordinates(
        width,
        height,
        grid_rows,
        grid_cols,
    )

    cell_width = (
        float(
            width
        )
        / max(
            1,
            grid_cols
            - 1,
        )
    )
    cell_height = (
        float(
            height
        )
        / max(
            1,
            grid_rows
            - 1,
        )
    )
    radius = (
        1.45
        * math.sqrt(
            cell_width
            * cell_width
            + cell_height
            * cell_height
        )
    )
    sigma = (
        0.62
        * radius
    )

    for row in range(
        grid_rows
    ):
        for col in range(
            grid_cols
        ):
            vertex = vertices[
                row,
                col,
            ]
            distance = np.linalg.norm(
                p0
                - vertex[
                    None,
                    :
                ],
                axis=1,
            )
            order = np.argsort(
                distance
            )
            order = order[
                : min(
                    90,
                    len(
                        order
                    ),
                )
            ]
            local_distance = distance[
                order
            ]
            local_keep = (
                local_distance
                <= radius
            )
            order = order[
                local_keep
            ]

            if len(
                order
            ) < 6:
                grid[
                    row,
                    col,
                ] = global_motion
                continue

            local_distance = distance[
                order
            ]
            weights = np.exp(
                -0.5
                * (
                    local_distance
                    / max(
                        sigma,
                        1e-6,
                    )
                ) ** 2
            )
            local = displacement[
                order
            ]
            estimate = np.array(
                [
                    _weighted_median(
                        local[
                            :,
                            0
                        ],
                        weights,
                    ),
                    _weighted_median(
                        local[
                            :,
                            1
                        ],
                        weights,
                    ),
                ],
                dtype=np.float64,
            )

            # The gyro-backed full frame is the global regularizing backbone.
            # Local motion may deviate to model parallax/rolling shutter, but
            # never enough to turn one moving foreground object into a rubber
            # mesh.
            delta = (
                estimate
                - global_motion
            )
            delta_norm = float(
                np.linalg.norm(
                    delta
                )
            )
            local_limit = max(
                5.0,
                0.75
                * min(
                    cell_width,
                    cell_height,
                )
                * 0.12,
            )

            if (
                delta_norm
                > local_limit
            ):
                delta *= (
                    local_limit
                    / delta_norm
                )

            grid[
                row,
                col,
            ] = (
                global_motion
                + 0.55
                * delta
            )

    grid = _spatial_regularize(
        grid,
        iterations=2,
        neighbor_strength=0.34,
    )

    return grid, {
        "valid": True,
        "track_count": int(
            len(
                points
            )
        ),
        "accepted_tracks": int(
            len(
                p0
            )
        ),
        "median_roundtrip_px": float(
            np.median(
                roundtrip
            )
        ),
        "global_dx": float(
            global_motion[
                0
            ]
        ),
        "global_dy": float(
            global_motion[
                1
            ]
        ),
    }


def _keyframe_envelope(
    count,
    spacing_frames,
):
    count = int(
        count
    )
    spacing = max(
        2,
        int(
            spacing_frames
        ),
    )
    envelope = np.ones(
        count,
        dtype=np.float64,
    )

    if count <= 1:
        return np.zeros(
            count,
            dtype=np.float64,
        )

    anchors = list(
        range(
            0,
            count,
            spacing,
        )
    )

    if anchors[
        -1
    ] != (
        count
        - 1
    ):
        anchors.append(
            count
            - 1
        )

    envelope[:] = 0.0

    for left, right in zip(
        anchors[
            :-1
        ],
        anchors[
            1:
        ],
    ):
        span = (
            right
            - left
        )

        if span <= 0:
            continue

        u = np.linspace(
            0.0,
            1.0,
            span + 1,
            dtype=np.float64,
        )
        envelope[
            left:right+1
        ] = np.sin(
            math.pi
            * u
        ) ** 2

    return envelope


def _zero_endpoint_baseline(
    correction,
):
    correction = np.asarray(
        correction,
        dtype=np.float64,
    ).copy()

    count = correction.shape[
        0
    ]

    if count <= 1:
        correction[...] = 0.0
        return correction

    u = np.linspace(
        0.0,
        1.0,
        count,
        dtype=np.float64,
    )
    start = correction[
        0
    ].copy()
    end = correction[
        -1
    ].copy()
    baseline = (
        (
            1.0
            - u
        )[
            :,
            None
        ]
        * start[
            None,
            :
        ]
        + u[
            :,
            None
        ]
        * end[
            None,
            :
        ]
    )
    correction -= baseline

    return correction


def _build_segment_correction(
    motion,
    *,
    fps,
    amount,
    global_authority=1.0,
):
    """
    Build a bounded correction from *velocity* profiles, not absolute paths.

    Earlier PanoPilot experiments smoothed integrated image position. During
    walking/forward travel that confuses real scene motion with shake and can
    demand hundreds of pixels of crop. Here we instead low-pass the pairwise
    mesh velocity and integrate only the rejected high-frequency component.
    Slow pan/translation therefore remains in the shot while step-frequency
    bobbing is removed.
    """
    count, rows, cols, _ = motion.shape
    amount = max(0.0, min(1.0, float(amount)))

    global_motion = np.median(
        motion.reshape(count, -1, 2),
        axis=1,
    )
    local_motion = (
        motion
        - global_motion[:, None, None, :]
    )

    # Walking shake is normally concentrated above the intended camera-motion
    # bandwidth. Smooth relative frame velocity, not integrated position.
    global_sigma_s = 0.10 + 0.24 * amount
    desired_global_motion = _gaussian_smooth(
        global_motion,
        global_sigma_s * float(fps),
    )
    global_rejected_velocity = (
        desired_global_motion
        - global_motion
    )
    global_correction = np.cumsum(
        global_rejected_velocity,
        axis=0,
    )
    global_correction = _zero_endpoint_baseline(
        global_correction
    )

    # Spatially varying residuals (parallax, rolling-shutter/stitch residual)
    # are allowed a narrower correction bandwidth and smaller authority.
    local_sigma_s = 0.07 + 0.15 * amount
    desired_local_motion = _gaussian_smooth(
        local_motion,
        local_sigma_s * float(fps),
    )
    local_rejected_velocity = (
        desired_local_motion
        - local_motion
    )
    local_correction = np.cumsum(
        local_rejected_velocity,
        axis=0,
    )

    keyframe_spacing_s = 0.80 + 0.30 * amount
    envelope = _keyframe_envelope(
        count,
        round(keyframe_spacing_s * float(fps)),
    )
    local_correction *= envelope[:, None, None, None]
    local_strength = 0.12 + 0.28 * amount

    global_authority = max(
        0.0,
        min(
            1.0,
            float(global_authority),
        ),
    )
    correction = (
        global_authority * global_correction[:, None, None, :]
        + local_strength * local_correction
    )

    for frame_index in range(count):
        correction[frame_index] = _spatial_regularize(
            correction[frame_index],
            iterations=2,
            neighbor_strength=0.28,
        )

    gain = 1.0 - (1.0 - amount) ** 3
    correction *= gain

    return correction, {
        "temporal_model": "lowpass-pairwise-velocity-then-integrate-rejected-band",
        "global_sigma_seconds": float(global_sigma_s),
        "local_sigma_seconds": float(local_sigma_s),
        "keyframe_spacing_seconds": float(keyframe_spacing_s),
        "local_strength": float(local_strength),
        "amount_gain": float(gain),
        "global_authority": float(global_authority),
    }

def _clip_crop_policy(
    correction,
    *,
    width,
    height,
    max_crop_percent,
):
    max_crop_percent = max(
        0.0,
        float(
            max_crop_percent
        ),
    )

    max_x = float(
        np.max(
            np.abs(
                correction[
                    ...,
                    0
                ]
            )
        )
    )
    max_y = float(
        np.max(
            np.abs(
                correction[
                    ...,
                    1
                ]
            )
        )
    )

    raw_required = max(
        (
            2.0
            * max_x
            / max(
                float(
                    width
                ),
                1.0,
            )
            * 100.0
        ),
        (
            2.0
            * max_y
            / max(
                float(
                    height
                ),
                1.0,
            )
            * 100.0
        ),
    )

    # Safety for bilinear field interpolation and integer crop rounding.
    required = (
        1.0
        + 1.10
        * raw_required
        if raw_required
        > 0.05
        else 0.0
    )

    if required <= max_crop_percent:
        gain = 1.0
        actual = required
    elif required <= 1e-9:
        gain = 1.0
        actual = 0.0
    else:
        # One constant gain for the whole Clip. No frame-dependent clipping.
        gain = max(
            0.0,
            min(
                1.0,
                (
                    max_crop_percent
                    - 1.0
                )
                / max(
                    1.10
                    * raw_required,
                    1e-9,
                ),
            ),
        )
        actual = (
            max_crop_percent
            if max_crop_percent
            > 0.0
            else 0.0
        )

    return {
        "gain": float(
            gain
        ),
        "actual_crop_percent": float(
            max(
                0.0,
                actual,
            )
        ),
        "raw_required_crop_percent": float(
            raw_required
        ),
        "max_x_px": float(
            max_x
        ),
        "max_y_px": float(
            max_y
        ),
    }


def analyze_anchored_stabilization(
    input_video,
    frame_segments,
    *,
    amount,
    max_crop_percent=18.0,
    analysis_width=960,
    grid_rows=4,
    grid_cols=6,
    global_authority=1.0,
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
    max_crop_percent = float(
        max_crop_percent
    )

    if not 0.0 <= max_crop_percent <= 35.0:
        raise ValueError(
            "max_crop_percent must be between 0 and 35 for anchored stabilization"
        )

    cap = cv2.VideoCapture(
        str(
            input_video
        )
    )

    if not cap.isOpened():
        raise RuntimeError(
            f"Could not open video for anchored stabilization: {input_video}"
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

    if (
        fps <= 0.0
        or frame_count <= 0
        or width <= 0
        or height <= 0
    ):
        cap.release()
        raise RuntimeError(
            "Rendered video metadata is invalid for anchored stabilization"
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
    grid_rows = max(
        3,
        min(
            6,
            int(
                grid_rows
            ),
        ),
    )
    grid_cols = max(
        4,
        min(
            8,
            int(
                grid_cols
            ),
        ),
    )

    segment_starts = {
        int(
            start
        )
        for start, _count
        in frame_segments
    }

    motion = np.zeros(
        (
            frame_count,
            grid_rows,
            grid_cols,
            2,
        ),
        dtype=np.float64,
    )
    valid_frame = np.zeros(
        frame_count,
        dtype=bool,
    )
    track_counts = []
    accepted_counts = []
    roundtrip_values = []

    previous_gray = None

    for frame_index in range(
        frame_count
    ):
        ok, frame = cap.read()

        if not ok:
            cap.release()
            raise RuntimeError(
                "Anchored stabilization analysis ended before expected frame "
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
            frame_index
            in segment_starts
            or previous_gray
            is None
        ):
            previous_gray = gray
            valid_frame[
                frame_index
            ] = True
            continue

        mesh_motion, diagnostics = (
            _estimate_mesh_motion(
                previous_gray,
                gray,
                grid_rows=(
                    grid_rows
                ),
                grid_cols=(
                    grid_cols
                ),
            )
        )
        motion[
            frame_index
        ] = mesh_motion
        valid_frame[
            frame_index
        ] = bool(
            diagnostics[
                "valid"
            ]
        )
        track_counts.append(
            int(
                diagnostics[
                    "track_count"
                ]
            )
        )
        accepted_counts.append(
            int(
                diagnostics[
                    "accepted_tracks"
                ]
            )
        )

        if (
            diagnostics[
                "median_roundtrip_px"
            ]
            is not None
        ):
            roundtrip_values.append(
                float(
                    diagnostics[
                        "median_roundtrip_px"
                    ]
                )
            )

        previous_gray = gray

    cap.release()

    # Invalid pairwise mesh estimates are filled temporally per vertex. This is
    # safer than switching models on/off at isolated frames.
    frame_indices = np.arange(
        frame_count,
        dtype=np.float64,
    )

    for row in range(
        grid_rows
    ):
        for col in range(
            grid_cols
        ):
            for component in range(
                2
            ):
                values = motion[
                    :,
                    row,
                    col,
                    component
                ]
                good = np.flatnonzero(
                    valid_frame
                    & np.isfinite(
                        values
                    )
                )

                if len(
                    good
                ) >= 2:
                    motion[
                        :,
                        row,
                        col,
                        component
                    ] = np.interp(
                        frame_indices,
                        good.astype(
                            np.float64
                        ),
                        values[
                            good
                        ],
                    )
                elif len(
                    good
                ) == 1:
                    motion[
                        :,
                        row,
                        col,
                        component
                    ] = values[
                        good[
                            0
                        ]
                    ]
                else:
                    motion[
                        :,
                        row,
                        col,
                        component
                    ] = 0.0

    # Hard-cut starts are exact zero motion.
    for start, _count in frame_segments:
        motion[
            int(
                start
            )
        ] = 0.0

    full_scale_x = (
        float(
            width
        )
        / float(
            analysis_width
        )
    )
    full_scale_y = (
        float(
            height
        )
        / float(
            analysis_height
        )
    )

    corrections = np.zeros_like(
        motion
    )
    frame_segment_index = np.zeros(
        frame_count,
        dtype=np.int32,
    )
    segment_crops = []
    segment_diagnostics = []

    for segment_index, (
        start,
        count,
    ) in enumerate(
        frame_segments
    ):
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

        frame_segment_index[
            start:end
        ] = int(
            segment_index
        )

        local_motion = motion[
            start:end
        ]
        local_correction, temporal = (
            _build_segment_correction(
                local_motion,
                fps=fps,
                amount=amount,
                global_authority=global_authority,
            )
        )
        local_correction[
            ...,
            0
        ] *= full_scale_x
        local_correction[
            ...,
            1
        ] *= full_scale_y

        crop_policy = _clip_crop_policy(
            local_correction,
            width=width,
            height=height,
            max_crop_percent=(
                max_crop_percent
            ),
        )
        local_correction *= (
            crop_policy[
                "gain"
            ]
        )
        corrections[
            start:end
        ] = local_correction
        segment_crops.append(
            float(
                crop_policy[
                    "actual_crop_percent"
                ]
            )
        )

        segment_diagnostics.append(
            {
                "segment_index": int(
                    segment_index
                ),
                "first_frame": int(
                    start
                ),
                "frame_count": int(
                    count
                ),
                **temporal,
                **crop_policy,
            }
        )

    diagnostics = {
        "algorithm": (
            "anchored-bundled-mesh-v1"
        ),
        "mode": "anchored",
        "motion_model": (
            "coarse-spatially-variant-translation-mesh-after-gyro"
        ),
        "grid_rows": int(
            grid_rows
        ),
        "grid_cols": int(
            grid_cols
        ),
        "analysis_width": int(
            analysis_width
        ),
        "analysis_height": int(
            analysis_height
        ),
        "amount": float(
            amount
        ),
        "global_authority": float(
            global_authority
        ),
        "max_crop_budget_percent": float(
            max_crop_percent
        ),
        "crop_semantics": (
            "maximum-budget; minimum-required-static-crop-per-hard-cut-clip"
        ),
        "per_frame_crop_or_zoom": False,
        "visual_scale_parameter": False,
        "visual_global_rotation_parameter": False,
        "keyframe_anchored_local_deformation": True,
        "single_final_image_warp": True,
        "valid_motion_ratio": float(
            np.mean(
                valid_frame
            )
        ),
        "mean_tracks": (
            float(
                np.mean(
                    track_counts
                )
            )
            if track_counts
            else 0.0
        ),
        "mean_accepted_tracks": (
            float(
                np.mean(
                    accepted_counts
                )
            )
            if accepted_counts
            else 0.0
        ),
        "median_forward_backward_error_px": (
            float(
                np.median(
                    roundtrip_values
                )
            )
            if roundtrip_values
            else 0.0
        ),
        "segment_crop_percent": [
            float(
                value
            )
            for value in segment_crops
        ],
        "segments": segment_diagnostics,
    }

    return AnchoredMeshPlan(
        corrections=(
            corrections.astype(
                np.float32
            )
        ),
        segment_crop_percent=tuple(
            segment_crops
        ),
        frame_segment_index=(
            frame_segment_index
        ),
        diagnostics=diagnostics,
    )


def render_anchored_stabilization(
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
            f"Could not open anchored stabilization input: {input_video}"
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
        plan.corrections
    ):
        cap.release()
        raise RuntimeError(
            "Anchored stabilization plan frame count does not match video"
        )

    base_x = np.broadcast_to(
        np.arange(
            width,
            dtype=np.float32,
        )[
            None,
            :
        ],
        (
            height,
            width,
        ),
    )
    base_y = np.broadcast_to(
        np.arange(
            height,
            dtype=np.float32,
        )[
            :,
            None
        ],
        (
            height,
            width,
        ),
    )

    command = [
        "ffmpeg",
        "-y",
        "-v",
        "error",
        "-f",
        "rawvideo",
        "-pix_fmt",
        "bgr24",
        "-s",
        f"{width}x{height}",
        "-r",
        f"{fps:.9f}",
        "-i",
        "-",
        "-an",
        "-c:v",
        "libx264",
        "-preset",
        str(
            preset
        ),
        "-crf",
        str(
            int(
                crf
            )
        ),
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        str(
            output_video
        ),
    ]

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
        for frame_index in range(
            frame_count
        ):
            ok, frame = cap.read()

            if not ok:
                raise RuntimeError(
                    "Anchored stabilization render ended before expected frame "
                    f"{frame_index}/{frame_count}"
                )

            grid = plan.corrections[
                frame_index
            ]
            dense_dx = cv2.resize(
                grid[
                    ...,
                    0
                ],
                (
                    width,
                    height,
                ),
                interpolation=cv2.INTER_LINEAR,
            )
            dense_dy = cv2.resize(
                grid[
                    ...,
                    1
                ],
                (
                    width,
                    height,
                ),
                interpolation=cv2.INTER_LINEAR,
            )

            # Correction describes where content should move. cv2.remap wants
            # the inverse sample location.
            map_x = (
                base_x
                - dense_dx
            )
            map_y = (
                base_y
                - dense_dy
            )
            warped = cv2.remap(
                frame,
                map_x,
                map_y,
                interpolation=cv2.INTER_LINEAR,
                borderMode=(
                    cv2.BORDER_REFLECT_101
                ),
            )

            segment_index = int(
                plan.frame_segment_index[
                    frame_index
                ]
            )
            crop_percent = float(
                plan.segment_crop_percent[
                    segment_index
                ]
            )

            if crop_percent > 0.01:
                retain = (
                    1.0
                    - crop_percent
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
                warped = warped[
                    y0:y0+crop_height,
                    x0:x0+crop_width,
                ]
                warped = cv2.resize(
                    warped,
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
                    warped.tobytes()
                )
            except BrokenPipeError as exc:
                raise RuntimeError(
                    "Anchored stabilization H.264 encoder stopped unexpectedly"
                ) from exc

            if (
                progress_callback
                and (
                    frame_index
                    == 0
                    or frame_index
                    + 1
                    == frame_count
                    or (
                        frame_index
                        + 1
                    )
                    % 15
                    == 0
                )
            ):
                progress_callback(
                    {
                        "stage": (
                            "anchored-visual-stabilization"
                        ),
                        "message": (
                            "Anchored mesh stabilization — "
                            f"{frame_index+1}/{frame_count} frames "
                            f"({100.0*(frame_index+1)/frame_count:.1f}%)"
                        ),
                        "frame": (
                            frame_index
                            + 1
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
            "Anchored stabilization H.264 encoding failed:\n"
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


def stabilize_rendered_video_anchored(
    input_video,
    output_video,
    frame_segments,
    *,
    amount,
    max_crop_percent=18.0,
    analysis_width=960,
    grid_rows=4,
    grid_cols=6,
    global_authority=1.0,
    crf=18,
    preset="medium",
    progress_callback=None,
):
    if progress_callback:
        progress_callback(
            {
                "stage": (
                    "anchored-visual-analysis"
                ),
                "message": (
                    "Analyzing anchored spatially-variant stabilization"
                ),
            }
        )

    analysis_started = (
        time.perf_counter()
    )
    plan = analyze_anchored_stabilization(
        input_video,
        frame_segments,
        amount=amount,
        max_crop_percent=(
            max_crop_percent
        ),
        analysis_width=(
            analysis_width
        ),
        grid_rows=(
            grid_rows
        ),
        grid_cols=(
            grid_cols
        ),
        global_authority=(
            global_authority
        ),
    )
    analysis_seconds = (
        time.perf_counter()
        - analysis_started
    )

    if progress_callback:
        actual_crop = max(
            plan.segment_crop_percent
            or (
                0.0,
            )
        )
        progress_callback(
            {
                "stage": (
                    "anchored-visual-stabilization"
                ),
                "message": (
                    "Applying anchored mesh stabilization; "
                    f"actual crop <= {actual_crop:.1f}%"
                ),
            }
        )

    result = render_anchored_stabilization(
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
