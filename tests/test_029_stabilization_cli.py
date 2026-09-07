from panopilot.cli import build_parser

def test_export_stabilization_override_optional():
    a=build_parser().parse_args(['project-export','p.json'])
    assert a.stabilization_amount is None

def test_export_stabilization_override_percent():
    a=build_parser().parse_args(['project-export','p.json','--stabilization-amount','70'])
    assert a.stabilization_amount==70.0
