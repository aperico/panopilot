\
from panopilot.cli import build_parser

def test_default_pipeline_is_panorama():
    a=build_parser().parse_args(['project-export','project.json'])
    assert a.render_pipeline == 'panorama'

def test_direct_pipeline_parses():
    a=build_parser().parse_args(['project-export','project.json','--render-pipeline','direct'])
    assert a.render_pipeline == 'direct'
