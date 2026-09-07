import json

import pytest

from panopilot.project import Project, commit_camera_position, load_project, save_project
from panopilot.session import ProjectSession
from panopilot.view_path import evaluate_clip_view_path


def _commit(project, time, yaw):
    commit_camera_position(
        project,
        "sample.OSV",
        source_time=time,
        yaw_deg=yaw,
        pitch_deg=0.0,
        fov_deg=90.0,
    )


def test_schema_v1_project_migrates_to_v3(tmp_path):
    path = tmp_path / "old.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "output_frame": {"aspect": "16:9"},
                "clips": [
                    {
                        "id": "clip-1",
                        "source": "sample.OSV",
                        "camera_positions": [],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    project = load_project(path)
    assert project.schema_version == 8
    assert project.clips[0].trim_in_source_time == 0.0
    assert project.clips[0].trim_out_source_time is None

    save_project(project, path)
    disk = json.loads(path.read_text(encoding="utf-8"))
    assert disk["schema_version"] == 8
    assert disk["clips"][0]["trim"] == {
        "in_source_time": 0.0,
        "out_source_time": None,
    }
    assert disk["camera_motion"] == {
        "easing": "smooth",
        "strength": 1.0,
    }


def test_trim_change_never_retimes_camera_positions():
    project = Project()
    _commit(project, 1.0, 10.0)
    _commit(project, 3.0, 30.0)
    _commit(project, 5.0, 50.0)
    before = [p.source_time for p in project.clips[0].camera_positions]

    session = ProjectSession(project)
    session.set_clip_trim_in(
        "sample.OSV", source_time=2.0, source_duration=6.0
    )
    session.set_clip_trim_out(
        "sample.OSV", source_time=4.0, source_duration=6.0
    )
    after = [
        p.source_time for p in session.project.clips[0].camera_positions
    ]
    assert after == before


def test_out_of_trim_positions_are_dormant_not_deleted():
    project = Project()
    _commit(project, 1.0, 10.0)
    _commit(project, 3.0, 30.0)
    _commit(project, 5.0, 50.0)
    session = ProjectSession(project)
    session.set_clip_trim_in(
        "sample.OSV", source_time=2.0, source_duration=6.0
    )
    session.set_clip_trim_out(
        "sample.OSV", source_time=4.0, source_duration=6.0
    )
    clip = session.project.clips[0]
    assert [p.source_time for p in clip.active_camera_positions()] == [3.0]
    assert [p.source_time for p in clip.dormant_camera_positions()] == [1.0, 5.0]
    assert len(clip.camera_positions) == 3


def test_single_active_position_holds_across_trim():
    project = Project()
    _commit(project, 1.0, 10.0)
    _commit(project, 3.0, 30.0)
    _commit(project, 5.0, 50.0)
    clip = project.clips[0]
    clip.trim_in_source_time = 2.0
    clip.trim_out_source_time = 4.0

    for time in (2.0, 2.5, 3.5, 4.0):
        sample = evaluate_clip_view_path(clip, time)
        assert sample.mode == "hold-single"
        assert sample.camera.yaw_deg == 30.0


def test_zero_active_positions_use_default_camera():
    project = Project()
    _commit(project, 1.0, 10.0)
    _commit(project, 5.0, 50.0)
    clip = project.clips[0]
    clip.trim_in_source_time = 2.0
    clip.trim_out_source_time = 4.0
    sample = evaluate_clip_view_path(clip, 3.0)
    assert sample.mode == "default"
    assert sample.camera.yaw_deg == 0.0


def test_trim_in_out_are_undoable():
    session = ProjectSession(Project())
    session.set_clip_trim_in(
        "sample.OSV", source_time=1.0, source_duration=6.0
    )
    session.set_clip_trim_out(
        "sample.OSV", source_time=5.0, source_duration=6.0
    )
    clip = session.project.clip_for_source("sample.OSV")
    assert clip.trim_in_source_time == 1.0
    assert clip.trim_out_source_time == 5.0

    session.undo()
    clip = session.project.clip_for_source("sample.OSV")
    assert clip.trim_out_source_time is None

    session.undo()
    assert session.project.clips == []


def test_invalid_trim_is_rejected_without_history_entry():
    session = ProjectSession(Project())
    session.set_clip_trim_out(
        "sample.OSV", source_time=2.0, source_duration=6.0
    )
    before = len(session._undo_stack)
    with pytest.raises(ValueError):
        session.set_clip_trim_in(
            "sample.OSV",
            source_time=2.0,
            source_duration=6.0,
            min_duration_s=0.05,
        )
    assert len(session._undo_stack) == before


def test_delete_last_position_preserves_clip_when_trim_exists():
    project = Project()
    _commit(project, 2.0, 20.0)
    session = ProjectSession(project)
    session.set_clip_trim_in(
        "sample.OSV", source_time=1.0, source_duration=6.0
    )
    session.delete_camera_position(
        "sample.OSV", source_time=2.0, tolerance_s=0.01
    )
    clip = session.project.clip_for_source("sample.OSV")
    assert clip is not None
    assert clip.camera_positions == []
    assert clip.trim_in_source_time == 1.0
