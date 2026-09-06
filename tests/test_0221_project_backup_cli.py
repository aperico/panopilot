from panopilot.cli import build_parser


def _commands(parser):
    for action in parser._actions:
        choices = getattr(
            action,
            "choices",
            None,
        )
        if isinstance(
            choices,
            dict,
        ):
            return set(
                choices
            )
    return set()


def test_project_backup_commands_registered():
    commands = _commands(
        build_parser()
    )

    assert "project-backups" in commands
    assert "project-recover" in commands


def test_project_recover_specific_backup_option():
    args = build_parser().parse_args(
        [
            "project-recover",
            "project.json",
            "--backup",
            "backup.json",
        ]
    )

    assert args.project == "project.json"
    assert args.backup == "backup.json"
