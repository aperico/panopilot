from pathlib import Path

import panopilot.locked_stabilization as locked_module
import panopilot.project_export as export_module


def test_locked_mode_forbids_visual_rotation_and_scale():
    source = Path(locked_module.__file__).read_text(encoding="utf-8")

    assert '"visual_rotation_correction": False' in source
    assert '"visual_scale_correction": False' in source
    assert '"per_frame_crop_clipping": False' in source
    assert '"crop_policy": "one-global-gain-per-clip-pass"' in source


def test_export_dispatches_locked_mode():
    compact = "".join(
        Path(export_module.__file__).read_text(encoding="utf-8").split()
    )
    assert 'visual_stabilization_mode=="locked"' in compact
    assert "stabilize_rendered_video_locked" in compact
