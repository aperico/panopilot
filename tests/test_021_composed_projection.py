import math

import cv2
import numpy as np

from panopilot.attitude import (
    rotate_equirectangular,
)
from panopilot.virtual_camera import (
    RectilinearProjector,
    VirtualCamera,
    reframe_equirectangular,
)


def _rotation_x(degrees):
    angle = math.radians(
        degrees
    )
    c = math.cos(angle)
    s = math.sin(angle)

    return np.array(
        [
            [1.0, 0.0, 0.0],
            [0.0, c, -s],
            [0.0, s, c],
        ],
        dtype=np.float64,
    )


def _rotation_z(degrees):
    angle = math.radians(
        degrees
    )
    c = math.cos(angle)
    s = math.sin(angle)

    return np.array(
        [
            [c, -s, 0.0],
            [s, c, 0.0],
            [0.0, 0.0, 1.0],
        ],
        dtype=np.float64,
    )


def _smooth_panorama(
    width=720,
    height=360,
):
    x = np.linspace(
        0.0,
        1.0,
        width,
        endpoint=False,
        dtype=np.float64,
    )[None, :]
    y = np.linspace(
        0.0,
        1.0,
        height,
        endpoint=True,
        dtype=np.float64,
    )[:, None]

    image = np.empty(
        (
            height,
            width,
            3,
        ),
        dtype=np.uint8,
    )
    image[..., 0] = (
        255.0 * x
    ).astype(
        np.uint8
    )
    image[..., 1] = (
        255.0 * y
    ).astype(
        np.uint8
    )
    image[..., 2] = (
        127.0
        + 100.0
        * np.sin(
            2.0
            * np.pi
            * x
        )
        * np.cos(
            np.pi
            * (
                y - 0.5
            )
        )
    ).clip(
        0.0,
        255.0,
    ).astype(
        np.uint8
    )

    return image


def test_projector_identity_matches_existing_virtual_camera():
    panorama = _smooth_panorama()
    camera = VirtualCamera(
        yaw_deg=25.0,
        pitch_deg=-8.0,
        fov_deg=78.0,
    )

    reference = reframe_equirectangular(
        panorama,
        camera,
        320,
        180,
    )

    projector = RectilinearProjector(
        panorama.shape[1],
        panorama.shape[0],
        320,
        180,
    )
    optimized = projector.reframe(
        panorama,
        camera,
    )

    difference = cv2.absdiff(
        reference,
        optimized,
    )

    # 0.24 computes the same projection geometry in float32. Sub-millipixel
    # map differences can move OpenCV bilinear rounding by one output value on
    # a very small number of pixels, so compare rendered equivalence rather
    # than requiring byte-identical intermediate arithmetic.
    assert int(
        difference.max()
    ) <= 1
    assert float(
        difference.mean()
    ) < 0.01


def test_composed_horizon_camera_matches_two_stage_geometry():
    panorama = _smooth_panorama()
    camera = VirtualCamera(
        yaw_deg=-35.0,
        pitch_deg=12.0,
        fov_deg=82.0,
    )
    content_rotation = (
        _rotation_z(
            7.0
        )
        @ _rotation_x(
            5.0
        )
    )

    reference = reframe_equirectangular(
        rotate_equirectangular(
            panorama,
            content_rotation,
        ),
        camera,
        320,
        180,
    )

    projector = RectilinearProjector(
        panorama.shape[1],
        panorama.shape[0],
        320,
        180,
    )
    optimized = projector.reframe(
        panorama,
        camera,
        content_rotation=(
            content_rotation
        ),
    )

    # The optimized path removes one bilinear resample. On a smooth panorama
    # the two mappings should therefore be geometrically equivalent with only
    # sub-LSB interpolation differences.
    difference = cv2.absdiff(
        reference,
        optimized,
    )

    assert int(
        difference.max()
    ) <= 1
    assert float(
        difference.mean()
    ) < 0.25


def test_projector_rejects_wrong_panorama_size():
    projector = RectilinearProjector(
        720,
        360,
        320,
        180,
    )

    wrong = np.zeros(
        (
            180,
            360,
            3,
        ),
        dtype=np.uint8,
    )

    try:
        projector.reframe(
            wrong,
            VirtualCamera(),
        )
    except ValueError as exc:
        assert "do not match projector" in str(
            exc
        )
    else:
        raise AssertionError(
            "Expected panorama size validation error"
        )
