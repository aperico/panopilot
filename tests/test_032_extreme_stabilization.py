import numpy as np

from panopilot.extreme_stabilization import (
    _correction_matrix,
    _matrix_fits_crop,
    _pass_parameters,
)


def test_identity_fits_extreme_crop():
    matrix = np.eye(
        3,
        dtype=np.float64,
    )

    assert _matrix_fits_crop(
        matrix,
        1920,
        1080,
        45.0,
    )


def test_extreme_correction_supports_scale_rotation_translation():
    matrix = _correction_matrix(
        1920,
        1080,
        50.0,
        -25.0,
        2.0,
        np.log(
            1.02
        ),
    )

    assert matrix.shape == (
        3,
        3,
    )
    assert not np.allclose(
        matrix,
        np.eye(
            3
        ),
    )


def test_long_extreme_path_smoothing_suppresses_alternating_jitter():
    frame_count = 120
    jitter = np.tile(
        np.array(
            [
                3.0,
                -3.0,
            ]
        ),
        frame_count // 2,
    )

    motion = {
        "dx": jitter.copy(),
        "dy": np.zeros(
            frame_count
        ),
        "angle_deg": np.zeros(
            frame_count
        ),
        "log_scale": np.zeros(
            frame_count
        ),
        "analysis_width": 960,
        "analysis_height": 540,
        "full_width": 1920,
        "full_height": 1080,
    }

    params = _pass_parameters(
        motion,
        [
            (
                0,
                frame_count,
            )
        ],
        fps=30.0,
        amount=1.0,
        sigma_seconds=1.8,
    )

    # Strong correction should oppose the cumulative alternating path rather
    # than leave it untouched.
    assert float(
        np.max(
            np.abs(
                params[
                    "dx"
                ]
            )
        )
    ) > 1.0
    assert params[
        "gain"
    ] == 1.0
