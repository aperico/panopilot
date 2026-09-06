import numpy as np

from panopilot.explore import ExploreState, ExploreWindow


def test_use_this_view_is_explicit_commit_boundary():
    panorama = np.zeros((180, 360, 3), dtype=np.uint8)
    calls = []

    def commit_callback(**kwargs):
        calls.append(kwargs)
        return {
            "created": True,
            "position_number": 1,
            "camera_position": {
                "source_time": kwargs["source_time"],
                "yaw_deg": kwargs["yaw_deg"],
                "pitch_deg": kwargs["pitch_deg"],
                "fov_deg": kwargs["fov_deg"],
            },
        }

    state = ExploreState()

    window = ExploreWindow(
        panorama,
        state=state,
        source_time=2.0,
        commit_callback=commit_callback,
        show_hud=False,
    )

    state.apply_drag(-100, 20, 800)
    state.apply_wheel_steps(2)

    # Exploration itself still has no side effect.
    assert calls == []

    result = window.use_this_view()

    assert len(calls) == 1
    assert calls[0]["source_time"] == 2.0
    assert result["position_number"] == 1
    assert window.has_uncommitted_changes is False


def test_moving_after_commit_becomes_uncommitted_again():
    panorama = np.zeros((180, 360, 3), dtype=np.uint8)

    def commit_callback(**kwargs):
        return {
            "created": True,
            "position_number": 1,
        }

    state = ExploreState()

    window = ExploreWindow(
        panorama,
        state=state,
        source_time=2.0,
        commit_callback=commit_callback,
        show_hud=False,
    )

    window.use_this_view()
    assert window.has_uncommitted_changes is False

    state.apply_drag(-20, 0, 800)

    assert window.has_uncommitted_changes is True
