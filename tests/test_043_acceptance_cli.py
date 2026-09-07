from panopilot.cli import build_parser


def test_acceptance_run_command_has_repeatable_report_defaults():
    args = build_parser().parse_args(
        [
            "acceptance-run",
            "project.json",
        ]
    )

    assert args.project == "project.json"
    assert (
        args.report
        == "results/acceptance-043.json"
    )
    assert args.rebuild_preview is False
    assert args.json is False
