import math

import cv2
import numpy as np

from panopilot.virtual_camera import (
    RectilinearProjector,
    VirtualCamera,
    camera_rotation,
)


def _reference_map(
    panorama_width,
    panorama_height,
    output_width,
    output_height,
    camera,
    *,
    content_rotation=None,
):
    aspect = (
        output_width
        / output_height
    )
    tan_half_h = math.tan(
        math.radians(
            camera.fov_deg
        )
        / 2.0
    )
    tan_half_v = (
        tan_half_h
        / aspect
    )

    x = (
        (
            (
                np.arange(
                    output_width,
                    dtype=np.float64,
                )
                + 0.5
            )
            / output_width
        )
        * 2.0
        - 1.0
    ) * tan_half_h

    y = (
        1.0
        - (
            (
                (
                    np.arange(
                        output_height,
                        dtype=np.float64,
                    )
                    + 0.5
                )
                / output_height
            )
            * 2.0
        )
    ) * tan_half_v

    xx, yy = np.meshgrid(
        x,
        y,
    )
    zz = np.ones_like(
        xx
    )
    rays = np.stack(
        (
            xx,
            yy,
            zz,
        ),
        axis=-1,
    )
    rays /= np.linalg.norm(
        rays,
        axis=-1,
        keepdims=True,
    )

    source = (
        rays
        @ camera_rotation(
            camera
        ).T
    )

    if content_rotation is not None:
        source = (
            source
            @ np.asarray(
                content_rotation,
                dtype=np.float64,
            )
        )

    longitude = np.arctan2(
        source[
            ...,
            0,
        ],
        source[
            ...,
            2,
        ],
    )
    latitude = np.arcsin(
        np.clip(
            source[
                ...,
                1,
            ],
            -1.0,
            1.0,
        )
    )

    map_x = (
        (
            longitude
            + np.pi
        )
        / (
            2.0
            * np.pi
        )
        * panorama_width
        - 0.5
    )
    map_y = (
        (
            np.pi
            / 2.0
            - latitude
        )
        / np.pi
        * panorama_height
        - 0.5
    )

    map_x = np.mod(
        map_x,
        panorama_width,
    ).astype(
        np.float32
    )
    map_y = np.clip(
        map_y,
        0.0,
        panorama_height
        - 1.0,
    ).astype(
        np.float32
    )

    return (
        map_x,
        map_y,
    )


def _rotation_x(
    degrees,
):
    angle = math.radians(
        degrees
    )
    c = math.cos(
        angle
    )
    s = math.sin(
        angle
    )

    return np.array(
        [
            [
                1.0,
                0.0,
                0.0,
            ],
            [
                0.0,
                c,
                -s,
            ],
            [
                0.0,
                s,
                c,
            ],
        ],
        dtype=np.float64,
    )


def test_optimized_map_matches_accepted_float64_geometry():
    projector = RectilinearProjector(
        3840,
        1920,
        640,
        360,
    )
    camera = VirtualCamera(
        yaw_deg=37.0,
        pitch_deg=-14.0,
        fov_deg=83.0,
    )
    rotation = _rotation_x(
        4.5
    )

    reference_x, reference_y = (
        _reference_map(
            3840,
            1920,
            640,
            360,
            camera,
            content_rotation=(
                rotation
            ),
        )
    )
    optimized_x, optimized_y = (
        projector.map(
            camera,
            content_rotation=(
                rotation
            ),
        )
    )

    assert float(
        np.max(
            np.abs(
                reference_x
                - optimized_x
            )
        )
    ) <= 0.001
    assert float(
        np.max(
            np.abs(
                reference_y
                - optimized_y
            )
        )
    ) <= 0.001


def test_optimized_projection_preserves_smooth_image_result():
    height = 360
    width = 720

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

    panorama = np.empty(
        (
            height,
            width,
            3,
        ),
        dtype=np.uint8,
    )
    panorama[..., 0] = (
        255.0
        * x
    ).astype(
        np.uint8
    )
    panorama[..., 1] = (
        255.0
        * y
    ).astype(
        np.uint8
    )
    panorama[..., 2] = (
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
                y
                - 0.5
            )
        )
    ).clip(
        0.0,
        255.0,
    ).astype(
        np.uint8
    )

    camera = VirtualCamera(
        yaw_deg=-28.0,
        pitch_deg=9.0,
        fov_deg=78.0,
    )
    rotation = _rotation_x(
        3.0
    )

    reference_x, reference_y = (
        _reference_map(
            width,
            height,
            320,
            180,
            camera,
            content_rotation=(
                rotation
            ),
        )
    )
    reference = cv2.remap(
        panorama,
        reference_x,
        reference_y,
        interpolation=(
            cv2.INTER_LINEAR
        ),
        borderMode=(
            cv2.BORDER_REPLICATE
        ),
    )

    optimized = RectilinearProjector(
        width,
        height,
        320,
        180,
    ).reframe(
        panorama,
        camera,
        content_rotation=(
            rotation
        ),
    )

    difference = cv2.absdiff(
        reference,
        optimized,
    )

    assert int(
        difference.max()
    ) <= 1
    assert float(
        difference.mean()
    ) < 0.01


def test_projector_uses_float32_cached_coordinate_axes():
    projector = RectilinearProjector(
        3840,
        1920,
        1920,
        1080,
    )

    assert (
        projector._nx.dtype
        == np.float32
    )
    assert (
        projector._ny.dtype
        == np.float32
    )
    assert (
        projector._nx_squared.dtype
        == np.float32
    )
    assert (
        projector._ny_squared.dtype
        == np.float32
    )
