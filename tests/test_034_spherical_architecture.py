from pathlib import Path

import panopilot.project_export as export_module
import panopilot.spherical_stabilization as spherical_module


def test_spherical_mode_uses_visual_motion_to_rerender_from_360_source():
    export_source = Path(
        export_module.__file__
    ).read_text(
        encoding="utf-8"
    )
    spherical_source = Path(
        spherical_module.__file__
    ).read_text(
        encoding="utf-8"
    )

    assert (
        "analyze_spherical_camera_stabilization"
        in export_source
    )
    assert (
        "visual_camera_offsets"
        in export_source
    )
    assert (
        "spherical_visual_rerender"
        in export_source
    )
    assert (
        "crop_required_for_global_correction"
        in spherical_source
    )
    assert (
        "lowpass-pairwise-velocity-then-integrate-rejected-band"
        in spherical_source
    )


def test_spherical_mode_limits_local_mesh_to_residual_only():
    source = Path(
        export_module.__file__
    ).read_text(
        encoding="utf-8"
    )

    assert (
        "global_authority=0.0"
        in source
    )
    assert (
        "local_budget = min"
        in source
    )
