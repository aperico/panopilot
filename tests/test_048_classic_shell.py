from pathlib import Path

import panopilot.explore as explore
import panopilot.project_editor as project_editor


def _source(module):
    return Path(module.__file__).read_text(encoding="utf-8")


def test_workspace_uses_native_main_window_menu_and_status_bar():
    source = _source(project_editor)
    assert "class ProjectWidget(QMainWindow):" in source
    for menu in ('"&File"', '"&Edit"', '"&Clip"', '"&View"', '"&Settings"'):
        assert f"addMenu({menu})" in source
    assert "status_bar = self.statusBar()" in source
    assert "status_bar.addWidget(self.project_info, 2)" in source
    assert "status_bar.addPermanentWidget(self.work_status)" in source


def test_global_commands_are_menu_actions_not_workspace_buttons():
    source = _source(project_editor)
    for token in (
        "self.save_action = QAction",
        "self.export_action = QAction",
        "self.undo_action = QAction",
        "self.redo_action = QAction",
        "self.close_project_action = QAction",
        "self.settings_action = QAction",
    ):
        assert token in source
    assert "self.top_bar" not in source
    assert "self.work_panel" not in source
    assert "self.settings_frame" not in source


def test_project_information_and_background_work_live_in_status_bar():
    source = _source(project_editor)
    assert "self.project_info.setText(presentation.summary)" in source
    assert 'self.work_status = QLabel("Idle")' in source
    assert "QFrame#workPanel" not in source or "self.work_panel" not in source


def test_clip_strip_is_automatically_hidden_during_clip_editing():
    source = _source(project_editor)
    assert "self.clip_strip_frame.hide()" in source
    assert "self.show_clips_action.isChecked()" in source
    assert "and not self.clip_editor_active" in source


def test_embedded_preview_surface_fills_media_container():
    source = _source(explore)
    assert "canvas_layout.addWidget(self.image_label, 1)" in source
    assert "canvas_layout.addStretch(1)" not in source
    assert "self._source_pixmap.scaled(" in source
    assert "Qt.AspectRatioMode.KeepAspectRatio" in source


def test_embedded_editor_moves_save_undo_redo_out_of_transport_row():
    source = _source(explore)
    assert "if embed_host is None:" in source
    assert "timeline_row.addWidget(self.undo_button)" in source
    assert "timeline_row.addWidget(self.redo_button)" in source
    assert "timeline_row.addWidget(self.save_button)" in source


def test_background_poll_does_not_reenable_export_during_clip_editing():
    source = _source(project_editor)
    assert "bool(session.project.clips)\n                    and not self.clip_editor_active" in source
