from pathlib import Path

import panopilot.virtual_camera as camera_module


def test_final_projector_hot_path_avoids_general_remainder():
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
        "_wrap_equirectangular_x_inplace"
        in class_source
    )
    assert (
        "np.remainder("
        not in class_source
    )
