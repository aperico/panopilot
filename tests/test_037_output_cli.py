from panopilot.cli import build_parser


def test_project_export_accepts_resolution_and_quality_overrides():
    args = build_parser().parse_args(
        [
            "project-export",
            "project.json",
            "--resolution",
            "720p",
            "--quality",
            "very-high",
        ]
    )

    assert args.resolution == "720p"
    assert args.quality == "very-high"
    assert args.crf is None
    assert args.preset is None
