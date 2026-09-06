import numpy as np

from panopilot.explore import ExploreState, ExploreWindow


def _panorama():
    return np.zeros((180, 360, 3), dtype=np.uint8)


def test_play_at_physical_source_end_restarts_from_zero():
    window = ExploreWindow(
        _panorama(),
        state=ExploreState(),
        source_time=6.0,
        source_duration=6.0,
        playback_fps=20.0,
        show_hud=False,
    )
    assert window.playback_start_time() == 0.0


def test_play_at_clip_out_restarts_from_clip_in():
    window = ExploreWindow(
        _panorama(),
        state=ExploreState(),
        source_time=5.0,
        source_duration=6.0,
        trim_in_source_time=1.0,
        trim_out_source_time=5.0,
        playback_fps=20.0,
        show_hud=False,
    )
    assert window.playback_start_time() == 1.0


def test_play_inside_clip_resumes_current_time():
    window = ExploreWindow(
        _panorama(),
        state=ExploreState(),
        source_time=3.0,
        source_duration=6.0,
        trim_in_source_time=1.0,
        trim_out_source_time=5.0,
        playback_fps=20.0,
        show_hud=False,
    )
    assert window.playback_start_time() == 3.0


def test_play_before_clip_in_starts_at_clip_in():
    window = ExploreWindow(
        _panorama(),
        state=ExploreState(),
        source_time=0.5,
        source_duration=6.0,
        trim_in_source_time=1.0,
        trim_out_source_time=5.0,
        playback_fps=20.0,
        show_hud=False,
    )
    assert window.playback_start_time() == 1.0


def test_logical_end_survives_cache_frame_snap():
    from panopilot.virtual_camera import VirtualCamera

    def seek_callback(requested):
        # A 20 fps cache for a 6.016 s source can have its last displayed
        # frame at 5.950 s even though the logical timeline was sought to end.
        return {
            "source_time": 5.95,
            "panorama": _panorama(),
            "camera": VirtualCamera(),
            "trim_in_source_time": 0.0,
            "trim_out_source_time": None,
        }

    window = ExploreWindow(
        _panorama(),
        state=ExploreState(),
        source_time=0.0,
        source_duration=6.016,
        playback_fps=20.0,
        seek_callback=seek_callback,
        show_hud=False,
    )
    window.seek(6.016)
    assert window.source_time == 5.95
    assert window.at_playback_end is True
    assert window.playback_start_time() == 0.0
