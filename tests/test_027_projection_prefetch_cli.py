from panopilot.cli import build_parser


def test_projection_prefetch_defaults_on():
    args = build_parser().parse_args(
        [
            "project-export",
            "project.json",
        ]
    )

    assert args.projection_prefetch is True


def test_projection_prefetch_can_be_disabled():
    args = build_parser().parse_args(
        [
            "project-export",
            "project.json",
            "--no-projection-prefetch",
        ]
    )

    assert args.projection_prefetch is False
