"""
Render a conventional frame using a persisted PanoPilot View Path.

This proves that Camera Positions are active rendering inputs rather than
merely project metadata.
"""
from __future__ import annotations

from pathlib import Path

from .project import load_project
from .reframe import reframe_osv_frame
from .view_path import evaluate_clip_view_path


def render_project_view_at(
    project_path,
    source,
    output,
    *,
    source_time,
    width=None,
    height=None,
    level_horizon=True,
    level_strength=1.0,
    imu_source="highrate",
    imu_offset_ms=0.0,
    panorama_width=1920,
    panorama_height=960,
):
    project_path = Path(project_path)

    if not project_path.is_file():
        raise FileNotFoundError(
            f"Project does not exist: {project_path}"
        )

    project = load_project(project_path)
    clip = project.clip_for_source(
        str(source),
        create=False,
    )

    if clip is None:
        raise ValueError(
            f"Project has no Clip for source {source}"
        )

    sample = evaluate_clip_view_path(
        clip,
        source_time,
    )

    camera = sample.camera

    result = reframe_osv_frame(
        source,
        output,
        source_time=source_time,
        yaw_deg=camera.yaw_deg,
        pitch_deg=camera.pitch_deg,
        fov_deg=camera.fov_deg,
        aspect=project.output_aspect,
        width=width,
        height=height,
        level_horizon=level_horizon,
        level_strength=level_strength,
        imu_source=imu_source,
        imu_offset_ms=imu_offset_ms,
        panorama_width=panorama_width,
        panorama_height=panorama_height,
    )

    result["project"] = str(project_path)
    result["view_path"] = sample.to_dict()
    result["camera_position_count"] = len(
        clip.camera_positions
    )

    return result
