from panopilot.cli import build_parser


def test_spherical_is_default_visual_stabilization_mode():
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


def test_anchored_mode_is_explicitly_selectable():
    args = build_parser().parse_args(
        [
            "project-export",
            "project.json",
            "--visual-stabilization",
            "--visual-stabilization-mode",
            "anchored",
            "--stabilization-crop",
            "18",
        ]
    )

    assert (
        args.visual_stabilization_mode
        == "anchored"
    )
    assert (
        args.stabilization_crop
        == 18.0
    )
