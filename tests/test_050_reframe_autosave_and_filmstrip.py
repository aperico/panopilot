import numpy as np

from panopilot.explore import ExploreState, ExploreWindow
from panopilot.thumbnails import filmstrip_tile_geometry


def _panorama():
    return np.zeros((32, 64, 3), dtype=np.uint8)


def test_reframe_updates_closest_camera_position_to_left_and_keeps_playhead():
    commits = []
    saves = []

    def commit_callback(**kwargs):
        commits.append(dict(kwargs))
        return {
            "changed": True,
            "created": False,
            "position_number": 2,
            "marker_times": [1.0, 4.0, 8.0],
            "dormant_marker_times": [],
            "dirty": True,
            "can_undo": True,
            "can_redo": False,
        }

    def save_callback():
        saves.append(True)
        return {
            "saved": True,
            "dirty": False,
            "can_undo": True,
            "can_redo": False,
        }

    window = ExploreWindow(
        _panorama(),
        state=ExploreState(yaw_deg=27.0, pitch_deg=3.0, fov_deg=72.0),
        source_time=6.0,
        source_duration=10.0,
        marker_times=[1.0, 4.0, 8.0],
        commit_callback=commit_callback,
        save_callback=save_callback,
    )

    result = window.update_left_camera_position()

    assert result["anchor_time"] == 4.0
    assert commits[0]["source_time"] == 4.0
    assert commits[0]["yaw_deg"] == 27.0
    assert window.source_time == 6.0
    assert saves == [True]
    assert "Camera Position 02" in window.last_edit_message
    assert "automatically" in window.last_edit_message


def test_reframe_before_first_camera_position_does_not_create_implicit_marker():
    calls = []
    window = ExploreWindow(
        _panorama(),
        state=ExploreState(),
        source_time=0.5,
        source_duration=10.0,
        marker_times=[1.0, 4.0],
        commit_callback=lambda **kwargs: calls.append(kwargs),
    )

    result = window.update_left_camera_position()

    assert result["changed"] is False
    assert result["reason"] == "no-camera-position-to-left"
    assert calls == []


def test_camera_position_anchor_includes_dormant_diamonds():
    window = ExploreWindow(
        _panorama(),
        state=ExploreState(),
        source_time=7.0,
        source_duration=10.0,
        marker_times=[2.0],
        dormant_marker_times=[5.0, 9.0],
    )
    assert window.camera_position_anchor_time() == 5.0


def test_filmstrip_tile_geometry_fills_width_without_single_stretched_image():
    geometry = filmstrip_tile_geometry(1920, height=46, max_tiles=24)
    assert geometry["count"] == 24
    assert geometry["width"] >= 80
    assert geometry["width"] * geometry["count"] >= 1920
