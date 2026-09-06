\
from pathlib import Path
import panopilot.project_export as export_module
import panopilot.direct_render as direct_module

def test_export_has_separate_direct_branch():
    s=Path(export_module.__file__).read_text(encoding='utf-8')
    assert 'render_pipeline == "panorama"' in s
    assert '"direct_lens_render"' in s
    assert '"direct_map_wait"' in s
    assert '"full_panorama_constructed_per_frame"' in s

def test_direct_renderer_uses_delivery_lens_remaps_and_blend():
    s=Path(direct_module.__file__).read_text(encoding='utf-8')
    assert 'cv2.remap(' in s
    assert 'cv2.blendLinear(' in s
    assert 'factory_mapper.map0_x' in s
