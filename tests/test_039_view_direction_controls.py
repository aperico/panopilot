from pathlib import Path

from panopilot.explore import ExploreState
import panopilot.explore as explore_module


def test_precise_view_nudge_changes_yaw_and_pitch():
    state = ExploreState(
        yaw_deg=10.0,
        pitch_deg=-5.0,
    )

    state.nudge_view(
        yaw_delta_deg=1.0,
        pitch_delta_deg=0.25,
    )

    assert state.yaw_deg == 11.0
    assert state.pitch_deg == -4.75


def test_view_nudge_wraps_yaw_and_clamps_pitch():
    state = ExploreState(
        yaw_deg=179.0,
        pitch_deg=84.0,
    )

    state.nudge_view(
        yaw_delta_deg=5.0,
        pitch_delta_deg=5.0,
    )

    assert state.yaw_deg == -176.0
    assert state.pitch_deg == state.pitch_limit_deg


def test_view_nudge_is_transient_navigation_only():
    state = ExploreState(
        yaw_deg=0.0,
        pitch_deg=0.0,
        initial_yaw_deg=0.0,
        initial_pitch_deg=0.0,
    )

    camera = state.nudge_view(
        yaw_delta_deg=-0.25,
    )

    assert camera.yaw_deg == -0.25
    assert state.initial_yaw_deg == 0.0
    assert state.initial_pitch_deg == 0.0


def test_editor_exposes_on_screen_direction_pad_and_shift_arrow_shortcuts():
    source = Path(
        explore_module.__file__
    ).read_text(
        encoding="utf-8"
    )

    for token in (
        "self.view_left_button",
        "self.view_right_button",
        "self.view_up_button",
        "self.view_down_button",
        "Fine  0.25°",
        "Normal  1°",
        "Coarse  5°",
        "Shift+Arrow",
        "setAutoRepeat",
    ):
        assert token in source
