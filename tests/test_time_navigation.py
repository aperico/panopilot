import numpy as np
import pytest

from panopilot.explore import ExploreState, ExploreWindow, format_time
from panopilot.virtual_camera import VirtualCamera


def _panorama():
    return np.zeros((180, 360, 3), dtype=np.uint8)


def test_format_time():
    assert format_time(0.0) == "00:00.000"
    assert format_time(1.234) == "00:01.234"
    assert format_time(61.007) == "01:01.007"


def test_seek_clamps_and_restores_path_camera():
    calls = []

    def seek_callback(source_time):
        calls.append(source_time)
        return {
            "source_time": source_time,
            "panorama": _panorama(),
            "camera": VirtualCamera(40.0, -5.0, 70.0),
            "aspect": "16:9",
            "marker_times": [0.8, 2.6],
        }

    state = ExploreState()

    window = ExploreWindow(
        _panorama(),
        state=state,
        source_time=1.0,
        source_duration=3.0,
        seek_callback=seek_callback,
        show_hud=False,
    )

    window.seek(10.0)

    assert calls == [3.0]
    assert window.source_time == 3.0
    assert state.yaw_deg == 40.0
    assert state.pitch_deg == -5.0
    assert state.fov_deg == 70.0
    assert window.marker_times == [0.8, 2.6]


def test_seek_discards_uncommitted_exploration():
    def seek_callback(source_time):
        return {
            "source_time": source_time,
            "panorama": _panorama(),
            "camera": VirtualCamera(25.0, 0.0, 90.0),
        }

    state = ExploreState()
    window = ExploreWindow(
        _panorama(),
        state=state,
        source_time=1.0,
        source_duration=3.0,
        seek_callback=seek_callback,
        show_hud=False,
    )

    state.apply_drag(-100, 0, 800)
    assert state.yaw_deg != 0.0

    window.seek(2.0)

    assert state.yaw_deg == 25.0
    assert window.last_commit is None


def test_arrow_step_is_deterministic():
    calls = []

    def seek_callback(source_time):
        calls.append(source_time)
        return {
            "source_time": source_time,
            "panorama": _panorama(),
            "camera": VirtualCamera(),
        }

    window = ExploreWindow(
        _panorama(),
        state=ExploreState(),
        source_time=1.0,
        source_duration=3.0,
        seek_callback=seek_callback,
        seek_step_seconds=0.1,
        show_hud=False,
    )

    window.step_time(+1)
    window.step_time(-1)

    assert calls[0] == pytest.approx(1.1)
    assert calls[1] == pytest.approx(1.0)


def test_commit_refreshes_markers():
    def commit_callback(**kwargs):
        return {
            "created": True,
            "position_number": 2,
            "marker_times": [0.8, 2.6],
        }

    window = ExploreWindow(
        _panorama(),
        state=ExploreState(),
        source_time=2.6,
        source_duration=3.0,
        commit_callback=commit_callback,
        marker_times=[0.8],
        show_hud=False,
    )

    window.use_this_view()

    assert window.marker_times == [0.8, 2.6]
