from pathlib import Path

import panopilot.explore as explore_module


def test_camera_position_move_callback_uses_authoritative_source_duration():
    source = Path(explore_module.__file__).read_text()
    assert "source_duration=source_duration," in source
    assert "source_duration=source_duration_value" not in source


def test_timeline_camera_position_drag_routes_through_move_callback():
    source = Path(explore_module.__file__).read_text()
    assert "outer.move_camera_position(original, target)" in source
    assert "widget._seek_to(target)" in source
