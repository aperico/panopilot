import json

import pytest

from panopilot.project import (
    Project,
    load_project,
    save_project,
)
from panopilot.session import ProjectSession
from panopilot.project import CameraPosition
from panopilot.view_path import (
    evaluate_view_path,
    interpolation_alpha,
)


def pos(t, yaw):
    return CameraPosition(
        source_time=t,
        yaw_deg=yaw,
        pitch_deg=0.0,
        fov_deg=90.0,
    )


@pytest.mark.parametrize(
    "mode",
    [
        "smooth",
        "ease-in-out",
        "ease-in",
        "ease-out",
        "linear",
    ],
)
def test_all_easing_modes_preserve_endpoints(mode):
    assert interpolation_alpha(
        0.0,
        interpolation=mode,
        strength=1.0,
    ) == pytest.approx(0.0)

    assert interpolation_alpha(
        1.0,
        interpolation=mode,
        strength=1.0,
    ) == pytest.approx(1.0)


def test_strength_zero_is_linear_for_any_curve():
    for mode in (
        "smooth",
        "ease-in-out",
        "ease-in",
        "ease-out",
    ):
        assert interpolation_alpha(
            0.2,
            interpolation=mode,
            strength=0.0,
        ) == pytest.approx(0.2)


def test_half_strength_blends_linear_and_curve():
    full = interpolation_alpha(
        0.2,
        interpolation="ease-in",
        strength=1.0,
    )
    half = interpolation_alpha(
        0.2,
        interpolation="ease-in",
        strength=0.5,
    )

    assert half == pytest.approx(
        0.2
        + 0.5
        * (
            full - 0.2
        )
    )


def test_ease_in_and_out_have_expected_bias():
    ease_in = interpolation_alpha(
        0.25,
        interpolation="ease-in",
        strength=1.0,
    )
    ease_out = interpolation_alpha(
        0.25,
        interpolation="ease-out",
        strength=1.0,
    )

    assert ease_in < 0.25
    assert ease_out > 0.25


def test_project_camera_motion_round_trip(tmp_path):
    path = tmp_path / "project.json"
    project = Project(
        camera_motion_easing="ease-in-out",
        camera_motion_strength=0.65,
    )

    save_project(
        project,
        path,
    )
    loaded = load_project(
        path
    )

    assert (
        loaded.camera_motion_easing
        == "ease-in-out"
    )
    assert loaded.camera_motion_strength == pytest.approx(
        0.65
    )


def test_schema_v2_migrates_with_current_smooth_default(tmp_path):
    path = tmp_path / "v2.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "output_frame": {
                    "aspect": "16:9"
                },
                "clips": [],
            }
        ),
        encoding="utf-8",
    )

    project = load_project(
        path
    )

    assert project.schema_version == 3
    assert project.camera_motion_easing == "smooth"
    assert project.camera_motion_strength == pytest.approx(
        1.0
    )


def test_camera_motion_session_change_is_undoable():
    session = ProjectSession(
        Project()
    )

    transaction = session.set_camera_motion(
        easing="ease-out",
        strength=0.4,
    )

    assert transaction["changed"] is True
    assert (
        session.project.camera_motion_easing
        == "ease-out"
    )
    assert session.project.camera_motion_strength == pytest.approx(
        0.4
    )

    session.undo()

    assert (
        session.project.camera_motion_easing
        == "smooth"
    )
    assert session.project.camera_motion_strength == pytest.approx(
        1.0
    )


def test_view_path_strength_changes_camera_position_between_points():
    positions = [
        pos(0.0, 0.0),
        pos(2.0, 90.0),
    ]

    linear = evaluate_view_path(
        positions,
        0.5,
        interpolation="smooth",
        strength=0.0,
    )
    smooth = evaluate_view_path(
        positions,
        0.5,
        interpolation="smooth",
        strength=1.0,
    )

    assert linear.camera.yaw_deg == pytest.approx(
        22.5
    )
    assert smooth.camera.yaw_deg < linear.camera.yaw_deg
    assert smooth.strength == pytest.approx(
        1.0
    )
