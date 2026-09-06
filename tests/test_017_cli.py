from panopilot.cli import build_parser


def _commands(parser):
    for action in parser._actions:
        choices = getattr(action, "choices", None)
        if isinstance(choices, dict):
            return set(choices)
    return set()


def test_timeline_info_command_is_registered():
    assert "timeline-info" in _commands(build_parser())


def test_explore_default_time_uses_clip_in():
    args = build_parser().parse_args(["explore", "sample.OSV"])
    assert args.time is None
