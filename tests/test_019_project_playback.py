import pytest

from panopilot.project import (
    CameraPosition,
    Clip,
    Project,
)
from panopilot.project_player import (
    project_playback_start_time,
    project_state_at,
)
from panopilot.timeline import (
    build_project_timeline,
)


def _project():
    return Project(
        camera_motion_easing="ease-in-out",
        camera_motion_strength=0.7,
        clips=[
            Clip(
                id="clip-1",
                source="a.OSV",
                trim_in_source_time=1.0,
                trim_out_source_time=4.0,
                camera_positions=[
                    CameraPosition(
                        source_time=2.0,
                        yaw_deg=10.0,
                        pitch_deg=0.0,
                        fov_deg=90.0,
                    )
                ],
            ),
            Clip(
                id="clip-2",
                source="b.OSV",
                trim_in_source_time=2.0,
                trim_out_source_time=6.0,
                camera_positions=[
                    CameraPosition(
                        source_time=3.0,
                        yaw_deg=60.0,
                        pitch_deg=5.0,
                        fov_deg=70.0,
                    )
                ],
            ),
        ],
    )


def _spans(project):
    return build_project_timeline(
        project,
        {
            "clip-1": 10.0,
            "clip-2": 10.0,
        },
    )


def test_project_state_maps_first_clip():
    project = _project()
    state = project_state_at(
        project,
        _spans(project),
        1.5,
    )

    assert state.clip_id == "clip-1"
    assert state.clip_index == 0
    assert state.source_time == pytest.approx(
        2.5
    )
    assert state.clip_time == pytest.approx(
        1.5
    )
    assert state.camera_mode == "hold-single"
    assert state.camera_yaw_deg == pytest.approx(
        10.0
    )


def test_project_state_crosses_clip_boundary():
    project = _project()
    spans = _spans(project)

    # Clip 1 duration = 3s. Project 3.25s is 0.25s into Clip 2.
    state = project_state_at(
        project,
        spans,
        3.25,
    )

    assert state.clip_id == "clip-2"
    assert state.clip_index == 1
    assert state.source_time == pytest.approx(
        2.25
    )
    assert state.clip_time == pytest.approx(
        0.25
    )
    assert state.camera_yaw_deg == pytest.approx(
        60.0
    )


def test_project_state_exact_end_maps_final_clip_out():
    project = _project()
    spans = _spans(project)

    state = project_state_at(
        project,
        spans,
        7.0,
    )

    assert state.clip_id == "clip-2"
    assert state.source_time == pytest.approx(
        6.0
    )
    assert state.clip_time == pytest.approx(
        4.0
    )


def test_play_at_project_end_restarts_zero():
    assert project_playback_start_time(
        7.0,
        7.0,
    ) == pytest.approx(
        0.0
    )


def test_play_inside_project_resumes():
    assert project_playback_start_time(
        4.0,
        7.0,
    ) == pytest.approx(
        4.0
    )
