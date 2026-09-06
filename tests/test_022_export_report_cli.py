from panopilot.cli import build_parser


def test_project_export_accepts_performance_report_path():
    args = build_parser().parse_args(
        [
            "project-export",
            "project.json",
            "--report",
            "results/performance.json",
        ]
    )

    assert args.report == "results/performance.json"
