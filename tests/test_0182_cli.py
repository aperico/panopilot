from panopilot.cli import build_parser


def test_reframe_path_accepts_clip_id_selector():
    args = build_parser().parse_args(
        [
            "reframe-path",
            "project.json",
            "clip-2",
            "--time",
            "2.0",
        ]
    )

    assert args.source == "clip-2"


def test_camera_at_accepts_clip_id_selector():
    args = build_parser().parse_args(
        [
            "camera-at",
            "project.json",
            "clip-2",
            "--time",
            "2.0",
        ]
    )

    assert args.source == "clip-2"
