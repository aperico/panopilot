"""
PanoPilot Virtual Camera.

Converts a 2:1 equirectangular panoramic representation into a conventional
rectilinear camera frame.

Canonical PanoPilot panoramic coordinate frame:

  +X = right
  +Y = up
  +Z = forward

User-facing camera semantics:

  yaw   > 0  -> look right
  pitch > 0  -> look up
  FOV        -> horizontal field of view

The projection is pinhole/rectilinear. Yaw/pitch/FOV are engineering controls
for SPIKE-02; the final UI will use direct manipulation.
"""
from __future__ import annotations

from dataclasses import dataclass
import math

import cv2
import numpy as np


@dataclass(frozen=True)
class VirtualCamera:
    yaw_deg: float = 0.0
    pitch_deg: float = 0.0
    fov_deg: float = 90.0

    def validate(self):
        if not -360.0 <= float(self.yaw_deg) <= 360.0:
            raise ValueError("yaw_deg must be between -360 and 360")
        if not -89.9 <= float(self.pitch_deg) <= 89.9:
            raise ValueError("pitch_deg must be between -89.9 and 89.9")
        if not 1.0 <= float(self.fov_deg) < 179.0:
            raise ValueError("fov_deg must be in [1, 179)")


def _rotation_y(angle_rad):
    c = math.cos(angle_rad)
    s = math.sin(angle_rad)
    return np.array([
        [c, 0.0, s],
        [0.0, 1.0, 0.0],
        [-s, 0.0, c],
    ], dtype=np.float64)


def _rotation_x(angle_rad):
    c = math.cos(angle_rad)
    s = math.sin(angle_rad)
    return np.array([
        [1.0, 0.0, 0.0],
        [0.0, c, -s],
        [0.0, s, c],
    ], dtype=np.float64)


def camera_rotation(camera: VirtualCamera):
    """
    Camera-local ray -> panorama/world ray.

    Positive user pitch means "look up". A standard positive X-axis rotation
    moves +Z toward -Y, so the internal rotation uses -pitch.
    """
    camera.validate()

    yaw = math.radians(float(camera.yaw_deg))
    pitch = math.radians(float(camera.pitch_deg))

    return _rotation_y(yaw) @ _rotation_x(-pitch)


def rectilinear_rays(width: int, height: int, horizontal_fov_deg: float):
    width = int(width)
    height = int(height)

    if width <= 0 or height <= 0:
        raise ValueError("output dimensions must be positive")

    fov = float(horizontal_fov_deg)

    if not 1.0 <= fov < 179.0:
        raise ValueError("horizontal FOV must be in [1, 179) degrees")

    aspect = width / height
    tan_half_h = math.tan(math.radians(fov) / 2.0)
    tan_half_v = tan_half_h / aspect

    x = (
        ((np.arange(width, dtype=np.float64) + 0.5) / width) * 2.0 - 1.0
    ) * tan_half_h

    y = (
        1.0 - ((np.arange(height, dtype=np.float64) + 0.5) / height) * 2.0
    ) * tan_half_v

    xx, yy = np.meshgrid(x, y)
    zz = np.ones_like(xx)

    rays = np.stack((xx, yy, zz), axis=-1)
    rays /= np.linalg.norm(rays, axis=-1, keepdims=True)

    return rays


def equirectangular_map(
    panorama_width: int,
    panorama_height: int,
    output_width: int,
    output_height: int,
    camera: VirtualCamera,
):
    panorama_width = int(panorama_width)
    panorama_height = int(panorama_height)

    if panorama_width <= 0 or panorama_height <= 0:
        raise ValueError("panorama dimensions must be positive")

    rays = rectilinear_rays(
        output_width,
        output_height,
        camera.fov_deg,
    )

    rotation = camera_rotation(camera)
    world = rays @ rotation.T

    wx = world[..., 0]
    wy = np.clip(world[..., 1], -1.0, 1.0)
    wz = world[..., 2]

    longitude = np.arctan2(wx, wz)
    latitude = np.arcsin(wy)

    map_x = (
        (longitude + np.pi)
        / (2.0 * np.pi)
        * panorama_width
        - 0.5
    )

    map_y = (
        (np.pi / 2.0 - latitude)
        / np.pi
        * panorama_height
        - 0.5
    )

    map_x = np.mod(map_x, panorama_width).astype(np.float32)
    map_y = np.clip(
        map_y,
        0.0,
        panorama_height - 1.0,
    ).astype(np.float32)

    return map_x, map_y



def _wrap_equirectangular_x_inplace(
    map_x,
    panorama_width,
):
    """
    Wrap equirectangular X coordinates in-place without general modulo.

    In the composed projector, atan2() constrains longitude to [-pi, +pi].
    After conversion to panorama pixels the X range is therefore bounded to
    approximately [-0.5, width-0.5]. General np.remainder() is substantially
    more expensive than needed for that known one-period range.

    Semantics are identical to:
        np.mod(map_x, panorama_width)

    for the projector's valid bounded input range:
      - negative values receive +width once;
      - values at/above width receive -width once.

    This preserves the accepted seam-wrap geometry while avoiding a costly
    per-pixel floating-point modulo operation.
    """
    width = np.float32(
        panorama_width
    )

    np.add(
        map_x,
        width,
        out=map_x,
        where=(
            map_x
            < np.float32(
                0.0
            )
        ),
    )
    np.subtract(
        map_x,
        width,
        out=map_x,
        where=(
            map_x
            >= width
        ),
    )

    return map_x


