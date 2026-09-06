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


def test_recovery_commands_registered():
    commands = _commands(
        build_parser()
    )

    assert "cache-sources" in commands
    assert (
        "project-rebuild-from-cache"
        in commands
    )


def test_rebuild_cli_parses_order_and_motion():
    args = build_parser().parse_args(
        [
            "project-rebuild-from-cache",
            "project.json",
            "--indexes",
            "2,1",
            "--camera-motion",
            "ease-in-out",
            "--motion-amount",
            "70",
        ]
    )

    assert args.indexes == "2,1"
    assert (
        args.camera_motion
        == "ease-in-out"
    )
    assert args.motion_amount == 70.0
