"""GUI-independent Project Arrange presentation state."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .timeline import build_project_timeline


@dataclass(frozen=True)
class ArrangeClipRow:
    clip_id: str
    source: str
    source_name: str
    order: int
    duration: float
    timeline_start: float
    timeline_end: float


@dataclass(frozen=True)
class ArrangeViewState:
    rows: tuple[ArrangeClipRow, ...]
    total_duration: float


def build_arrange_view_state(project, source_durations):
    if not project.clips:
        return ArrangeViewState(rows=(), total_duration=0.0)
    spans = build_project_timeline(project, source_durations)
    rows = []
    for index, span in enumerate(spans):
        rows.append(
            ArrangeClipRow(
                clip_id=span.clip_id,
                source=span.source,
                source_name=Path(span.source).name,
                order=index + 1,
                duration=float(span.duration),
                timeline_start=float(span.timeline_start),
                timeline_end=float(span.timeline_end),
            )
        )
    return ArrangeViewState(
        rows=tuple(rows),
        total_duration=float(spans[-1].timeline_end if spans else 0.0),
    )
