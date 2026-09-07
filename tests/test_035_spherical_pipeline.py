from pathlib import Path

import panopilot.project_export as export_module
import panopilot.spherical_stabilization as spherical_module
from panopilot.cli import build_parser


def test_spherical_local_mesh_is_opt_in():
    args = build_parser().parse_args(
        [
            "project-export",
            "project.json",
        ]
    )

    assert args.spherical_local_mesh is False

    args = build_parser().parse_args(
        [
            "project-export",
            "project.json",
            "--spherical-local-mesh",
        ]
    )

    assert args.spherical_local_mesh is True


def test_spherical_analysis_keeps_roll_in_camera_correction():
    source = Path(
        spherical_module.__file__
    ).read_text(
        encoding="utf-8"
    )

    assert (
        "ransac-rigid-translation-plus-roll-scale-discarded"
        in source
    )
    assert (
        "raw_roll_p95_abs_deg_per_frame"
        in source
    )
    assert (
        "rolling_shutter_or_parallax_suspected"
        in source
    )


def test_export_applies_third_visual_channel_as_virtual_camera_roll():
    source = Path(
        export_module.__file__
    ).read_text(
        encoding="utf-8"
    )

    assert (
        "roll_offset_deg"
        in source
    )
    assert (
        "roll_deg=float(roll)"
        in source
    )
    assert (
        "spherical_local_mesh=False"
        in source
    )
    assert (
        "disabled by default to preserve rigid"
        in source
    )
