from panopilot.cli import build_parser


def test_project_export_defaults_to_auto_rolling_shutter():
    args = build_parser().parse_args(
        [
            "project-export",
            "project.json",
        ]
    )

    assert (
        args.rolling_shutter
        == "auto"
    )
    assert (
        args.rolling_shutter_readout_ms
        is None
    )
    assert (
        args.rolling_shutter_reference_offset_ms
        == 0.0
    )


def test_project_export_accepts_manual_rolling_shutter_parameters():
    args = build_parser().parse_args(
        [
            "project-export",
            "project.json",
            "--rolling-shutter",
            "manual",
            "--rolling-shutter-readout-ms",
            "8.2",
            "--rolling-shutter-reference-offset-ms",
            "-1.5",
            "--rolling-shutter-direction",
            "bottom-to-top",
        ]
    )

    assert (
        args.rolling_shutter
        == "manual"
    )
    assert (
        args.rolling_shutter_readout_ms
        == 8.2
    )
    assert (
        args.rolling_shutter_reference_offset_ms
        == -1.5
    )
    assert (
        args.rolling_shutter_direction
        == "bottom-to-top"
    )
