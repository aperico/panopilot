from pathlib import Path

import panopilot.factory as factory_module
import panopilot.project_export as export_module


def test_factory_stitch_uses_native_spatial_blend():
    source = Path(
        factory_module.__file__
    ).read_text(
        encoding="utf-8"
    )

    assert "cv2.blendLinear" in source
    assert "p0.astype(np.float32)" not in source


def test_project_export_passes_existing_probe_to_pts_resolver():
    source = Path(
        export_module.__file__
    ).read_text(
        encoding="utf-8"
    )

    assert "probe=probe" in source
    assert "return_diagnostics=True" in source
