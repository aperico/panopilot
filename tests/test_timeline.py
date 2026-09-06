import pytest

from panopilot.project import Clip, Project
from panopilot.timeline import (
    build_project_timeline,
    clip_local_to_source_time,
    source_to_clip_local_time,
    timeline_time_to_source,
)


def test_source_clip_local_mapping_is_trim_relative():
    clip = Clip(
        id="clip-1",
        source="a.OSV",
        trim_in_source_time=2.0,
        trim_out_source_time=5.0,
    )
    assert source_to_clip_local_time(clip, 3.25) == pytest.approx(1.25)
    assert clip_local_to_source_time(clip, 1.25) == pytest.approx(3.25)


def test_project_timeline_is_sequential_after_trim():
    project = Project(
        clips=[
            Clip(
                id="clip-1",
                source="a.OSV",
                trim_in_source_time=1.0,
                trim_out_source_time=4.0,
            ),
            Clip(
                id="clip-2",
                source="b.OSV",
                trim_in_source_time=2.0,
                trim_out_source_time=6.0,
            ),
        ]
    )
    spans = build_project_timeline(
        project, {"a.OSV": 10.0, "b.OSV": 10.0}
    )
    assert spans[0].timeline_start == 0.0
    assert spans[0].timeline_end == 3.0
    assert spans[0].source_in == 1.0
    assert spans[0].source_out == 4.0
    assert spans[1].timeline_start == 3.0
    assert spans[1].timeline_end == 7.0
    assert spans[1].source_in == 2.0
    assert spans[1].source_out == 6.0


def test_project_timeline_mapping_uses_clip_instance_span():
    project = Project(
        clips=[
            Clip(
                id="clip-1",
                source="a.OSV",
                trim_in_source_time=1.0,
                trim_out_source_time=4.0,
            ),
            Clip(
                id="clip-2",
                source="b.OSV",
                trim_in_source_time=2.0,
                trim_out_source_time=6.0,
            ),
        ]
    )
    spans = build_project_timeline(
        project, {"a.OSV": 10.0, "b.OSV": 10.0}
    )
    span, source_time = timeline_time_to_source(spans, 4.0)
    assert span.clip_id == "clip-2"
    assert source_time == pytest.approx(3.0)
