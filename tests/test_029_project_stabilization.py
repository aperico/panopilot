from panopilot.project import Project
from panopilot.session import ProjectSession

def test_schema_v4_roundtrip():
    p=Project(stabilization_amount=0.72); d=p.to_dict()
    assert d['schema_version']==8 and d['stabilization']['amount']==0.72
    assert Project.from_dict(d).stabilization_amount==0.72

def test_schema_v3_migrates_to_zero():
    p=Project.from_dict({'schema_version':3,'output_frame':{'aspect':'16:9'},
                         'camera_motion':{'easing':'smooth','strength':1.0},'clips':[]})
    assert p.stabilization_amount==0.0

def test_stabilization_edit_is_undoable():
    s=ProjectSession(Project()); s.set_stabilization_amount(0.65)
    assert s.project.stabilization_amount==0.65
    s.undo(); assert s.project.stabilization_amount==0.0
