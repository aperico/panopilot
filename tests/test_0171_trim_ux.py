import numpy as np

from panopilot.explore import (
    ExploreState,
    ExploreWindow,
    trim_summary_text,
)


def _panorama():
    return np.zeros(
        (180, 360, 3),
        dtype=np.uint8,
    )


def test_trim_summary_is_explicit():
    assert trim_summary_text(
        1.05,
        5.05,
    ) == (
        "ACTIVE CLIP   "
        "IN 00:01.050   "
        "OUT 00:05.050   "
        "DURATION 00:04.000"
    )


def test_camera_exploration_is_not_project_dirty():
    state = ExploreState()

    window = ExploreWindow(
        _panorama(),
        state=state,
        source_time=1.0,
        source_duration=6.0,
        show_hud=False,
    )

    assert window.camera_exploration_changed is True
    assert window.project_dirty is False


def test_legacy_transient_property_is_compatibility_alias():
    state = ExploreState()

    window = ExploreWindow(
        _panorama(),
        state=state,
        source_time=1.0,
        source_duration=6.0,
        show_hud=False,
    )

    assert (
        window.has_uncommitted_changes
        == window.camera_exploration_changed
    )


def test_set_in_feedback_contains_exact_trim_values():
    def callback(**kwargs):
        return {
            "changed": True,
            "label": "Set Clip In",
            "dirty": True,
            "can_undo": True,
            "can_redo": False,
            "trim_in_source_time": 1.05,
            "trim_out_source_time": 5.05,
            "marker_times": [],
            "dormant_marker_times": [],
        }

    window = ExploreWindow(
        _panorama(),
        state=ExploreState(),
        source_time=1.05,
        source_duration=6.016,
        trim_in_callback=callback,
        trim_in_source_time=0.0,
        trim_out_source_time=5.05,
        show_hud=False,
    )

    window.set_trim_in_here()

    assert window.last_edit_message == (
        "Clip In set: 00:01.050 | "
        "Out: 00:05.050 | "
        "Duration: 00:04.000"
    )


def test_set_out_feedback_contains_exact_trim_values():
    def callback(**kwargs):
        return {
            "changed": True,
            "label": "Set Clip Out",
            "dirty": True,
            "can_undo": True,
            "can_redo": False,
            "trim_in_source_time": 1.05,
            "trim_out_source_time": 5.05,
            "marker_times": [],
            "dormant_marker_times": [],
        }

    window = ExploreWindow(
        _panorama(),
        state=ExploreState(),
        source_time=5.05,
        source_duration=6.016,
        trim_out_callback=callback,
        trim_in_source_time=1.05,
        trim_out_source_time=None,
        show_hud=False,
    )

    window.set_trim_out_here()

    assert window.last_edit_message == (
        "Clip Out set: 00:05.050 | "
        "In: 00:01.050 | "
        "Duration: 00:04.000"
    )
