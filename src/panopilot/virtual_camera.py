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
