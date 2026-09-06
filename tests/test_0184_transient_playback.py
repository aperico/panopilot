import numpy as np

from panopilot.explore import (
    ExploreState,
    ExploreWindow,
)
from panopilot.virtual_camera import (
    VirtualCamera,
)


def _panorama():
    return np.zeros(
        (180, 360, 3),
        dtype=np.uint8,
    )


def test_zero_camera_positions_can_preview_explored_view_without_edit():
    state = ExploreState(
        yaw_deg=0.0,
        pitch_deg=0.0,
        fov_deg=90.0,
        initial_yaw_deg=0.0,
        initial_pitch_deg=0.0,
        initial_fov_deg=90.0,
    )

    window = ExploreWindow(
        _panorama(),
        state=state,
        source_time=1.0,
        source_duration=6.0,
        marker_times=[],
        dormant_marker_times=[],
        show_hud=False,
    )

    state.apply_drag(
        -200,
        0,
        800,
    )

    assert (
        window.exploration_differs_from_initial
        is True
    )
    assert (
        window.can_preview_transient_hold
        is True
    )
    assert (
        window.begin_playback_view()
        == "transient-hold"
    )


def test_transient_hold_survives_playback_seek():
    state = ExploreState(
        yaw_deg=40.0,
        pitch_deg=-5.0,
        fov_deg=70.0,
        initial_yaw_deg=0.0,
        initial_pitch_deg=0.0,
        initial_fov_deg=90.0,
    )

    def seek_callback(source_time):
        return {
            "source_time": source_time,
            "panorama": _panorama(),
            "camera": VirtualCamera(
                yaw_deg=0.0,
                pitch_deg=0.0,
                fov_deg=90.0,
            ),
            "aspect": "16:9",
            "marker_times": [],
            "dormant_marker_times": [],
        }

    window = ExploreWindow(
        _panorama(),
        state=state,
        source_time=1.0,
        source_duration=6.0,
        seek_callback=seek_callback,
        marker_times=[],
        dormant_marker_times=[],
        show_hud=False,
    )

    window.begin_playback_view()
    window.seek_for_playback(
        2.0
    )

    assert state.yaw_deg == 40.0
    assert state.pitch_deg == -5.0
    assert state.fov_deg == 70.0


def test_existing_view_path_disables_transient_hold_preview():
    state = ExploreState(
        yaw_deg=40.0,
        pitch_deg=0.0,
        fov_deg=80.0,
        initial_yaw_deg=20.0,
        initial_pitch_deg=0.0,
        initial_fov_deg=90.0,
    )

    window = ExploreWindow(
        _panorama(),
        state=state,
        source_time=1.0,
        source_duration=6.0,
        marker_times=[1.0],
        dormant_marker_times=[],
        show_hud=False,
    )

    assert window.camera_position_count == 1
    assert window.can_preview_transient_hold is False
    assert (
        window.begin_playback_view()
        == "persisted-path"
    )


def test_unchanged_default_view_does_not_enter_transient_hold():
    state = ExploreState(
        yaw_deg=0.0,
        pitch_deg=0.0,
        fov_deg=90.0,
        initial_yaw_deg=0.0,
        initial_pitch_deg=0.0,
        initial_fov_deg=90.0,
    )

    window = ExploreWindow(
        _panorama(),
        state=state,
        source_time=1.0,
        source_duration=6.0,
        marker_times=[],
        dormant_marker_times=[],
        show_hud=False,
    )

    assert (
        window.exploration_differs_from_initial
        is False
    )
    assert (
        window.can_preview_transient_hold
        is False
    )
