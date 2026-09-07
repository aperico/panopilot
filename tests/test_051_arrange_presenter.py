from panopilot.arrange_presenter import build_arrange_view_state
from panopilot.project import Project


def test_arrange_rows_are_sequential_and_duration_based():
    project = Project()
    a = project.add_clip("a.osv", source_identity_value={})
    b = project.add_clip("b.osv", source_identity_value={})
    a.trim_in_source_time = 1.0
    a.trim_out_source_time = 5.0
    b.trim_out_source_time = 8.0
    state = build_arrange_view_state(project, {a.id: 10.0, b.id: 10.0})
    assert [row.clip_id for row in state.rows] == [a.id, b.id]
    assert [row.duration for row in state.rows] == [4.0, 8.0]
    assert state.rows[1].timeline_start == 4.0
    assert state.total_duration == 12.0
