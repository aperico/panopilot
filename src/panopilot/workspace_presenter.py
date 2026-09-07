"""GUI-independent presentation logic for the Project workspace.

This is the first MVP-style boundary in the desktop shell: domain/application
objects remain authoritative, while Qt views consume a compact immutable view
state.  Mutation still goes through ``ProjectSession``; rendering stays outside
this module entirely.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .output_profile import output_fps_label
from .project import project_source_statuses
from .timeline import build_project_timeline


@dataclass(frozen=True)
class WorkspaceViewState:
    clip_rows: tuple[dict, ...]
    project_duration: float | None
    timeline_available: bool
    stabilization_percent: int
    fps_summary: str
    status: str
    summary: str


def clip_list_rows(project, durations=None):
    durations = durations or {}
    rows = []
    status_by_clip = {
        item["clip_id"]: item
        for item in project_source_statuses(project)
    }

    for index, clip in enumerate(project.clips):
        duration = durations.get(clip.id)
        if duration is None:
            resolved_out = clip.trim_out_source_time
            clip_duration = None
        else:
            resolved_out = clip.resolved_trim_out(duration)
            clip_duration = resolved_out - clip.trim_in_source_time

        rows.append({
            "index": index,
            "number": index + 1,
            "clip_id": clip.id,
            "source": clip.source,
            "source_name": Path(clip.source).name,
            "trim_in": float(clip.trim_in_source_time),
            "trim_out": float(resolved_out) if resolved_out is not None else None,
            "source_duration": float(duration) if duration is not None else None,
            "duration": float(clip_duration) if clip_duration is not None else None,
            "camera_position_count": len(clip.camera_positions),
            "source_status": status_by_clip.get(
                clip.id,
                {"status": "unknown", "message": "Source status unavailable"},
            ),
        })

    return rows


def build_workspace_view_state(project, durations=None, *, dirty=False):
    durations = durations or {}
    rows = clip_list_rows(project, durations)
    timeline_available = len(durations) == len(project.clips)

    project_duration = None
    if timeline_available:
        if project.clips:
            spans = build_project_timeline(project, durations)
            project_duration = spans[-1].timeline_end if spans else 0.0
        else:
            project_duration = 0.0

    status = "Modified" if dirty else "Saved"
    stabilization_percent = int(round(project.stabilization_amount * 100.0))
    fps_summary = output_fps_label(project.output_fps)
    duration_summary = (
        f"Project duration {project_duration:.3f}s"
        if project_duration is not None
        else "Project duration unavailable"
    )
    summary = (
        f"{project.name}  ·  {len(project.clips)} Clips  ·  {duration_summary}  ·  "
        f"{project.output_resolution} / {fps_summary}  ·  "
        f"Stabilization {stabilization_percent}%  ·  {status}"
    )

    return WorkspaceViewState(
        clip_rows=tuple(rows),
        project_duration=project_duration,
        timeline_available=timeline_available,
        stabilization_percent=stabilization_percent,
        fps_summary=fps_summary,
        status=status,
        summary=summary,
    )