class RectilinearProjector:
    """
    Reusable equirectangular -> conventional-frame projector.

    The projector caches output-pixel normalized coordinates because Project
    Output Profile dimensions stay fixed throughout an export.

    ``content_rotation`` uses the same semantics as
    ``attitude.rotate_equirectangular``:

      rotation describes where source content should move on the sphere.

    Instead of first rotating the complete panorama and then performing a
    second perspective remap, this projector composes both inverse mappings:

      output rectilinear ray
          ↓ Virtual Camera
      leveled-panorama direction
          ↓ inverse content rotation
      original factory-panorama direction
          ↓
      one cv2.remap()

    This removes one full-resolution post-stitch resampling stage while
    preserving the canonical Virtual Camera and horizon-correction semantics.
    """

    def __init__(
        self,
        panorama_width,
        panorama_height,
        output_width,
        output_height,
    ):
        self.panorama_width = int(
            panorama_width
        )
        self.panorama_height = int(
            panorama_height
        )
        self.output_width = int(
            output_width
        )
        self.output_height = int(
            output_height
        )

        if (
            self.panorama_width <= 0
            or self.panorama_height <= 0
            or self.output_width <= 0
            or self.output_height <= 0
        ):
            raise ValueError(
                "projector dimensions must be positive"
            )

        # NDC pixel-center coordinates are independent of FOV and camera pose.
        #
        # Final export is a hot loop over millions of output pixels per frame,
        # so keep the reusable coordinate axes in float32 and also cache their
        # squares for ray normalization.
        self._nx = (
            (
                (
                    np.arange(
                        self.output_width,
                        dtype=np.float32,
                    )
                    + np.float32(
                        0.5
                    )
                )
                / np.float32(
                    self.output_width
                )
            )
            * np.float32(
                2.0
            )
            - np.float32(
                1.0
            )
        )[None, :]

        self._ny = (
            np.float32(
                1.0
            )
            - (
                (
                    (
                        np.arange(
                            self.output_height,
                            dtype=np.float32,
                        )
                        + np.float32(
                            0.5
                        )
                    )
                    / np.float32(
                        self.output_height
                    )
                )
                * np.float32(
                    2.0
                )
            )
        )[:, None]

        self._nx_squared = (
            self._nx
            * self._nx
        )
        self._ny_squared = (
            self._ny
            * self._ny
        )

        self._map_x_scale = np.float32(
            self.panorama_width
            / (
                2.0
                * math.pi
            )
        )
        self._map_y_scale = np.float32(
            self.panorama_height
            / math.pi
        )
        self._map_x_offset = np.float32(
            self.panorama_width
            / 2.0
            - 0.5
        )
        self._map_y_offset = np.float32(
            self.panorama_height
            / 2.0
            - 0.5
        )

    def map(
        self,
        camera: VirtualCamera,
        *,
        content_rotation=None,
    ):
        """
        Generate the equirectangular sampling map for one output frame.

        0.24 keeps the exact geometric model from the accepted 0.21 composed
        projection, but removes the largest avoidable CPU/memory costs:

        - no H×W×3 float64 ray tensor;
        - no two per-pixel 3×3 matrix multiplications;
        - camera and horizon rotations are combined once as a 3×3 matrix;
        - normalized camera-space axes are cached in float32;
        - longitude/latitude arrays are transformed in-place where possible.

        For an unnormalized camera ray ``u = [x, y, 1]`` and combined rotation
        matrix ``M``:

            source = normalize(u) · M

        Longitude is invariant to the positive normalization factor, so it can
        be computed directly from the unnormalized rotated X/Z components.
        Only the rotated Y component requires normalization before ``asin``.
        """
        camera.validate()

        aspect = np.float32(
            self.output_width
            / self.output_height
        )
        tan_half_h = np.float32(
            math.tan(
                math.radians(
                    float(
                        camera.fov_deg
                    )
                )
                / 2.0
            )
        )
        tan_half_v = np.float32(
            tan_half_h
            / aspect
        )

        # Previous semantics:
        #
        #   source = rays @ camera_matrix.T
        #   source = source @ content_rotation
        #
        # Combine the two 3x3 transforms once per frame instead of multiplying
        # every output ray twice.
        combined = camera_rotation(
            camera
        ).T

        if content_rotation is not None:
            content_rotation = np.asarray(
                content_rotation,
                dtype=np.float64,
            )

            if content_rotation.shape != (
                3,
                3,
            ):
                raise ValueError(
                    "content_rotation must be a 3x3 rotation matrix"
                )

            combined = (
                combined
                @ content_rotation
            )

        combined = np.asarray(
            combined,
            dtype=np.float32,
        )

        # Rotate the unnormalized camera ray [x, y, 1] analytically.
        # nx is 1×W and ny is H×1; NumPy broadcasting materializes only the
        # required H×W component arrays rather than one H×W×3 tensor.
        sx = (
            self._nx
            * (
                tan_half_h
                * combined[
                    0,
                    0,
                ]
            )
            + self._ny
            * (
                tan_half_v
                * combined[
                    1,
                    0,
                ]
            )
            + combined[
                2,
                0,
            ]
        )
        sy = (
            self._nx
            * (
                tan_half_h
                * combined[
                    0,
                    1,
                ]
            )
            + self._ny
            * (
                tan_half_v
                * combined[
                    1,
                    1,
                ]
            )
            + combined[
                2,
                1,
            ]
        )
        sz = (
            self._nx
            * (
                tan_half_h
                * combined[
                    0,
                    2,
                ]
            )
            + self._ny
            * (
                tan_half_v
                * combined[
                    1,
                    2,
                ]
            )
            + combined[
                2,
                2,
            ]
        )

        # Rotation preserves ray length, so normalize only the Y component
        # needed by latitude=asin(y). Longitude=atan2(x,z) is scale invariant.
        norm = (
            self._nx_squared
            * (
                tan_half_h
                * tan_half_h
            )
            + self._ny_squared
            * (
                tan_half_v
                * tan_half_v
            )
            + np.float32(
                1.0
            )
        )
        np.sqrt(
            norm,
            out=norm,
        )

        sy /= norm
        np.clip(
            sy,
            np.float32(
                -1.0
            ),
            np.float32(
                1.0
            ),
            out=sy,
        )

        # Reuse sx and sy as longitude/latitude and then directly as the final
        # float32 OpenCV map arrays.
        np.arctan2(
            sx,
            sz,
            out=sx,
        )
        np.arcsin(
            sy,
            out=sy,
        )

        sx *= self._map_x_scale
        sx += self._map_x_offset

        sy *= -self._map_y_scale
        sy += self._map_y_offset

        _wrap_equirectangular_x_inplace(
            sx,
            self.panorama_width,
        )
        np.clip(
            sy,
            np.float32(
                0.0
            ),
            np.float32(
                self.panorama_height
                - 1.0
            ),
            out=sy,
        )

        return (
            sx.astype(
                np.float32,
                copy=False,
            ),
            sy.astype(
                np.float32,
                copy=False,
            ),
        )

    def reframe(
        self,
        panorama,
        camera: VirtualCamera,
        *,
        content_rotation=None,
    ):
        if panorama is None:
            raise ValueError(
                "panorama is required"
            )

        actual_height, actual_width = (
            panorama.shape[:2]
        )

        if (
            actual_width
            != self.panorama_width
            or actual_height
            != self.panorama_height
        ):
            raise ValueError(
                "panorama dimensions do not match projector: "
                f"{actual_width}x{actual_height} != "
                f"{self.panorama_width}x{self.panorama_height}"
            )

        map_x, map_y = self.map(
            camera,
            content_rotation=content_rotation,
        )

        return cv2.remap(
            panorama,
            map_x,
            map_y,
            interpolation=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_REPLICATE,
        )


