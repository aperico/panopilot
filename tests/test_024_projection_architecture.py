from pathlib import Path

import panopilot.project_export as export_module
import panopilot.virtual_camera as camera_module


def test_projection_kernel_does_not_allocate_three_channel_ray_tensor():
    source = Path(
        camera_module.__file__
    ).read_text(
        encoding="utf-8"
    )

    class_source = source[
        source.index(
            "class RectilinearProjector"
        ):
    ]

    assert (
        "dtype=np.float32"
        in class_source
    )
    assert (
        "combined ="
        in class_source
    )
    assert (
        "rays = np.empty"
        not in class_source
    )
    assert (
        "source = (\\n            rays"
        not in class_source
    )


def test_export_reports_projection_substages():
    source = Path(
        export_module.__file__
    ).read_text(
        encoding="utf-8"
    )

    assert (
        '"map_generation_worker"'
        in source
    )
    assert (
        '"projection_map_wait"'
        in source
    )
    assert (
        '"panorama_remap"'
        in source
    )
    assert (
        '"float32-analytic-composed-map"'
        in source
    )
