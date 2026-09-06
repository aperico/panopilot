from panopilot.cli import build_parser


def test_project_export_decoder_defaults_to_auto():
    args = build_parser().parse_args(
        [
            "project-export",
            "project.json",
        ]
    )

    assert args.decoder == "auto"
    assert args.vaapi_device is None


def test_project_export_accepts_explicit_vaapi_device():
    args = build_parser().parse_args(
        [
            "project-export",
            "project.json",
            "--decoder",
            "vaapi",
            "--vaapi-device",
            "/dev/dri/renderD128",
        ]
    )

    assert args.decoder == "vaapi"
    assert (
        args.vaapi_device
        == "/dev/dri/renderD128"
    )
