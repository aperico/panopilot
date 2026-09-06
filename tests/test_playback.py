import numpy as np

from panopilot.explore import ExploreState, ExploreWindow


def _panorama():
    return np.zeros((180, 360, 3), dtype=np.uint8)


def test_playback_configuration_is_state_only_before_qt_loop():
    window = ExploreWindow(
        _panorama(),
        state=ExploreState(),
        source_time=1.0,
        source_duration=3.0,
        playback_fps=20.0,
        cache_media_path="cache.mp4",
        audio_enabled=True,
        show_hud=False,
    )
    assert window.playing is False
    assert window.playback_fps == 20.0
    assert window.cache_media_path == "cache.mp4"


def test_seek_during_navigation_still_restores_persisted_camera():
    from panopilot.virtual_camera import VirtualCamera

    def seek_callback(t):
        return {
            "source_time": t,
            "panorama": _panorama(),
            "camera": VirtualCamera(20.0, -3.0, 75.0),
        }

    state = ExploreState()
    window = ExploreWindow(
        _panorama(),
        state=state,
        source_time=0.0,
        source_duration=3.0,
        seek_callback=seek_callback,
        show_hud=False,
    )
    window.seek(1.0)
    assert state.yaw_deg == 20.0
    assert state.pitch_deg == -3.0
    assert state.fov_deg == 75.0
