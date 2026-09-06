from panopilot.cli import build_parser


def _commands(parser):
    for action in parser._actions:
        choices = getattr(
            action,
            "choices",
            None,
        )
        if isinstance(choices, dict):
            return set(choices)
    return set()


def test_project_export_command_registered():
    assert "project-export" in _commands(
        build_parser()
    )


def test_project_export_defaults():
    args = build_parser().parse_args(
        [
            "project-export",
            "project.json",
        ]
    )

    assert args.output == "results/panopilot_export.mp4"
    assert args.panorama_width == 3840
    assert args.panorama_height == 1920
    assert args.crf == 18
    assert args.preset == "medium"
