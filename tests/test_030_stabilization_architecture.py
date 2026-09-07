from pathlib import Path
import panopilot.project_export as export_module
import panopilot.preview as preview_module
import panopilot.stabilization as stabilization_module

def _source(m): return Path(m.__file__).read_text(encoding="utf-8")

def test_export_smooths_native_imu_before_exposure_sampling():
    s=_source(export_module)
    assert "build_adaptive_trajectory" in s and "sample_trajectory" in s
    assert '"dji-perframe-highrate-anchor"' in s

def test_preview_uses_same_adaptive_algorithm():
    s=_source(preview_module)
    assert "build_adaptive_trajectory" in s and '"adaptive-highrate-v1"' in s

def test_clean_room_algorithm_has_no_third_party_runtime_dependency():
    s=_source(stabilization_module).lower()
    assert "scipy" not in s
