"""
Horizon leveling in PanoPilot's canonical factory-calibrated equirect frame.

Important coordinate distinction
---------------------------------

PanoPilot's current factory-calibrated panorama uses the following canonical
equirectangular frame:

  Xeq = image/right
  Yeq = image/up
  Zeq = image/forward

The DJI IMU body frame observed in the current Osmo 360 sample is aligned as:

  Ximu -> +Xeq
  Yimu -> +Zeq
  Zimu -> -Yeq

Equivalently:

  equirect right   = IMU +X
  equirect up      = IMU -Z
  equirect forward = IMU +Y

This differs from the earlier v0.4 experiment, which reused the coordinate
transform of a different panoramic-stitch baseline. The v0.4 transform yielded
an impossible ~90-degree correction on an almost-level image.

The mapping below is also consistent with the embedded accelerometer on the
current sample: when the panorama is visually close to level, the measured
"up" vector maps close to equirect +Y.

This module applies horizon correction as a true spherical rotation, never as
a 2D image rotation.
"""
from __future__ import annotations

import math

import cv2
import numpy as np


WORLD_DOWN = np.array([0.0, 0.0, 1.0], dtype=np.float64)
EQUIRECT_DOWN = np.array([0.0, -1.0, 0.0], dtype=np.float64)

# DJI IMU body -> PanoPilot factory-calibrated equirect frame.
IMU_TO_FACTORY_EQUIRECT = np.array([
    [1.0, 0.0,  0.0],   # Xeq = +Ximu
    [0.0, 0.0, -1.0],   # Yeq = -Zimu
    [0.0, 1.0,  0.0],   # Zeq = +Yimu
], dtype=np.float64)


def quat_to_matrix(q):
    q = np.asarray(q, dtype=np.float64)
    q = q / np.linalg.norm(q)

    w, x, y, z = q

    return np.array([
        [1 - 2*(y*y + z*z), 2*(x*y - z*w),     2*(x*z + y*w)],
        [2*(x*y + z*w),     1 - 2*(x*x + z*z), 2*(y*z - x*w)],
        [2*(x*z - y*w),     2*(y*z + x*w),     1 - 2*(x*x + y*y)],
    ], dtype=np.float64)


def minimal_rotation(a, b):
    a = np.asarray(a, dtype=np.float64)
    b = np.asarray(b, dtype=np.float64)

    a = a / np.linalg.norm(a)
    b = b / np.linalg.norm(b)

    v = np.cross(a, b)
    c = float(np.dot(a, b))
    s = float(np.linalg.norm(v))

    if s < 1e-9:
        if c > 0:
            return np.eye(3, dtype=np.float64)

        # 180 degrees: choose an axis orthogonal to a.
        basis = np.array([1.0, 0.0, 0.0])
        if abs(float(np.dot(a, basis))) > 0.9:
            basis = np.array([0.0, 0.0, 1.0])

        axis = np.cross(a, basis)
        axis /= np.linalg.norm(axis)
        K = np.array([
            [0.0, -axis[2], axis[1]],
            [axis[2], 0.0, -axis[0]],
            [-axis[1], axis[0], 0.0],
        ])
        return np.eye(3) + 2.0 * (K @ K)

    vx = np.array([
        [0.0, -v[2], v[1]],
        [v[2], 0.0, -v[0]],
        [-v[1], v[0], 0.0],
    ])

    return np.eye(3) + vx + (vx @ vx) * (1.0 / (1.0 + c))


def rotation_strength(rotation, strength):
    strength = max(0.0, min(1.0, float(strength)))

    if strength <= 1e-9:
        return np.eye(3, dtype=np.float64)

    if strength >= 1.0 - 1e-9:
        return rotation

    angle = math.acos(
        max(-1.0, min(1.0, (float(np.trace(rotation)) - 1.0) / 2.0))
    )

    if angle < 1e-9:
        return np.eye(3, dtype=np.float64)

    axis = np.array([
        rotation[2, 1] - rotation[1, 2],
        rotation[0, 2] - rotation[2, 0],
        rotation[1, 0] - rotation[0, 1],
    ], dtype=np.float64)

    norm = float(np.linalg.norm(axis))
    if norm < 1e-9:
        return rotation

    axis /= norm
    angle *= strength

    K = np.array([
        [0.0, -axis[2], axis[1]],
        [axis[2], 0.0, -axis[0]],
        [-axis[1], axis[0], 0.0],
    ])

    return (
        np.eye(3)
        + math.sin(angle) * K
        + (1.0 - math.cos(angle)) * (K @ K)
    )



def gravity_equirectangular(quaternion):
    """
    Return DJI WORLD_DOWN expressed in PanoPilot's canonical factory
    equirectangular frame.
    """
    body_to_world = quat_to_matrix(quaternion)

    gravity_body = body_to_world.T @ WORLD_DOWN
    gravity_equirect = IMU_TO_FACTORY_EQUIRECT @ gravity_body

    norm = float(np.linalg.norm(gravity_equirect))
    if norm < 1e-12:
        raise ValueError("Invalid zero-length gravity vector")

    return gravity_equirect / norm


