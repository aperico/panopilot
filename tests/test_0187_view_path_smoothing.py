import pytest

from panopilot.project import (
    CameraPosition,
)
from panopilot.view_path import (
    evaluate_view_path,
    smootherstep_alpha,
)


def pos(
    source_time,
    yaw,
    pitch=0.0,
    fov=90.0,
):
    return CameraPosition(
        source_time=source_time,
        yaw_deg=yaw,
        pitch_deg=pitch,
        fov_deg=fov,
    )


def test_smootherstep_exact_endpoints_and_midpoint():
    assert smootherstep_alpha(
        0.0
    ) == pytest.approx(0.0)

    assert smootherstep_alpha(
        0.5
    ) == pytest.approx(0.5)

    assert smootherstep_alpha(
        1.0
    ) == pytest.approx(1.0)


def test_smooth_path_moves_less_near_segment_start_than_linear():
    positions = [
        pos(0.0, 0.0),
        pos(2.0, 90.0),
    ]

    smooth = evaluate_view_path(
        positions,
        0.2,
    )
    linear = evaluate_view_path(
        positions,
        0.2,
        interpolation="linear",
    )

    assert smooth.alpha == pytest.approx(
        0.1
    )
    assert smooth.eased_alpha < smooth.alpha
    assert (
        abs(smooth.camera.yaw_deg)
        < abs(linear.camera.yaw_deg)
    )


def test_smooth_path_arrives_gently_at_camera_position():
    positions = [
        pos(0.0, 0.0),
        pos(2.0, 90.0),
        pos(4.0, 0.0),
    ]

    # Compare motion over a 20 ms interval near the Camera Position with an
    # equal interval around the middle of a segment.
    near_a = evaluate_view_path(
        positions,
        1.96,
    )
    near_b = evaluate_view_path(
        positions,
        1.98,
    )

    middle_a = evaluate_view_path(
        positions,
        0.96,
    )
    middle_b = evaluate_view_path(
        positions,
        0.98,
    )

    near_motion = abs(
        near_b.camera.yaw_deg
        - near_a.camera.yaw_deg
    )
    middle_motion = abs(
        middle_b.camera.yaw_deg
        - middle_a.camera.yaw_deg
    )

    assert near_motion < (
        middle_motion * 0.05
    )


def test_smooth_path_departs_gently_after_camera_position():
    positions = [
        pos(0.0, 0.0),
        pos(2.0, 90.0),
        pos(4.0, 0.0),
    ]

    a = evaluate_view_path(
        positions,
        2.02,
    )
    b = evaluate_view_path(
        positions,
        2.04,
    )

    assert (
        89.99
        < a.camera.yaw_deg
        <= 90.0
    )
    assert (
        89.9
        < b.camera.yaw_deg
        <= 90.0
    )


def test_smooth_and_linear_share_exact_midpoint():
    positions = [
        pos(
            0.0,
            10.0,
            pitch=-10.0,
            fov=60.0,
        ),
        pos(
            2.0,
            50.0,
            pitch=10.0,
            fov=100.0,
        ),
    ]

    smooth = evaluate_view_path(
        positions,
        1.0,
    )
    linear = evaluate_view_path(
        positions,
        1.0,
        interpolation="linear",
    )

    assert smooth.camera == linear.camera
    assert smooth.eased_alpha == pytest.approx(
        0.5
    )
    assert smooth.interpolation == "smooth"
    assert linear.interpolation == "linear"


def test_yaw_shortest_route_is_preserved_with_smoothing():
    sample = evaluate_view_path(
        [
            pos(0.0, 170.0),
            pos(2.0, -170.0),
        ],
        1.0,
    )

    assert abs(
        abs(sample.camera.yaw_deg)
        - 180.0
    ) < 1e-9
