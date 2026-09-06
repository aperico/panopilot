from pathlib import Path

import panopilot.project_editor as project_editor_module
import panopilot.project_player as project_player_module


def _source(module):
    return Path(
        module.__file__
    ).read_text(
        encoding="utf-8"
    )


def test_project_organizer_exposes_preview_action():
    source = _source(
        project_editor_module
    )

    assert '"Preview Project"' in source
    assert 'state["action"] = "preview"' in source


def test_project_player_switches_audio_by_clip():
    source = _source(
        project_player_module
    )

    assert "_sync_audio" in source
    assert "frame_state.clip_id" in source
    assert "QMediaPlayer" in source


def test_project_player_uses_persisted_camera_motion():
    source = _source(
        project_player_module
    )

    assert "project.camera_motion_easing" in source
    assert "project.camera_motion_strength" in source
    assert "evaluate_clip_view_path" in source
