import pytest

from panopilot.project import (
    Clip,
    Project,
)
from panopilot.project_export import (
    build_export_frame_groups,
)
from panopilot.timeline import (
    build_project_timeline,
)


def test_frame_groups_use_one_global_cfr_timeline():
    project = Project(
        clips=[
            Clip(
                id="clip-1",
                source="a.OSV",
                trim_in_source_time=1.0,
                trim_out_source_time=2.03,
            ),
            Clip(
                id="clip-2",
                source="b.OSV",
                trim_in_source_time=3.0,
                trim_out_source_time=4.02,
            ),
        ]
    )
    spans = build_project_timeline(
        project,
        {
            "clip-1": 10.0,
            "clip-2": 10.0,
        },
    )

    groups, total = build_export_frame_groups(
        project,
        spans,
        fps=30.0,
    )

    assert total == round(
        spans[-1].timeline_end
        * 30.0
    )
    assert sum(
        group.frame_count
        for group in groups
    ) == total
    assert [
        group.clip_id
        for group in groups
    ] == [
        "clip-1",
        "clip-2",
    ]
    assert groups[1].first_frame_index == (
        groups[0].frame_count
    )


def test_frame_group_source_start_respects_trim_and_boundary_mapping():
    project = Project(
        clips=[
            Clip(
                id="clip-1",
                source="a.OSV",
                trim_in_source_time=1.25,
                trim_out_source_time=2.25,
            ),
            Clip(
                id="clip-2",
                source="b.OSV",
                trim_in_source_time=5.0,
                trim_out_source_time=6.0,
            ),
        ]
    )
    spans = build_project_timeline(
        project,
        {
            "clip-1": 10.0,
            "clip-2": 10.0,
        },
    )

    groups, total = build_export_frame_groups(
        project,
        spans,
        fps=30.0,
    )

    assert total == 60
    assert groups[0].source_time_start == pytest.approx(
        1.25
    )
    assert groups[1].source_time_start == pytest.approx(
        5.0
    )
    assert groups[0].frame_count == 30
    assert groups[1].frame_count == 30
