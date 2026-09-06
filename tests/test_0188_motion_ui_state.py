import numpy as np
import pytest

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


def test_motion_callback_updates_editor_state_and_camera():
    def callback(
        *,
        easing,
        strength,
        source_time,
    ):
        return {
            "changed": True,
            "label": "Camera motion",
            "dirty": True,
            "can_undo": True,
            "can_redo": False,
            "undo_label": "Camera motion",
            "redo_label": None,
            "camera_motion_easing": easing,
            "camera_motion_strength": strength,
            "camera": VirtualCamera(
                25.0,
                -2.0,
                80.0,
            ),
            "aspect": "16:9",
        }

    state = ExploreState()

    window = ExploreWindow(
        _panorama(),
        state=state,
        source_time=1.0,
        source_duration=6.0,
        motion_callback=callback,
        show_hud=False,
    )

    result = window.set_camera_motion(
        easing="ease-out",
        strength=0.55,
    )

    assert result["changed"] is True
    assert window.camera_motion_easing == "ease-out"
    assert window.camera_motion_strength == pytest.approx(
        0.55
    )
    assert state.yaw_deg == pytest.approx(
        25.0
    )
    assert window.project_dirty is True
