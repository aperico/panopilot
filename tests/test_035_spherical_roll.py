import math

import cv2
import numpy as np

from panopilot.spherical_stabilization import (
    _estimate_rigid_motion,
    _smooth_rejected_velocity,
)
from panopilot.virtual_camera import (
    VirtualCamera,
    camera_rotation,
)


def test_virtual_camera_roll_rotates_about_local_forward_axis():
    camera = VirtualCamera(
        yaw_deg=0.0,
        pitch_deg=0.0,
        fov_deg=90.0,
        roll_deg=90.0,
    )
    rotation = camera_rotation(
        camera
    )

    world_right = rotation @ np.array(
        [
            1.0,
            0.0,
            0.0,
        ]
    )

    assert np.allclose(
        world_right,
        [
            0.0,
            1.0,
            0.0,
        ],
        atol=1e-9,
    )


def test_zero_roll_preserves_previous_yaw_pitch_rotation():
    a = camera_rotation(
        VirtualCamera(
            yaw_deg=31.0,
            pitch_deg=-12.0,
            fov_deg=78.0,
        )
    )
    b = camera_rotation(
        VirtualCamera(
            yaw_deg=31.0,
            pitch_deg=-12.0,
            fov_deg=78.0,
            roll_deg=0.0,
        )
    )

    assert np.array_equal(
        a,
        b,
    )


def test_rigid_visual_estimator_recovers_roll_and_center_translation():
    rng = np.random.default_rng(
        35
    )
    height = 360
    width = 640
    image = rng.integers(
        0,
        256,
        size=(
            height,
            width,
        ),
        dtype=np.uint8,
    )
    image = cv2.GaussianBlur(
        image,
        (
            3,
            3,
        ),
        0.0,
    )

    # cv2's image-coordinate angle convention is opposite the angle returned
    # by estimateAffinePartial2D/atan2(M[1,0], M[0,0]). A -2 degree OpenCV
    # warp therefore represents approximately +2 degrees in PanoPilot's
    # measured visual-roll convention.
    matrix = cv2.getRotationMatrix2D(
        (
            width / 2.0,
            height / 2.0,
        ),
        -2.0,
        1.005,
    )
    matrix[
        0,
        2,
    ] += 4.0
    matrix[
        1,
        2,
    ] -= 3.0

    moved = cv2.warpAffine(
        image,
        matrix,
        (
            width,
            height,
        ),
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_REFLECT_101,
    )

    estimate = _estimate_rigid_motion(
        image,
        moved,
    )

    assert estimate is not None
    assert abs(
        estimate[
            "roll_deg"
        ]
        - 2.0
    ) < 0.35
    assert abs(
        estimate[
            "dx"
        ]
        - 4.0
    ) < 1.5
    assert abs(
        estimate[
            "dy"
        ]
        + 3.0
    ) < 1.5
    # Scale is measured for diagnostics only; the correction model is rigid.
    assert abs(
        estimate[
            "nuisance_scale"
        ]
        - 1.005
    ) < 0.02


def test_roll_velocity_gets_crop_free_high_frequency_correction():
    count = 180
    motion = np.zeros(
        (
            count,
            3,
        ),
        dtype=np.float64,
    )
    motion[
        :,
        2,
    ] = np.tile(
        [
            1.2,
            -1.2,
        ],
        count // 2,
    )

    correction, diagnostics = (
        _smooth_rejected_velocity(
            motion,
            fps=30.0,
            amount=1.0,
        )
    )

    assert np.allclose(
        correction[
            :,
            :2,
        ],
        0.0,
        atol=1e-12,
    )
    assert float(
        np.max(
            np.abs(
                correction[
                    :,
                    2
                ]
            )
        )
    ) > 0.5
    assert diagnostics[
        "roll_sigma_seconds"
    ] > diagnostics[
        "translation_sigma_seconds"
    ]
