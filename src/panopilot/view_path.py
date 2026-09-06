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

Yaw follows the shortest angular route across the panoramic seam.

Between Camera Positions, PanoPilot applies quintic ease-in/ease-out
("smootherstep") to the normalized segment time before interpolating yaw,
pitch, and horizontal FOV. This gives zero velocity and zero acceleration at
Camera Positions, avoiding the harsh change of motion that occurs when a
piecewise-linear camera path hits a reframing point.
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
    eased_alpha: Optional[float] = None
    interpolation: Optional[str] = None
    strength: Optional[float] = None

    def to_dict(self):
        return {
            "source_time": float(self.source_time),
            "mode": self.mode,
            "left_time": self.left_time,
            "right_time": self.right_time,
            "alpha": self.alpha,
            "eased_alpha": self.eased_alpha,
            "interpolation": self.interpolation,
            "strength": self.strength,
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


def smootherstep_alpha(alpha):
    """Quintic ease-in/ease-out: zero velocity and acceleration at both ends."""
    a = max(0.0, min(1.0, float(alpha)))
    return (
        a * a * a
        * (
            a
            * (
                a * 6.0
                - 15.0
            )
            + 10.0
        )
    )


def smoothstep_alpha(alpha):
    """Cubic ease-in/ease-out: zero velocity at both ends."""
    a = max(0.0, min(1.0, float(alpha)))
    return a * a * (3.0 - 2.0 * a)


def ease_in_alpha(alpha):
    """Cubic ease-in: slow departure, faster arrival."""
    a = max(0.0, min(1.0, float(alpha)))
    return a * a * a


def ease_out_alpha(alpha):
    """Cubic ease-out: faster departure, gentle arrival."""
    a = max(0.0, min(1.0, float(alpha)))
    inv = 1.0 - a
    return 1.0 - inv * inv * inv


def easing_curve_alpha(
    alpha,
    *,
    interpolation="smooth",
):
    """
    Evaluate one normalized easing preset.

    Presets:
      smooth       quintic ease-in/out; gentlest setpoint arrival/departure
      ease-in-out  cubic ease-in/out
      ease-in      slow departure, fast arrival
      ease-out     fast departure, gentle arrival
      linear       constant-speed interpolation
    """
    a = max(0.0, min(1.0, float(alpha)))

    if interpolation == "smooth":
        return smootherstep_alpha(a)

    if interpolation == "ease-in-out":
        return smoothstep_alpha(a)

    if interpolation == "ease-in":
        return ease_in_alpha(a)

    if interpolation == "ease-out":
        return ease_out_alpha(a)

    if interpolation == "linear":
        return a

    raise ValueError(
        "interpolation must be one of: "
        "smooth, ease-in-out, ease-in, ease-out, linear"
    )


def interpolation_alpha(
    alpha,
    *,
    interpolation="smooth",
    strength=1.0,
):
    """
    Blend between raw linear time and the selected easing curve.

    strength = 0.0 -> completely linear
    strength = 1.0 -> full selected easing
    """
    a = max(0.0, min(1.0, float(alpha)))
    strength = max(0.0, min(1.0, float(strength)))

    curved = easing_curve_alpha(
        a,
        interpolation=interpolation,
    )

    return (
        a
        + strength
        * (
            curved - a
        )
    )


def interpolate_camera(
    left,
    right,
    alpha,
    *,
    interpolation="smooth",
    strength=1.0,
):
    alpha = interpolation_alpha(
        alpha,
        interpolation=interpolation,
        strength=strength,
    )

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
    interpolation: str = "smooth",
    strength: float = 1.0,
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
            interpolation=str(interpolation),
            strength=float(strength),
        )

    if len(positions) == 1:
        p = positions[0]

        return ViewPathSample(
            source_time=t,
            camera=_camera_from_position(p),
            mode="hold-single",
            interpolation=str(interpolation),
            strength=float(strength),
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
            interpolation=str(interpolation),
            strength=float(strength),
            left_time=float(first.source_time),
            right_time=float(first.source_time),
            alpha=0.0,
        )

    if t >= float(last.source_time):
        return ViewPathSample(
            source_time=t,
            camera=_camera_from_position(last),
            mode="hold-last",
            interpolation=str(interpolation),
            strength=float(strength),
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
                    interpolation=str(interpolation),
            strength=float(strength),
                    left_time=t0,
                    right_time=t1,
                    alpha=1.0,
                )

            alpha = (t - t0) / span
            eased_alpha = interpolation_alpha(
                alpha,
                interpolation=interpolation,
                strength=strength,
            )

            return ViewPathSample(
                source_time=t,
                camera=interpolate_camera(
                    left,
                    right,
                    alpha,
                    interpolation=interpolation,
                    strength=strength,
                ),
                mode="interpolate",
                left_time=t0,
                right_time=t1,
                alpha=float(alpha),
                eased_alpha=float(
                    eased_alpha
                ),
                interpolation=str(
                    interpolation
                ),
                strength=float(
                    strength
                ),
            )

    return ViewPathSample(
        source_time=t,
        camera=_camera_from_position(last),
        mode="hold-last",
        interpolation=str(interpolation),
        left_time=float(last.source_time),
        right_time=float(last.source_time),
        alpha=1.0,
    )


def evaluate_clip_view_path(
    clip: Clip,
    source_time: float,
    *,
    default_camera: VirtualCamera = DEFAULT_CAMERA,
    interpolation: str = "smooth",
    strength: float = 1.0,
):
    """Evaluate only Camera Positions active in the current Clip trim."""
    return evaluate_view_path(
        clip.active_camera_positions(),
        source_time,
        default_camera=default_camera,
        interpolation=interpolation,
        strength=strength,
    )
