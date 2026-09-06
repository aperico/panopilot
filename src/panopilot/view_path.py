"""
PanoPilot View Path evaluation.

A View Path belongs to a Clip and is defined by that Clip's ordered Camera
Positions.

Iteration-1 deterministic behavior:

- zero Camera Positions: use the default Virtual Camera;
- one Camera Position: hold it for the whole Clip;
- before the first Camera Position: hold the first;
- after the last Camera Position: hold the last;
- between Camera Positions: interpolate.

Yaw follows the shortest angular route across the panoramic seam. Pitch and
horizontal FOV use linear interpolation for this first View Path increment.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional

from .project import CameraPosition, Clip
from .virtual_camera import VirtualCamera


DEFAULT_CAMERA = VirtualCamera(
    yaw_deg=0.0,
    pitch_deg=0.0,
    fov_deg=90.0,
)


@dataclass(frozen=True)
class ViewPathSample:
    source_time: float
    camera: VirtualCamera
    mode: str
    left_time: Optional[float] = None
    right_time: Optional[float] = None
    alpha: Optional[float] = None

    def to_dict(self):
        return {
            "source_time": float(self.source_time),
            "mode": self.mode,
            "left_time": self.left_time,
            "right_time": self.right_time,
            "alpha": self.alpha,
            "camera": {
                "yaw_deg": float(self.camera.yaw_deg),
                "pitch_deg": float(self.camera.pitch_deg),
                "fov_deg": float(self.camera.fov_deg),
            },
        }


def wrap_yaw_deg(value):
    return ((float(value) + 180.0) % 360.0) - 180.0


def shortest_yaw_delta_deg(start, end):
    delta = ((float(end) - float(start) + 180.0) % 360.0) - 180.0

    # Resolve the exact 180° ambiguity deterministically.
    if abs(delta + 180.0) <= 1e-12:
        delta = 180.0

    return delta


def _camera_from_position(position):
    return VirtualCamera(
        yaw_deg=float(position.yaw_deg),
        pitch_deg=float(position.pitch_deg),
        fov_deg=float(position.fov_deg),
    )


def interpolate_camera(left, right, alpha):
    alpha = max(0.0, min(1.0, float(alpha)))

    yaw = wrap_yaw_deg(
        float(left.yaw_deg)
        + alpha
        * shortest_yaw_delta_deg(
            left.yaw_deg,
            right.yaw_deg,
        )
    )

    pitch = (
        float(left.pitch_deg)
        + alpha
        * (
            float(right.pitch_deg)
            - float(left.pitch_deg)
        )
    )

    fov = (
        float(left.fov_deg)
        + alpha
        * (
            float(right.fov_deg)
            - float(left.fov_deg)
        )
    )

    return VirtualCamera(
        yaw_deg=yaw,
        pitch_deg=pitch,
        fov_deg=fov,
    )


def evaluate_view_path(
    positions: Iterable[CameraPosition],
    source_time: float,
    *,
    default_camera: VirtualCamera = DEFAULT_CAMERA,
):
    positions = sorted(
        list(positions),
        key=lambda p: p.source_time,
    )

    t = float(source_time)

    if not positions:
        return ViewPathSample(
            source_time=t,
            camera=default_camera,
            mode="default",
        )

    if len(positions) == 1:
        p = positions[0]

        return ViewPathSample(
            source_time=t,
            camera=_camera_from_position(p),
            mode="hold-single",
            left_time=float(p.source_time),
            right_time=float(p.source_time),
            alpha=0.0,
        )

    first = positions[0]
    last = positions[-1]

    if t <= float(first.source_time):
        return ViewPathSample(
            source_time=t,
            camera=_camera_from_position(first),
            mode="hold-first",
            left_time=float(first.source_time),
            right_time=float(first.source_time),
            alpha=0.0,
        )

    if t >= float(last.source_time):
        return ViewPathSample(
            source_time=t,
            camera=_camera_from_position(last),
            mode="hold-last",
            left_time=float(last.source_time),
            right_time=float(last.source_time),
            alpha=1.0,
        )

    for left, right in zip(
        positions[:-1],
        positions[1:],
    ):
        t0 = float(left.source_time)
        t1 = float(right.source_time)

        if t0 <= t <= t1:
            span = t1 - t0

            if span <= 0.0:
                return ViewPathSample(
                    source_time=t,
                    camera=_camera_from_position(right),
                    mode="hold-duplicate",
                    left_time=t0,
                    right_time=t1,
                    alpha=1.0,
                )

            alpha = (t - t0) / span

            return ViewPathSample(
                source_time=t,
                camera=interpolate_camera(
                    left,
                    right,
                    alpha,
                ),
                mode="interpolate",
                left_time=t0,
                right_time=t1,
                alpha=float(alpha),
            )

    return ViewPathSample(
        source_time=t,
        camera=_camera_from_position(last),
        mode="hold-last",
        left_time=float(last.source_time),
        right_time=float(last.source_time),
        alpha=1.0,
    )


def evaluate_clip_view_path(
    clip: Clip,
    source_time: float,
    *,
    default_camera: VirtualCamera = DEFAULT_CAMERA,
):
    return evaluate_view_path(
        clip.camera_positions,
        source_time,
        default_camera=default_camera,
    )
