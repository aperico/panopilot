import numpy as np

from panopilot.explore import (
    ExploreState,
    ExploreWindow,
)


def _panorama():
    return np.zeros(
        (180, 360, 3),
        dtype=np.uint8,
    )


def test_set_camera_autosaves_in_desktop_workflow():
    calls = []

    def commit_callback(**kwargs):
        calls.append("commit")
        return {
            "changed": True,
            "label": "Use this view",
            "created": True,
            "position_number": 1,
            "dirty": True,
            "can_undo": True,
            "can_redo": False,
            "undo_label": "Use this view",
            "redo_label": None,
            "marker_times": [kwargs["source_time"]],
            "dormant_marker_times": [],
        }

    def save_callback():
        calls.append("save")
        return {
            "saved": True,
            "dirty": False,
            "can_undo": True,
            "can_redo": False,
            "undo_label": "Use this view",
            "redo_label": None,
            "marker_times": [2.0],
            "dormant_marker_times": [],
        }

    window = ExploreWindow(
        _panorama(),
        state=ExploreState(
            yaw_deg=72.0,
            pitch_deg=-6.0,
            fov_deg=70.0,
        ),
        source_time=2.0,
        source_duration=6.0,
        commit_callback=commit_callback,
        save_callback=save_callback,
        show_hud=False,
    )

    result = window.use_this_view()

    assert calls == ["commit", "save"]
    assert result["autosaved"] is True
    assert window.project_dirty is False
    assert window.marker_times == [2.0]
    assert window.saved_this_session is True
    assert (
        window.last_edit_message
        == "Camera Position 01 created and saved @ 00:02.000"
    )


def test_set_camera_without_save_callback_still_supports_unit_workflow():
    def commit_callback(**kwargs):
        return {
            "changed": True,
            "label": "Use this view",
            "created": True,
            "position_number": 1,
            "dirty": True,
            "can_undo": True,
            "can_redo": False,
            "undo_label": "Use this view",
            "redo_label": None,
            "marker_times": [kwargs["source_time"]],
            "dormant_marker_times": [],
        }

    window = ExploreWindow(
        _panorama(),
        state=ExploreState(),
        source_time=1.0,
        source_duration=6.0,
        commit_callback=commit_callback,
        show_hud=False,
    )

    result = window.use_this_view()

    assert result["autosaved"] is False
    assert window.project_dirty is True
    assert (
        window.last_edit_message
        == "Camera Position 01 created and set @ 00:01.000"
    )


def test_set_camera_update_is_autosaved():
    def commit_callback(**kwargs):
        return {
            "changed": True,
            "label": "Use this view",
            "created": False,
            "position_number": 1,
            "dirty": True,
            "can_undo": True,
            "can_redo": False,
            "undo_label": "Use this view",
            "redo_label": None,
            "marker_times": [kwargs["source_time"]],
            "dormant_marker_times": [],
        }

    def save_callback():
        return {
            "saved": True,
            "dirty": False,
            "can_undo": True,
            "can_redo": False,
            "undo_label": "Use this view",
            "redo_label": None,
            "marker_times": [3.0],
            "dormant_marker_times": [],
        }

    window = ExploreWindow(
        _panorama(),
        state=ExploreState(),
        source_time=3.0,
        source_duration=6.0,
        commit_callback=commit_callback,
        save_callback=save_callback,
        show_hud=False,
    )

    result = window.use_this_view()

    assert result["autosaved"] is True
    assert (
        window.last_edit_message
        == "Camera Position 01 updated and saved @ 00:03.000"
    )
