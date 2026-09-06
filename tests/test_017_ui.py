import numpy as np

from panopilot.explore import ExploreState, ExploreWindow
from panopilot.virtual_camera import VirtualCamera


def _panorama():
    return np.zeros((180, 360, 3), dtype=np.uint8)


def test_trim_callback_updates_trim_and_dormant_markers():
    def trim_in_callback(**kwargs):
        return {
            "changed": True,
            "label": "Set Clip In",
            "dirty": True,
            "can_undo": True,
            "can_redo": False,
            "trim_in_source_time": 2.0,
            "trim_out_source_time": 5.0,
            "marker_times": [3.0],
            "dormant_marker_times": [1.0],
            "camera": VirtualCamera(30.0, 0.0, 90.0),
        }

    window = ExploreWindow(
        _panorama(),
        state=ExploreState(),
        source_time=2.0,
        source_duration=6.0,
        trim_in_callback=trim_in_callback,
        show_hud=False,
    )
    window.set_trim_in_here()
    assert window.trim_start == 2.0
    assert window.trim_end == 5.0
    assert window.marker_times == [3.0]
    assert window.dormant_marker_times == [1.0]
    assert window.project_dirty is True
