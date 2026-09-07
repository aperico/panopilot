from pathlib import Path
import panopilot.project_editor as editor
import panopilot.project_export as exp

def test_organizer_has_slider():
    s=Path(editor.__file__).read_text()
    assert 'self.stabilization_slider' in s and 'set_stabilization_amount' in s

def test_export_uses_stabilized_rotation():
    s=Path(exp.__file__).read_text()
    assert 'stabilized_horizon_rotation' in s
    assert '"stabilization_rotation_math"' in s
    assert 'native-imu-adaptive-3axis-plus-horizon' in s
