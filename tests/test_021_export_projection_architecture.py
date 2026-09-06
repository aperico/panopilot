from pathlib import Path

import panopilot.project_export as export_module
import panopilot.virtual_camera as camera_module
import panopilot.projection_prefetch as prefetch_module


def _source(module):
    return Path(
        module.__file__
    ).read_text(
        encoding="utf-8"
    )


def test_final_export_uses_reusable_composed_projector():
    source = _source(
        export_module
    )

    prefetch_source = _source(
        prefetch_module
    )

    assert "RectilinearProjector" in source
    assert "projector.map" in prefetch_source
    assert "cv2.remap" in source
    assert "rotate_equirectangular(" not in source
    assert '"post_stitch_resamples_per_frame"' in source
    assert 'render_pipeline == "panorama"' in source


def test_projector_caches_output_coordinate_axes():
    source = _source(
        camera_module
    )

    assert "self._nx" in source
    assert "self._ny" in source
    assert "content_rotation" in source
