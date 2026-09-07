import pytest
from panopilot.project import CameraPosition, Clip, Project
from panopilot.session import ProjectSession

def _project():
    return Project(clips=[Clip(id='clip-1',source='source.OSV',camera_positions=[CameraPosition(source_time=1.0,yaw_deg=20.0,pitch_deg=-5.0,roll_deg=3.0,fov_deg=80.0)])])

def test_move_camera_position_preserves_camera_and_is_undoable():
    session=ProjectSession(_project()); result=session.move_camera_position_from_clip('clip-1',source_time=1.0,new_source_time=2.5,source_duration=10.0,tolerance_s=0.01)
    assert result['changed']; p=session.project.clips[0].camera_positions[0]
    assert (p.source_time,p.yaw_deg,p.pitch_deg,p.roll_deg,p.fov_deg)==(2.5,20.0,-5.0,3.0,80.0)
    session.undo(); assert session.project.clips[0].camera_positions[0].source_time==1.0
    session.redo(); assert session.project.clips[0].camera_positions[0].source_time==2.5

def test_move_camera_position_rejects_collision():
    project=_project(); project.clips[0].camera_positions.append(CameraPosition(3.0,0.0,0.0,90.0)); session=ProjectSession(project)
    with pytest.raises(ValueError,match='already exists'): session.move_camera_position_from_clip('clip-1',source_time=1.0,new_source_time=3.0,source_duration=10.0,tolerance_s=0.01)

def test_move_camera_position_rejects_outside_source_duration():
    session=ProjectSession(_project())
    with pytest.raises(ValueError,match='outside the Source Recording'): session.move_camera_position_from_clip('clip-1',source_time=1.0,new_source_time=12.0,source_duration=10.0)
