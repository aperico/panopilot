from pathlib import Path

import panopilot.project_editor as project_editor_module
import panopilot.project_export as project_export_module


def _source(module):
    return Path(
        module.__file__
    ).read_text(
        encoding="utf-8"
    )


def test_project_organizer_exposes_export_action():
    source = _source(
        project_editor_module
    )

    assert 'self.export_action = QAction("Export &Final Video…", self)' in source
    assert 'self.export_action.triggered.connect(self._export_project)' in source
    assert 'file_menu.addAction(self.export_action)' in source
    assert 'BackgroundJobManager' in source
    assert 'export_project_video(' in source
    assert 'self.abort_export_button = QPushButton("Abort")' in source
    assert "getSaveFileName" in source


def test_final_export_does_not_use_preview_cache():
    source = _source(
        project_export_module
    )

    assert "FactoryCalibratedMapper" in source
    assert "extract_calibration" in source
    assert "evaluate_clip_view_path" in source
    assert "ensure_preview_cache" not in source
    assert "PanoramaCacheReader" not in source


def test_final_export_is_atomic_and_verified_before_replace():
    source = _source(
        project_export_module
    )

    assert ".preparing" in source
    assert "verify_project_export" in source
    assert "output_preparing.replace" in source
