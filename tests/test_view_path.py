import pytest

from panopilot.project import CameraPosition
from panopilot.view_path import (
    evaluate_view_path,
    shortest_yaw_delta_deg,
)


def pos(t, yaw=0.0, pitch=0.0, fov=90.0):
    return CameraPosition(
        source_time=t,
        yaw_deg=yaw,
        pitch_deg=pitch,
        fov_deg=fov,
    )


def test_zero_positions_use_default_camera():
    sample = evaluate_view_path([], 5.0)

    assert sample.mode == "default"
    assert sample.camera.yaw_deg == 0.0
    assert sample.camera.pitch_deg == 0.0
    assert sample.camera.fov_deg == 90.0


def test_one_position_holds_for_whole_clip():
    positions = [
        pos(5.0, yaw=30.0, pitch=5.0, fov=70.0)
    ]

    before = evaluate_view_path(positions, 0.0)
    after = evaluate_view_path(positions, 10.0)

    for sample in (before, after):
        assert sample.mode == "hold-single"
        assert sample.camera.yaw_deg == 30.0
        assert sample.camera.pitch_deg == 5.0
        assert sample.camera.fov_deg == 70.0


def test_before_first_holds_first():
    sample = evaluate_view_path(
        [
            pos(2.0, yaw=20.0),
            pos(4.0, yaw=80.0),
        ],
        1.0,
    )

    assert sample.mode == "hold-first"
    assert sample.camera.yaw_deg == 20.0


def test_after_last_holds_last():
    sample = evaluate_view_path(
        [
            pos(2.0, yaw=20.0),
            pos(4.0, yaw=80.0),
        ],
        8.0,
    )

    assert sample.mode == "hold-last"
    assert sample.camera.yaw_deg == 80.0


def test_linear_midpoint_interpolation():
    sample = evaluate_view_path(
        [
            pos(
                0.0,
                yaw=10.0,
                pitch=-10.0,
                fov=60.0,
            ),
            pos(
                2.0,
                yaw=50.0,
                pitch=10.0,
                fov=100.0,
            ),
        ],
        1.0,
    )

    assert sample.mode == "interpolate"
    assert sample.alpha == pytest.approx(0.5)
    assert sample.camera.yaw_deg == pytest.approx(30.0)
    assert sample.camera.pitch_deg == pytest.approx(0.0)
    assert sample.camera.fov_deg == pytest.approx(80.0)


def test_yaw_crosses_seam_via_shortest_route():
    sample = evaluate_view_path(
        [
            pos(0.0, yaw=170.0),
            pos(2.0, yaw=-170.0),
        ],
        1.0,
    )

    assert abs(
        abs(sample.camera.yaw_deg) - 180.0
    ) < 1e-9


def test_shortest_yaw_delta():
    assert shortest_yaw_delta_deg(
        170.0,
        -170.0,
    ) == pytest.approx(20.0)

    assert shortest_yaw_delta_deg(
        -170.0,
        170.0,
    ) == pytest.approx(-20.0)

    assert shortest_yaw_delta_deg(
        10.0,
        190.0,
    ) == pytest.approx(180.0)


def test_exact_committed_camera_is_reproduced():
    sample = evaluate_view_path(
        [
            pos(
                1.0,
                yaw=22.0,
                pitch=3.0,
                fov=75.0,
            ),
            pos(
                3.0,
                yaw=99.0,
                pitch=-8.0,
                fov=65.0,
            ),
        ],
        1.0,
    )

    assert sample.camera.yaw_deg == 22.0
    assert sample.camera.pitch_deg == 3.0
    assert sample.camera.fov_deg == 75.0
