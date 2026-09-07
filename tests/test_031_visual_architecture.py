from pathlib import Path
import panopilot.project_export as export_module
import panopilot.visual_stabilization as visual_module

def test_visual_stage_is_post_render_pre_mux():
    source=Path(export_module.__file__).read_text(encoding="utf-8")
    assert "stabilize_rendered_video" in source
    assert '"visual_residual_stabilization"' in source
    assert "video_rendered" in source

def test_visual_algorithm_uses_klt_ransac_and_crop():
    source=Path(visual_module.__file__).read_text(encoding="utf-8")
    assert "calcOpticalFlowPyrLK" in source
    assert "estimateAffinePartial2D" in source
    assert "cv2.RANSAC" in source
    assert "_max_feasible_alpha" in source
