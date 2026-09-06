import json

from panopilot.project import Project
from panopilot.session import ProjectSession


def _commit(session, time=1.0, yaw=10.0):
    return session.commit_camera_position(
        "sample.OSV",
        source_time=time,
        yaw_deg=yaw,
        pitch_deg=0.0,
        fov_deg=90.0,
        output_aspect="16:9",
    )


def test_session_starts_clean():
    session = ProjectSession(Project())
    assert session.dirty is False
    assert session.can_undo is False
    assert session.can_redo is False


def test_camera_position_edit_is_dirty_and_undoable():
    session = ProjectSession(Project())

    result = _commit(session)

    assert result["changed"] is True
    assert session.dirty is True
    assert session.can_undo is True

    session.undo()

    assert session.dirty is False
    assert session.project.clips == []
    assert session.can_redo is True


def test_redo_restores_edit():
    session = ProjectSession(Project())

    _commit(session)
    session.undo()
    session.redo()

    assert session.dirty is True
    assert len(session.project.clips) == 1
    assert len(
        session.project.clips[0].camera_positions
    ) == 1


def test_new_edit_after_undo_clears_redo():
    session = ProjectSession(Project())

    _commit(session, time=1.0, yaw=10.0)
    _commit(session, time=2.0, yaw=20.0)

    session.undo()
    assert session.can_redo is True

    _commit(session, time=3.0, yaw=30.0)

    assert session.can_redo is False


def test_update_same_position_undo_restores_previous_values():
    session = ProjectSession(Project())

    _commit(session, time=1.0, yaw=10.0)
    _commit(session, time=1.0, yaw=50.0)

    position = (
        session.project.clips[0]
        .camera_positions[0]
    )
    assert position.yaw_deg == 50.0

    session.undo()

    position = (
        session.project.clips[0]
        .camera_positions[0]
    )
    assert position.yaw_deg == 10.0


def test_delete_camera_position_is_undoable():
    session = ProjectSession(Project())

    _commit(session, time=1.0, yaw=10.0)

    result = session.delete_camera_position(
        "sample.OSV",
        source_time=1.01,
        tolerance_s=0.02,
    )

    assert result["changed"] is True
    assert session.project.clips == []

    session.undo()

    assert len(session.project.clips) == 1
    assert len(
        session.project.clips[0].camera_positions
    ) == 1


def test_delete_away_from_marker_does_not_create_history():
    session = ProjectSession(Project())

    _commit(session, time=1.0, yaw=10.0)
    before_undo_count = len(session._undo_stack)

    result = session.delete_camera_position(
        "sample.OSV",
        source_time=2.0,
        tolerance_s=0.02,
    )

    assert result["changed"] is False
    assert len(session._undo_stack) == before_undo_count


def test_output_aspect_is_undoable():
    session = ProjectSession(Project())

    result = session.set_output_aspect("9:16")

    assert result["changed"] is True
    assert session.project.output_aspect == "9:16"

    session.undo()

    assert session.project.output_aspect == "16:9"


def test_save_establishes_clean_baseline_without_clearing_history(tmp_path):
    path = tmp_path / "project.json"
    session = ProjectSession(
        Project(),
        path=path,
    )

    _commit(session)
    assert session.dirty is True

    session.save()

    assert session.dirty is False
    assert session.can_undo is True
    assert path.is_file()

    disk = json.loads(
        path.read_text(encoding="utf-8")
    )
    assert len(disk["clips"]) == 1

    session.undo()

    assert session.dirty is True


def test_redo_back_to_saved_state_becomes_clean(tmp_path):
    path = tmp_path / "project.json"
    session = ProjectSession(
        Project(),
        path=path,
    )

    _commit(session)
    session.save()

    session.undo()
    assert session.dirty is True

    session.redo()
    assert session.dirty is False


def test_discard_restores_last_saved_snapshot(tmp_path):
    path = tmp_path / "project.json"
    session = ProjectSession(
        Project(),
        path=path,
    )

    _commit(session, time=1.0, yaw=10.0)
    session.save()

    _commit(session, time=2.0, yaw=20.0)
    assert session.dirty is True

    session.discard_to_saved()

    assert session.dirty is False
    assert session.can_undo is False
    assert session.can_redo is False
    assert len(
        session.project.clips[0]
        .camera_positions
    ) == 1
