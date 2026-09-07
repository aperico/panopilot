from panopilot.cli import build_parser


def test_locked_visual_mode_is_available():
    args = build_parser().parse_args(
        [
            "project-export",
            "project.json",
            "--visual-stabilization",
            "--visual-stabilization-mode",
            "locked",
            "--stabilization-crop",
            "50",
        ]
    )

    assert args.visual_stabilization_mode == "locked"
    assert args.stabilization_crop == 50.0
    assert args.locked_stabilization_passes == 2


def test_main_validation_allows_50_percent_crop_for_locked(monkeypatch):
    import sys
    from panopilot.cli import main

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "panopilot",
            "project-export",
            "/definitely/missing/project.json",
            "--visual-stabilization",
            "--visual-stabilization-mode",
            "locked",
            "--stabilization-crop",
            "50",
        ],
    )

    try:
        main()
    except SystemExit as exc:
        message = str(exc)
        assert "stabilization-crop" not in message
        assert "Project does not exist" in message
    else:
        raise AssertionError("Expected missing project error")
