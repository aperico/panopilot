import numpy as np

from panopilot.anchored_stabilization import (
    _build_segment_correction,
    _clip_crop_policy,
    _keyframe_envelope,
    _spatial_regularize,
)


def test_keyframe_envelope_is_zero_and_slope_safe_at_anchors():
    envelope = _keyframe_envelope(
        61,
        30,
    )

    assert envelope[0] == 0.0
    assert envelope[30] == 0.0
    assert abs(float(envelope[60])) < 1e-12
    assert envelope[15] > 0.99
    assert envelope[45] > 0.99


def test_spatial_regularization_reduces_single_vertex_spike():
    field = np.zeros(
        (
            4,
            6,
            2,
        ),
        dtype=np.float64,
    )
    field[2, 3, 0] = 20.0

    out = _spatial_regularize(
        field,
        iterations=2,
        neighbor_strength=0.35,
    )

    assert (
        abs(
            out[2, 3, 0]
        )
        < 20.0
    )
    assert (
        abs(
            out[2, 2, 0]
        )
        > 0.0
    )


def test_uniform_jitter_produces_uniform_mesh_correction():
    count = 120
    motion = np.zeros(
        (
            count,
            4,
            6,
            2,
        ),
        dtype=np.float64,
    )
    jitter = np.tile(
        np.array(
            [
                3.0,
                -3.0,
            ],
            dtype=np.float64,
        ),
        count // 2,
    )
    motion[:, :, :, 0] = (
        jitter[
            :,
            None,
            None
        ]
    )

    correction, diagnostics = (
        _build_segment_correction(
            motion,
            fps=30.0,
            amount=1.0,
        )
    )

    spread = np.max(
        correction[..., 0],
        axis=(
            1,
            2,
        ),
    ) - np.min(
        correction[..., 0],
        axis=(
            1,
            2,
        ),
    )

    assert float(
        np.max(
            np.abs(
                spread
            )
        )
    ) < 1e-8
    assert diagnostics[
        "keyframe_spacing_seconds"
    ] >= 0.9


def test_crop_argument_is_budget_not_forced_crop():
    correction = np.zeros(
        (
            10,
            4,
            6,
            2,
        ),
        dtype=np.float64,
    )
    correction[..., 0] = 20.0
    correction[..., 1] = 10.0

    policy = _clip_crop_policy(
        correction,
        width=1920,
        height=1080,
        max_crop_percent=25.0,
    )

    assert policy[
        "gain"
    ] == 1.0
    assert (
        policy[
            "actual_crop_percent"
        ]
        < 10.0
    )
    assert (
        policy[
            "actual_crop_percent"
        ]
        < 25.0
    )
