import numpy as np
from panopilot.explore import ExploreState, ExploreWindow


def test_monotonic_playback_clock_progresses_independent_of_last_camera_position():
    assert ExploreWindow.monotonic_playback_target(4.0, 100.0, now=103.5) == 7.5


def test_playback_seek_beyond_last_diamond_is_not_clamped_to_diamond():
    window = ExploreWindow(
        np.zeros((16, 32, 3), dtype=np.uint8),
        state=ExploreState(),
        source_time=4.0,
        source_duration=12.0,
        marker_times=[1.0, 4.0],
    )
    window.begin_playback_view()
    result = window.seek_for_playback(9.0)
    assert result["source_time"] == 9.0
    assert window.source_time == 9.0
