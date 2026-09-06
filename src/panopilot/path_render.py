"""
Render a conventional frame using a persisted PanoPilot View Path.

This proves that Camera Positions are active rendering inputs rather than
merely project metadata.
"""
from __future__ import annotations

from pathlib import Path

from .project import load_project, resolve_project_clip
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
    clip = resolve_project_clip(
        project,
        source,
    )

    # The selected Clip owns the authoritative source reference.
    source = clip.source

    sample = evaluate_clip_view_path(
        clip,
        source_time,
        interpolation=project.camera_motion_easing,
        strength=project.camera_motion_strength,
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
    result["clip_id"] = clip.id
    result["source"] = clip.source
    result["view_path"] = sample.to_dict()
    result["camera_position_count"] = len(
        clip.camera_positions
    )
    result["camera_motion"] = {
        "easing": project.camera_motion_easing,
        "strength": float(
            project.camera_motion_strength
        ),
    }

    return result
