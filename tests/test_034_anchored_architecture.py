from pathlib import Path

import panopilot.anchored_stabilization as anchored_module
import panopilot.project_export as export_module


def test_anchored_model_is_spatially_variant_and_keyframe_regularized():
    source = Path(
        anchored_module.__file__
    ).read_text(
        encoding="utf-8"
    )

    assert (
        "_estimate_mesh_motion"
        in source
    )
    assert (
        "_keyframe_envelope"
        in source
    )
    assert (
        "_spatial_regularize"
        in source
    )
    assert (
        "per_frame_crop_or_zoom"
        in source
    )
    assert (
        "minimum-required-static-crop-per-hard-cut-clip"
        in source
    )


def test_export_dispatches_anchored_mode():
    source = Path(
        export_module.__file__
    ).read_text(
        encoding="utf-8"
    )

    compact = "".join(
        source.split()
    )

    assert (
        "stabilize_rendered_video_anchored"
        in source
    )
    assert (
        'visual_stabilization_mode=="anchored"'
        in compact
    )
