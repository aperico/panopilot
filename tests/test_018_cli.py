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


def test_project_edit_command_is_registered():
    assert "project-edit" in _commands(
        build_parser()
    )


def test_project_edit_accepts_multiple_sources():
    args = build_parser().parse_args(
        [
            "project-edit",
            "a.OSV",
            "b.OSV",
            "--project",
            "p.json",
        ]
    )

    assert args.sources == [
        "a.OSV",
        "b.OSV",
    ]
    assert args.project == "p.json"
