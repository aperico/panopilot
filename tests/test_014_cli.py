from panopilot.cli import build_parser


def _parse(*args):
    return build_parser().parse_args(list(args))


def test_explore_camera_defaults_follow_view_path():
    args = _parse("explore", "sample.OSV")

    assert args.yaw is None
    assert args.pitch is None
    assert args.fov is None


def test_seek_step_default_and_override():
    default = _parse("explore", "sample.OSV")
    custom = _parse(
        "explore",
        "sample.OSV",
        "--seek-step-ms",
        "250",
    )

    assert default.seek_step_ms == 100.0
    assert custom.seek_step_ms == 250.0
