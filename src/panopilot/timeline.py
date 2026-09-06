"""UI-independent sequential Project Timeline primitives."""
from __future__ import annotations

from dataclasses import dataclass

from .project import Clip, Project, TIME_MATCH_TOLERANCE_S


@dataclass(frozen=True)
class ClipTimelineSpan:
    clip_id: str
    source: str
    timeline_start: float
    timeline_end: float
    source_in: float
    source_out: float

    @property
    def duration(self):
        return self.timeline_end - self.timeline_start

    def to_dict(self):
        return {
            "clip_id": self.clip_id,
            "source": self.source,
            "timeline_start": float(self.timeline_start),
            "timeline_end": float(self.timeline_end),
            "duration": float(self.duration),
            "source_in": float(self.source_in),
            "source_out": float(self.source_out),
        }


def source_to_clip_local_time(clip: Clip, source_time):
    return float(source_time) - float(clip.trim_in_source_time)


def clip_local_to_source_time(clip: Clip, clip_local_time):
    return float(clip.trim_in_source_time) + float(clip_local_time)


def _duration_for_clip(clip, source_durations):
    if clip.id in source_durations:
        return float(source_durations[clip.id])
    if clip.source in source_durations:
        return float(source_durations[clip.source])
    raise KeyError(f"No source duration supplied for Clip {clip.id} ({clip.source})")


def build_project_timeline(project: Project, source_durations):
    cursor = 0.0
    spans = []
    for clip in project.clips:
        source_duration = _duration_for_clip(clip, source_durations)
        source_in, source_out = clip.resolved_trim_bounds(source_duration)
        duration = source_out - source_in
        spans.append(
            ClipTimelineSpan(
                clip_id=clip.id,
                source=clip.source,
                timeline_start=cursor,
                timeline_end=cursor + duration,
                source_in=source_in,
                source_out=source_out,
            )
        )
        cursor += duration
    return spans


def project_duration(project, source_durations):
    spans = build_project_timeline(project, source_durations)
    return spans[-1].timeline_end if spans else 0.0


def timeline_time_to_source(spans, timeline_time):
    spans = list(spans)
    if not spans:
        raise ValueError("Cannot map an empty Project Timeline")
    value = float(timeline_time)
    if value < -TIME_MATCH_TOLERANCE_S:
        raise ValueError("timeline_time must be >= 0")
    final_end = spans[-1].timeline_end
    if value > final_end + TIME_MATCH_TOLERANCE_S:
        raise ValueError("timeline_time exceeds Project duration")

    for span in spans:
        if value < span.timeline_end - TIME_MATCH_TOLERANCE_S:
            local = value - span.timeline_start
            return span, span.source_in + local

    span = spans[-1]
    return span, span.source_out
