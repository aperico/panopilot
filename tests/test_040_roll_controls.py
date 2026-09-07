from pathlib import Path

from panopilot.explore import ExploreState
from panopilot.project import (
    CameraPosition,
    Project,
)
from panopilot.view_path import (
    evaluate_view_path,
)
import panopilot.explore as explore_module


def test_explore_roll_nudge_clockwise_and_counterclockwise():
    state = ExploreState(
        roll_deg=10.0
    )

    state.nudge_view(
        roll_delta_deg=5.0
    )
    assert state.roll_deg == 15.0
    assert state.camera().roll_deg == 15.0

    state.nudge_view(
        roll_delta_deg=-20.0
    )
    assert state.roll_deg == -5.0


def test_roll_wraps_at_panorama_angle_boundary():
    state = ExploreState(
        roll_deg=179.0
    )

    state.nudge_view(
        roll_delta_deg=5.0
    )

    assert state.roll_deg == -176.0


def test_camera_position_roll_round_trip_and_v6_migration():
    project = Project.from_dict(
        {
            "schema_version": 6,
            "output_frame": {
                "aspect": "16:9",
                "resolution": "1080p",
                "quality": "high",
            },
            "clips": [
                {
                    "id": "clip-1",
                    "source": "sample.OSV",
                    "camera_positions": [
                        {
                            "source_time": 1.0,
                            "yaw_deg": 10.0,
                            "pitch_deg": 5.0,
                            "fov_deg": 80.0,
                        }
                    ],
                }
            ],
        }
    )

    assert project.schema_version == 8
    assert (
        project.clips[0]
        .camera_positions[0]
        .roll_deg
        == 0.0
    )

    project.clips[0].camera_positions[0].roll_deg = 12.5
    data = project.to_dict()

    assert (
        data["clips"][0]
        ["camera_positions"][0]
        ["roll_deg"]
        == 12.5
    )


def test_view_path_interpolates_roll_shortest_route():
    positions = [
        CameraPosition(
            source_time=0.0,
            yaw_deg=0.0,
            pitch_deg=0.0,
            fov_deg=90.0,
            roll_deg=170.0,
        ),
        CameraPosition(
            source_time=10.0,
            yaw_deg=0.0,
            pitch_deg=0.0,
            fov_deg=90.0,
            roll_deg=-170.0,
        ),
    ]

    sample = evaluate_view_path(
        positions,
        5.0,
        interpolation="linear",
        strength=1.0,
    )

    assert abs(
        abs(sample.camera.roll_deg)
        - 180.0
    ) < 1e-6


def test_editor_exposes_clockwise_and_counterclockwise_roll_controls():
    source = Path(
        explore_module.__file__
    ).read_text(
        encoding="utf-8"
    )

    for token in (
        "self.view_ccw_button",
        "self.view_cw_button",
        '"↺"',
        '"↻"',
        "Rotate view clockwise",
        "Rotate view counter-clockwise",
        "Qt.Key.Key_BracketLeft",
        "Qt.Key.Key_BracketRight",
        "roll_direction",
    ):
        assert token in source
