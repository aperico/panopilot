from panopilot.cli import build_parser

def test_visual_stabilization_is_opt_in():
    args=build_parser().parse_args(["project-export","project.json"])
    assert args.visual_stabilization is False
    assert args.stabilization_crop == 25.0

def test_visual_stabilization_controls():
    args=build_parser().parse_args(["project-export","project.json","--visual-stabilization","--stabilization-crop","30"])
    assert args.visual_stabilization is True
    assert args.stabilization_crop == 30.0
