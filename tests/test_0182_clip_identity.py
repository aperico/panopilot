import pytest

from panopilot.project import (
    Clip,
    Project,
    resolve_project_clip,
)
from panopilot.session import ProjectSession
from panopilot.view_path import (
    evaluate_clip_view_path,
)


def test_one_setpoint_holds_entire_selected_clip():
    project = Project(
        clips=[
            Clip(
                id="clip-1",
                source="a.OSV",
            ),
            Clip(
                id="clip-2",
                source="b.OSV",
            ),
        ]
    )
    session = ProjectSession(project)

    transaction = (
        session.commit_camera_position_to_clip(
            "clip-2",
            source_time=5.0,
            yaw_deg=73.0,
            pitch_deg=-8.0,
            fov_deg=68.0,
        )
    )

    assert transaction["changed"] is True

    clip = session.project.clip_for_id(
        "clip-2"
    )

    for source_time in (
        0.0,
        1.0,
        5.0,
        10.0,
    ):
        sample = evaluate_clip_view_path(
            clip,
            source_time,
        )

        assert sample.mode == "hold-single"
        assert sample.camera.yaw_deg == 73.0
        assert sample.camera.pitch_deg == -8.0
        assert sample.camera.fov_deg == 68.0

    assert (
        session.project.clip_for_id(
            "clip-1"
        ).camera_positions
        == []
    )


def test_two_setpoints_interpolate_only_selected_clip():
    project = Project(
        clips=[
            Clip(
                id="clip-1",
                source="a.OSV",
            ),
            Clip(
                id="clip-2",
                source="b.OSV",
            ),
        ]
    )
    session = ProjectSession(project)

    session.commit_camera_position_to_clip(
        "clip-2",
        source_time=2.0,
        yaw_deg=10.0,
        pitch_deg=0.0,
        fov_deg=90.0,
    )
    session.commit_camera_position_to_clip(
        "clip-2",
        source_time=4.0,
        yaw_deg=30.0,
        pitch_deg=10.0,
        fov_deg=70.0,
    )

    sample = evaluate_clip_view_path(
        session.project.clip_for_id(
            "clip-2"
        ),
        3.0,
    )

    assert sample.mode == "interpolate"
    assert sample.camera.yaw_deg == pytest.approx(
        20.0
    )
    assert sample.camera.pitch_deg == pytest.approx(
        5.0
    )
    assert sample.camera.fov_deg == pytest.approx(
        80.0
    )

    assert (
        session.project.clip_for_id(
            "clip-1"
        ).camera_positions
        == []
    )


def test_resolver_prefers_clip_id_over_source_string():
    project = Project(
        clips=[
            Clip(
                id="clip-1",
                source="clip-2",
            ),
            Clip(
                id="clip-2",
                source="video.OSV",
            ),
        ]
    )

    resolved = resolve_project_clip(
        project,
        "clip-2",
    )

    assert resolved.id == "clip-2"
    assert resolved.source == "video.OSV"


def test_resolver_accepts_relative_absolute_alias(
    tmp_path,
    monkeypatch,
):
    media = tmp_path / "sample.OSV"
    media.write_bytes(b"x")

    monkeypatch.chdir(tmp_path)

    project = Project(
        clips=[
            Clip(
                id="clip-1",
                source="sample.OSV",
            )
        ]
    )

    resolved = resolve_project_clip(
        project,
        str(media.resolve()),
    )

    assert resolved.id == "clip-1"


def test_resolver_error_lists_available_clips():
    project = Project(
        clips=[
            Clip(
                id="clip-1",
                source="a.OSV",
            ),
            Clip(
                id="clip-2",
                source="b.OSV",
            ),
        ]
    )

    with pytest.raises(
        ValueError,
        match="clip-1=a.OSV",
    ):
        resolve_project_clip(
            project,
            "missing.OSV",
        )
