import json
from pathlib import Path
import pytest
from panopilot.media_identity import identity_matches, source_identity, source_reference_status
from panopilot.project import Clip, Project, assert_project_sources, load_project, save_project
from panopilot.project_editor import import_sources_into_session
from panopilot.session import ProjectSession

def test_sampled_identity_detects_content_replacement_even_if_path_is_same(tmp_path):
    source=tmp_path/'sample.OSV'; source.write_bytes(b'A'*4096)
    expected=source_identity(source,sample_bytes=512)
    source.write_bytes(b'B'*4096); actual=source_identity(source,sample_bytes=512)
    assert not identity_matches(expected,actual)
    assert source_reference_status(source,expected)['status']=='mismatch'

def test_touching_same_content_does_not_change_authoritative_identity(tmp_path):
    source=tmp_path/'sample.OSV'; source.write_bytes(b'stable-media'*800)
    first=source_identity(source,sample_bytes=256); source.touch(); second=source_identity(source,sample_bytes=256)
    assert identity_matches(first,second)

def test_project_schema_v8_persists_expected_identity(tmp_path):
    source=tmp_path/'source.OSV'; source.write_bytes(b'camera'*1000)
    project=Project(); project.add_clip(source); path=tmp_path/'project.json'; save_project(project,path,create_backup=False)
    data=json.loads(path.read_text()); assert data['schema_version']==10
    assert data['clips'][0]['source_identity']['algorithm']=='sampled-sha256-v1'
    assert_project_sources(load_project(path))

def test_project_blocks_silent_source_substitution(tmp_path):
    source=tmp_path/'source.OSV'; source.write_bytes(b'original'*1000)
    identity=source_identity(source,sample_bytes=128)
    project=Project(clips=[Clip(id='clip-1',source=str(source),source_identity=identity)])
    source.write_bytes(b'different'*1000)
    with pytest.raises(RuntimeError,match='will not silently substitute'): assert_project_sources(project)

def test_import_rejects_one_source_without_blocking_other(monkeypatch):
    class Acceptance:
        def __init__(self,accepted,reason,identity=None): self.accepted=accepted; self.reason=reason; self.identity=identity
    def fake(source,decode_smoke=True):
        if str(source).endswith('bad.OSV'): return Acceptance(False,'missing DJI calibration')
        return Acceptance(True,'supported',{'algorithm':'sampled-sha256-v1','size':1,'fingerprint':'x'})
    monkeypatch.setattr('panopilot.project_editor.validate_source_recording',fake)
    session=ProjectSession(Project()); result=import_sources_into_session(session,['good.OSV','bad.OSV','good2.OSV'],validate=True)
    assert len(result['added_clip_ids'])==2 and len(result['rejected'])==1
    assert [Path(c.source).name for c in session.project.clips]==['good.OSV','good2.OSV']
