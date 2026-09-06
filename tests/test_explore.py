import numpy as np

from panopilot.explore import ExploreState, ExploreWindow


def test_drag_changes_transient_camera_and_clamps_pitch():
    state = ExploreState()

    state.apply_drag(dx_pixels=-100, dy_pixels=1000, view_width=800)

    # Grab interaction: dragging left looks right.
    assert state.yaw_deg > 0
    assert state.pitch_deg == state.pitch_limit_deg


def test_reset_restores_initial_exploratory_view():
    state = ExploreState(
        yaw_deg=25,
        pitch_deg=-10,
        fov_deg=70,
        aspect="9:16",
        initial_yaw_deg=25,
        initial_pitch_deg=-10,
        initial_fov_deg=70,
        initial_aspect="9:16",
    )

    state.apply_drag(-100, 50, 800)
    state.apply_wheel_steps(2)
    state.set_aspect("16:9")
    state.reset()

    assert state.yaw_deg == 25
    assert state.pitch_deg == -10
    assert state.fov_deg == 70
    assert state.aspect == "9:16"


def test_wheel_positive_zooms_in_and_respects_bounds():
    state = ExploreState(fov_deg=90)

    state.apply_wheel_steps(1)
    assert state.fov_deg < 90

    state.apply_wheel_steps(100)
    assert state.fov_deg == state.min_fov_deg

    state.apply_wheel_steps(-100)
    assert state.fov_deg == state.max_fov_deg


def test_yaw_wraps_cleanly():
    state = ExploreState(yaw_deg=179)
    state.apply_drag(-100, 0, 800)
    assert -180 <= state.yaw_deg < 180


def test_wheel_delta_normalizes_qt_angle_delta():
    assert ExploreWindow.wheel_steps(120) == 1.0
    assert ExploreWindow.wheel_steps(-120) == -1.0
    assert ExploreWindow.wheel_steps(60) == 0.5


def test_render_has_requested_explore_aspect_shape():
    panorama = np.zeros((360, 720, 3), dtype=np.uint8)

    landscape = ExploreWindow(
        panorama,
        state=ExploreState(aspect="16:9"),
        source_time=2.0,
        landscape_size=(320, 180),
        portrait_size=(180, 320),
        show_hud=False,
    )
    assert landscape.render().shape == (180, 320, 3)

    portrait = ExploreWindow(
        panorama,
        state=ExploreState(aspect="9:16"),
        source_time=2.0,
        landscape_size=(320, 180),
        portrait_size=(180, 320),
        show_hud=False,
    )
    assert portrait.render().shape == (320, 180, 3)
