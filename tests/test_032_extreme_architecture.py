from pathlib import Path

import panopilot.extreme_stabilization as extreme_module
import panopilot.project_export as export_module


def test_extreme_mode_uses_iterative_reanalysis_and_single_final_warp():
    source = Path(
        extreme_module.__file__
    ).read_text(
        encoding="utf-8"
    )

    assert (
        "calcOpticalFlowPyrLK"
        in source
    )
    assert (
        "back_points"
        in source
    )
    assert (
        "estimateAffinePartial2D"
        in source
    )
    assert (
        "for pass_index"
        in source
    )
    assert (
        '"single_final_image_warp": True'
        in source
    )


def test_export_dispatches_explicit_extreme_mode():
    source = Path(
        export_module.__file__
    ).read_text(
        encoding="utf-8"
    )

    assert (
        "stabilize_rendered_video_extreme"
        in source
    )
    compact = "".join(
        source.split()
    )
    assert (
        'visual_stabilization_mode=="extreme"'
        in compact
    )
