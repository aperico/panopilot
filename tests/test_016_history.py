import numpy as np

from panopilot.explore import (
    ExploreState,
    ExploreWindow,
)
from panopilot.virtual_camera import VirtualCamera


def _panorama():
    return np.zeros(
        (180, 360, 3),
        dtype=np.uint8,
    )


def test_commit_updates_dirty_history_state():
    def commit_callback(**kwargs):
        return {
            "created": True,
            "position_number": 1,
            "changed": True,
            "dirty": True,
            "can_undo": True,
            "can_redo": False,
            "undo_label": "Use this view",
            "redo_label": None,
            "marker_times": [kwargs["source_time"]],
        }

    window = ExploreWindow(
        _panorama(),
        state=ExploreState(),
        source_time=1.0,
        commit_callback=commit_callback,
        show_hud=False,
    )

    window.use_this_view()

    assert window.project_dirty is True
    assert window.can_undo is True
    assert window.marker_times == [1.0]


def test_undo_restores_persisted_camera_and_history_state():
    def undo_callback(**kwargs):
        return {
            "changed": True,
            "label": "Use this view",
            "dirty": False,
            "can_undo": False,
            "can_redo": True,
            "undo_label": None,
            "redo_label": "Use this view",
            "camera": VirtualCamera(
                30.0,
                -4.0,
                75.0,
            ),
            "aspect": "16:9",
            "marker_times": [],
        }

    state = ExploreState(
        yaw_deg=80.0,
        pitch_deg=10.0,
        fov_deg=60.0,
    )

    window = ExploreWindow(
        _panorama(),
        state=state,
        source_time=1.0,
        undo_callback=undo_callback,
        show_hud=False,
    )

    window.undo_edit()

    assert window.project_dirty is False
    assert window.can_redo is True
    assert state.yaw_deg == 30.0
    assert state.pitch_deg == -4.0
    assert state.fov_deg == 75.0


def test_output_aspect_callback_marks_project_dirty():
    def aspect_callback(**kwargs):
        return {
            "changed": True,
            "label": "Output frame",
            "dirty": True,
            "can_undo": True,
            "can_redo": False,
            "undo_label": "Output frame",
            "redo_label": None,
            "aspect": kwargs["aspect"],
        }

    state = ExploreState()
    window = ExploreWindow(
        _panorama(),
        state=state,
        source_time=1.0,
        aspect_callback=aspect_callback,
        show_hud=False,
    )

    window.set_output_aspect("9:16")

    assert state.aspect == "9:16"
    assert window.project_dirty is True
    assert window.can_undo is True


def test_save_clears_dirty_state():
    def save_callback():
        return {
            "saved": True,
            "dirty": False,
            "can_undo": True,
            "can_redo": False,
            "undo_label": "Use this view",
            "redo_label": None,
        }

    window = ExploreWindow(
        _panorama(),
        state=ExploreState(),
        source_time=1.0,
        save_callback=save_callback,
        show_hud=False,
    )
    window.project_dirty = True

    window.save_project()

    assert window.project_dirty is False
    assert window.saved_this_session is True
