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


def test_project_preview_command_is_registered():
    assert "project-preview" in _commands(
        build_parser()
    )


def test_project_preview_parser():
    args = build_parser().parse_args(
        [
            "project-preview",
            "project.json",
            "--view-long-edge",
            "800",
        ]
    )

    assert args.project == "project.json"
    assert args.view_long_edge == 800