def horizon_correction_from_gravity(gravity_equirect, strength=1.0):
    """
    Compute the minimal spherical rotation that sends a measured/smoothed
    gravity vector to equirectangular image-down.
    """
    gravity_equirect = np.asarray(gravity_equirect, dtype=np.float64)

    norm = float(np.linalg.norm(gravity_equirect))
    if norm < 1e-12:
        raise ValueError("Invalid zero-length gravity vector")

    gravity_equirect = gravity_equirect / norm

    full = minimal_rotation(gravity_equirect, EQUIRECT_DOWN)
    correction = rotation_strength(full, strength)

    tilt = math.degrees(
        math.acos(
            max(
                -1.0,
                min(1.0, float(np.dot(gravity_equirect, EQUIRECT_DOWN))),
            )
        )
    )

    return correction, {
        "gravity_equirect": [float(v) for v in gravity_equirect],
        "tilt_before_deg": float(tilt),
        "strength": float(strength),
    }


def smooth_unit_vectors_centered(vectors, sigma_frames):
    """
    Centered Gaussian smoothing for a sequence of unit vectors.

    The filter is zero-phase because the complete source telemetry is known
    before playback/rendering. Therefore smoothing does not introduce the
    temporal lag of a causal low-pass filter.

    ``sigma_frames`` is the Gaussian sigma in output-frame units.
    A value <= 0 disables smoothing.
    """
    vectors = np.asarray(vectors, dtype=np.float64)

    if vectors.ndim != 2 or vectors.shape[1] != 3:
        raise ValueError("Expected an Nx3 vector sequence")

    if len(vectors) == 0:
        return vectors.copy()

    sigma_frames = float(sigma_frames)

    if sigma_frames <= 1e-9:
        out = vectors.copy()
        norms = np.linalg.norm(out, axis=1, keepdims=True)
        norms = np.where(norms < 1e-12, 1.0, norms)
        return out / norms

    radius = max(1, int(math.ceil(3.0 * sigma_frames)))
    x = np.arange(-radius, radius + 1, dtype=np.float64)

    kernel = np.exp(-0.5 * (x / sigma_frames) ** 2)
    kernel /= kernel.sum()

    padded = np.pad(
        vectors,
        ((radius, radius), (0, 0)),
        mode="edge",
    )

    out = np.column_stack([
        np.convolve(padded[:, component], kernel, mode="valid")
        for component in range(3)
    ])

    norms = np.linalg.norm(out, axis=1, keepdims=True)
    norms = np.where(norms < 1e-12, 1.0, norms)

    return out / norms


def horizon_correction(quaternion, strength=1.0):
    """
    Return (rotation_matrix, diagnostics) from one DJI quaternion.

    DJI quaternion maps IMU BODY -> WORLD:
      v_world = R_body_to_world @ v_body

    WORLD_DOWN is transformed back into camera/body coordinates and then into
    PanoPilot's canonical factory equirectangular frame.
    """
    body_to_world = quat_to_matrix(quaternion)
    gravity_body = body_to_world.T @ WORLD_DOWN

    gravity_equirect = IMU_TO_FACTORY_EQUIRECT @ gravity_body
    gravity_equirect /= np.linalg.norm(gravity_equirect)

    correction, diagnostics = horizon_correction_from_gravity(
        gravity_equirect,
        strength=strength,
    )

    diagnostics["gravity_body"] = [float(v) for v in gravity_body]

    return correction, diagnostics

def rotate_equirectangular(image, rotation):
    """
    Apply a spherical CONTENT rotation to a 2:1 equirectangular image.

    ``rotation`` describes where source content shall move on the sphere.

    In inverse image mapping, every output ray must therefore sample the
    source at the inverse rotation:

      source_direction = rotation.T @ output_direction

    The previous implementation incorrectly used ``rotation`` instead of its
    inverse. That applied horizon correction in the opposite direction and
    effectively amplified camera tilt.

    Horizontal sampling wraps across the panorama seam.
    """
    height, width = image.shape[:2]

    lon = (
        (np.arange(width, dtype=np.float64) + 0.5)
        / width * 2.0 * np.pi
        - np.pi
    )
    lat = (
        np.pi / 2.0
        - (np.arange(height, dtype=np.float64) + 0.5)
        / height * np.pi
    )

    cos_lat = np.cos(lat)[:, None]
    sin_lat = np.sin(lat)[:, None]

    directions = np.stack([
        cos_lat * np.sin(lon)[None, :],
        np.broadcast_to(sin_lat, (height, width)),
        cos_lat * np.cos(lon)[None, :],
    ], axis=-1)

    # Row-vector equivalent of source_direction = rotation.T @ output_direction.
    # For row vectors: d_source = d_output @ rotation.
    source = directions @ np.asarray(rotation, dtype=np.float64)

    sx = source[..., 0]
    sy = source[..., 1]
    sz = source[..., 2]

    source_lon = np.arctan2(sx, sz)
    source_lat = np.arcsin(np.clip(sy, -1.0, 1.0))

    map_x = (
        (source_lon + np.pi)
        / (2.0 * np.pi)
        * width
        - 0.5
    )
    map_y = (
        (np.pi / 2.0 - source_lat)
        / np.pi
        * height
        - 0.5
    )

    map_x = np.mod(map_x, width).astype(np.float32)
    map_y = map_y.astype(np.float32)

    return cv2.remap(
        image,
        map_x,
        map_y,
        interpolation=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_WRAP,
    )
