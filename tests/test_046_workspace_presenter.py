from panopilot.project import Project
from panopilot.session import ProjectSession
from panopilot.workspace_presenter import build_workspace_view_state


def test_workspace_presenter_builds_compact_view_state():
    session = ProjectSession(Project())
    session.add_clip("a.OSV")
    session.add_clip("b.OSV")
    clip_ids = [clip.id for clip in session.project.clips]

    state = build_workspace_view_state(
        session.project,
        {clip_ids[0]: 6.0, clip_ids[1]: 4.0},
        dirty=True,
    )

    assert len(state.clip_rows) == 2
    assert state.timeline_available is True
    assert state.project_duration == 10.0
    assert state.status == "Modified"
    assert "2 Clips" in state.summary
    assert "Project duration 10.000s" in state.summary


def test_workspace_presenter_marks_duration_unavailable_without_guessing():
    session = ProjectSession(Project())
    session.add_clip("a.OSV")

    state = build_workspace_view_state(session.project, {}, dirty=False)

    assert state.timeline_available is False
    assert state.project_duration is None
    assert "Project duration unavailable" in state.summary
