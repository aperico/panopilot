from panopilot.project import (
    Project,
    commit_camera_position,
)
from panopilot.view_path import evaluate_clip_view_path


def test_two_committed_positions_define_intermediate_camera():
    project = Project()

    commit_camera_position(
        project,
        "sample.OSV",
        source_time=1.0,
        yaw_deg=0.0,
        pitch_deg=0.0,
        fov_deg=90.0,
    )

    commit_camera_position(
        project,
        "sample.OSV",
        source_time=3.0,
        yaw_deg=60.0,
        pitch_deg=10.0,
        fov_deg=70.0,
    )

    clip = project.clip_for_source("sample.OSV")

    sample = evaluate_clip_view_path(
        clip,
        2.0,
    )

    assert sample.camera.yaw_deg == 30.0
    assert sample.camera.pitch_deg == 5.0
    assert sample.camera.fov_deg == 80.0
