from panopilot.cli import build_parser


def test_project_export_accepts_fps_override():
    args = build_parser().parse_args(
        [
            "project-export",
            "project.json",
            "--fps",
            "60",
        ]
    )

    assert args.fps == "60"


def test_project_export_fps_override_defaults_to_saved_project():
    args = build_parser().parse_args(
        [
            "project-export",
            "project.json",
        ]
    )

    assert args.fps is None