def reframe_equirectangular_composed(
    panorama,
    camera: VirtualCamera,
    width: int,
    height: int,
    *,
    content_rotation=None,
):
    """
    Convenience one-shot composed projector.

    Export code should prefer one reusable ``RectilinearProjector`` instance.
    """
    if panorama is None:
        raise ValueError(
            "panorama is required"
        )

    panorama_height, panorama_width = (
        panorama.shape[:2]
    )

    return RectilinearProjector(
        panorama_width,
        panorama_height,
        width,
        height,
    ).reframe(
        panorama,
        camera,
        content_rotation=content_rotation,
    )


def reframe_equirectangular(
    panorama,
    camera: VirtualCamera,
    width: int,
    height: int,
):
    if panorama is None:
        raise ValueError("panorama is required")

    panorama_height, panorama_width = panorama.shape[:2]

    map_x, map_y = equirectangular_map(
        panorama_width,
        panorama_height,
        width,
        height,
        camera,
    )

    return cv2.remap(
        panorama,
        map_x,
        map_y,
        interpolation=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_REPLICATE,
    )


def aspect_dimensions(aspect: str, width=None, height=None):
    if aspect not in ("16:9", "9:16"):
        raise ValueError("aspect must be '16:9' or '9:16'")

    ratio = 16.0 / 9.0 if aspect == "16:9" else 9.0 / 16.0

    if width is None and height is None:
        return (1920, 1080) if aspect == "16:9" else (1080, 1920)

    if width is not None:
        width = int(width)
        if width <= 0:
            raise ValueError("width must be positive")

    if height is not None:
        height = int(height)
        if height <= 0:
            raise ValueError("height must be positive")

    if width is None:
        width = int(round(height * ratio))
    elif height is None:
        height = int(round(width / ratio))
    else:
        actual = width / height
        if abs(actual - ratio) / ratio > 0.01:
            raise ValueError(
                f"{width}x{height} does not match requested aspect {aspect}"
            )

    return width, height
