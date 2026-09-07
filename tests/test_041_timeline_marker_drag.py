from pathlib import Path
import panopilot.explore as explore_module

def test_timeline_exposes_camera_position_drag_interaction():
    source=Path(explore_module.__file__).read_text()
    for token in ('_camera_drag_from','_marker_near_x','Drag a red or gray','move_camera_position','move_position_callback'): assert token in source
