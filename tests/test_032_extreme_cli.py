from panopilot.cli import build_parser


def test_project_export_extreme_mode_is_available():
    args = build_parser().parse_args(
        [
            "project-export",
            "project.json",
            "--visual-stabilization",
            "--visual-stabilization-mode",
            "extreme",
            "--stabilization-crop",
            "45",
        ]
    )

    assert (
        args.visual_stabilization_mode
        == "extreme"
    )
    assert (
        args.stabilization_crop
        == 45.0
    )
    assert (
        args.extreme_stabilization_passes
        == 3
    )


def test_spherical_is_new_default():
    args = build_parser().parse_args(
        [
            "project-export",
            "project.json",
        ]
    )

    assert (
        args.visual_stabilization_mode
        == "spherical"
    )
