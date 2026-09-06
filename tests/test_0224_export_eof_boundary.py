import pytest

from panopilot.project import (
    Clip,
    Project,
)
from panopilot.project_export import (
    _lens_decoder_command,
    build_export_frame_groups,
)
from panopilot.timeline import (
    build_project_timeline,
)


def test_6016ms_clip_at_30fps_gets_nearest_180_frame_boundary():
    project = Project(
        clips=[
            Clip(
                id="clip-1",
                source="a.OSV",
                trim_in_source_time=0.0,
                trim_out_source_time=6.016,
            ),
            Clip(
                id="clip-2",
                source="b.OSV",
                trim_in_source_time=0.0,
                trim_out_source_time=1.0,
            ),
        ]
    )
    spans = build_project_timeline(
        project,
        {
            "clip-1": 6.016,
            "clip-2": 1.0,
        },
    )

    groups, total = build_export_frame_groups(
        project,
        spans,
        fps=30.0,
    )

    assert groups[0].frame_count == 180
    assert groups[1].first_frame_index == 180
    assert sum(
        group.frame_count
        for group in groups
    ) == total


def test_cumulative_boundary_rounding_limits_boundary_error_to_half_frame():
    project = Project(
        clips=[
            Clip(
                id="clip-1",
                source="a.OSV",
                trim_in_source_time=0.0,
                trim_out_source_time=6.016,
            ),
            Clip(
                id="clip-2",
                source="b.OSV",
                trim_in_source_time=2.0,
                trim_out_source_time=4.0,
            ),
        ]
    )
    spans = build_project_timeline(
        project,
        {
            "clip-1": 6.016,
            "clip-2": 10.0,
        },
    )

    groups, _total = build_export_frame_groups(
        project,
        spans,
        fps=30.0,
    )

    quantized_boundary = (
        groups[1].first_frame_index
        / 30.0
    )
    exact_boundary = (
        spans[0].timeline_end
    )

    assert abs(
        quantized_boundary
        - exact_boundary
    ) <= (
        0.5 / 30.0
        + 1e-12
    )
    assert groups[1].source_time_start == pytest.approx(
        2.0
    )


def test_lens_decoder_has_bounded_eof_clone_padding():
    command = _lens_decoder_command(
        "source.OSV",
        0,
        1,
        1920,
        1920,
        fps=30.0,
        start=0.0,
        frame_count=180,
    )

    graph = command[
        command.index(
            "-filter_complex"
        )
        + 1
    ]

    assert "tpad=stop_mode=clone" in graph
    assert "stop_duration=0.066666667" in graph
