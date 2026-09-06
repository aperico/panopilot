from panopilot.cli import build_parser


def test_explore_015_preview_defaults():
    args = build_parser().parse_args(["explore", "sample.OSV"])
    assert args.preview_fps == 20.0
    assert args.panorama_width == 1280
    assert args.panorama_height == 640
    assert args.rebuild_preview is False
    assert args.no_preview_cache is False


def test_prepare_preview_command_registered():
    args = build_parser().parse_args(["prepare-preview", "sample.OSV"])
    assert args.width == 1280
    assert args.height == 640
    assert args.fps == 20.0
