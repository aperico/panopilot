from pathlib import Path

from panopilot.project import (
    Project,
    commit_camera_position,
    load_project,
    save_project,
)


def test_exploration_does_not_mutate_project_without_commit():
    project = Project()
    assert project.clips == []


def test_camera_position_commit_creates_clip_and_position():
    project = Project()

    result = commit_camera_position(
        project,
        "sample.OSV",
        source_time=2.0,
        yaw_deg=25.0,
        pitch_deg=-5.0,
        fov_deg=70.0,
        output_aspect="16:9",
    )

    assert result["created"] is True
    assert len(project.clips) == 1
    assert len(project.clips[0].camera_positions) == 1
    assert project.clips[0].camera_positions[0].source_time == 2.0


def test_second_commit_at_same_source_time_updates_not_duplicates():
    project = Project()

    commit_camera_position(
        project,
        "sample.OSV",
        source_time=2.0,
        yaw_deg=10.0,
        pitch_deg=0.0,
        fov_deg=90.0,
    )

    result = commit_camera_position(
        project,
        "sample.OSV",
        source_time=2.0,
        yaw_deg=40.0,
        pitch_deg=-8.0,
        fov_deg=65.0,
    )

    clip = project.clips[0]

    assert result["created"] is False
    assert len(clip.camera_positions) == 1
    assert clip.camera_positions[0].yaw_deg == 40.0
    assert clip.camera_positions[0].fov_deg == 65.0


def test_positions_are_sorted_by_source_time():
    project = Project()

    for t in (4.0, 1.0, 3.0):
        commit_camera_position(
            project,
            "sample.OSV",
            source_time=t,
            yaw_deg=t,
            pitch_deg=0.0,
            fov_deg=90.0,
        )

    assert [
        position.source_time
        for position in project.clips[0].camera_positions
    ] == [1.0, 3.0, 4.0]


def test_project_round_trip(tmp_path):
    path = tmp_path / "project.json"

    project = Project(output_aspect="9:16")

    commit_camera_position(
        project,
        "sample.OSV",
        source_time=2.5,
        yaw_deg=22.0,
        pitch_deg=4.0,
        fov_deg=75.0,
        output_aspect="9:16",
    )

    save_project(project, path)
    restored = load_project(path)

    assert restored.output_aspect == "9:16"
    assert len(restored.clips) == 1
    assert len(restored.clips[0].camera_positions) == 1

    position = restored.clips[0].camera_positions[0]
    assert position.source_time == 2.5
    assert position.yaw_deg == 22.0


def test_save_project_is_separate_from_source(tmp_path):
    source = tmp_path / "source.OSV"
    source.write_bytes(b"immutable-source")
    before = source.read_bytes()

    project = Project()

    commit_camera_position(
        project,
        str(source),
        source_time=1.0,
        yaw_deg=0.0,
        pitch_deg=0.0,
        fov_deg=90.0,
    )

    save_project(project, tmp_path / "project.json")

    assert source.read_bytes() == before
