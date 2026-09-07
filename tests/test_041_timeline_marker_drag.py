from pathlib import Path
import panopilot.explore as explore_module


def test_timeline_exposes_camera_position_click_and_drag_interaction():
    source = Path(explore_module.__file__).read_text()
    for token in (
        "_camera_drag_from",
        "_marker_near_x",
        "Click a Camera Position diamond",
        "move_camera_position",
        "move_position_callback",
        "widget._seek_to(original)",
    ):
        assert token in source
