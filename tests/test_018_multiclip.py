import copy

from panopilot.project import (
    CameraPosition,
    Clip,
    Project,
)
from panopilot.session import ProjectSession
from panopilot.timeline import (
    build_project_timeline,
)


def _project():
    return Project(
        clips=[
            Clip(
                id="clip-1",
                source="a.OSV",
                trim_in_source_time=1.0,
                trim_out_source_time=4.0,
                camera_positions=[
                    CameraPosition(
                        2.0,
                        10.0,
                        0.0,
                        90.0,
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
                        3.0,
                        20.0,
                        0.0,
                        80.0,
                    )
                ],
            ),
        ]
    )


def test_add_clip_uses_non_colliding_id_after_remove():
    project = Project(
        clips=[
            Clip(
                id="clip-1",
                source="a.OSV",
            ),
            Clip(
                id="clip-3",
                source="c.OSV",
            ),
        ]
    )

    clip = project.add_clip(
        "d.OSV"
    )

    assert clip.id == "clip-4"


def test_duplicate_source_is_rejected():
    project = Project()
    project.add_clip("a.OSV")

    try:
        project.add_clip("a.OSV")
    except ValueError as exc:
        assert "already present" in str(exc)
    else:
        raise AssertionError(
            "duplicate source should be rejected"
        )


def test_reorder_changes_timeline_not_camera_source_times():
    project = _project()

    before = {
        clip.id: [
            p.source_time
            for p in clip.camera_positions
        ]
        for clip in project.clips
    }

    project.move_clip(
        "clip-2",
        0,
    )

    after = {
        clip.id: [
            p.source_time
            for p in clip.camera_positions
        ]
        for clip in project.clips
    }

    assert [
        clip.id
        for clip in project.clips
    ] == [
        "clip-2",
        "clip-1",
    ]
    assert after == before

    spans = build_project_timeline(
        project,
        {
            "a.OSV": 10.0,
            "b.OSV": 10.0,
        },
    )

    assert spans[0].clip_id == "clip-2"
    assert spans[0].timeline_start == 0.0
    assert spans[0].timeline_end == 4.0
    assert spans[1].clip_id == "clip-1"
    assert spans[1].timeline_start == 4.0
    assert spans[1].timeline_end == 7.0


def test_remove_clip_is_undoable_with_full_clip_state():
    session = ProjectSession(
        _project()
    )

    original = copy.deepcopy(
        session.project.clip_for_id(
            "clip-1"
        ).to_dict()
    )

    result = session.remove_clip(
        "clip-1"
    )

    assert result["changed"] is True
    assert (
        session.project.clip_for_id(
            "clip-1"
        )
        is None
    )

    session.undo()

    restored = session.project.clip_for_id(
        "clip-1"
    )

    assert restored is not None
    assert restored.to_dict() == original


def test_reorder_is_undo_redo_transaction():
    session = ProjectSession(
        _project()
    )

    session.move_clip_by(
        "clip-2",
        -1,
    )

    assert [
        clip.id
        for clip in session.project.clips
    ] == [
        "clip-2",
        "clip-1",
    ]

    session.undo()

    assert [
        clip.id
        for clip in session.project.clips
    ] == [
        "clip-1",
        "clip-2",
    ]

    session.redo()

    assert [
        clip.id
        for clip in session.project.clips
    ] == [
        "clip-2",
        "clip-1",
    ]


def test_add_remove_reorder_new_edit_clears_redo():
    session = ProjectSession(
        _project()
    )

    session.move_clip_by(
        "clip-2",
        -1,
    )
    session.undo()

    assert session.can_redo is True

    session.add_clip(
        "c.OSV"
    )

    assert session.can_redo is False
