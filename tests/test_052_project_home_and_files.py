import json
from pathlib import Path

from panopilot.project import Project, save_project


ROOT = Path(__file__).resolve().parents[1]
PROJECT_EDITOR = (ROOT / "src" / "panopilot" / "project_editor.py").read_text(encoding="utf-8")


def test_home_clip_browser_is_bottom_wrapping_and_vertically_scrollable():
    assert "self.list.setWrapping(True)" in PROJECT_EDITOR
    assert "self.list.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)" in PROJECT_EDITOR
    assert "self.list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)" in PROJECT_EDITOR
    assert "layout.addWidget(self.editor_host, 1)" in PROJECT_EDITOR
    assert "layout.addWidget(self.clip_strip_frame, 0)" in PROJECT_EDITOR


def test_home_exposes_edit_and_settings_with_a_shrinkable_project_name():
    assert 'self.home_heading = QLabel("Project")' not in PROJECT_EDITOR
    assert 'self.home_edit_button = QPushButton("Edit Selected Clip")' in PROJECT_EDITOR
    assert 'self.home_settings_button = QPushButton("Project Settings…")' in PROJECT_EDITOR
    assert "double-click to edit" not in PROJECT_EDITOR
    assert 'self.home_name_edit.setObjectName("projectNameEdit")' in PROJECT_EDITOR
    assert "self.home_name_edit.setMinimumWidth(0)" in PROJECT_EDITOR


def test_home_workflow_orders_edit_arrange_preview_and_export():
    assert 'home_actions.addWidget(self.home_edit_button, 0, 0)' in PROJECT_EDITOR
    assert 'home_actions.addWidget(self.home_arrange_button, 0, 1)' in PROJECT_EDITOR
    assert 'home_actions.addWidget(self.home_preview_button, 1, 0)' in PROJECT_EDITOR
    assert 'home_actions.addWidget(self.home_export_button, 1, 1)' in PROJECT_EDITOR
    assert 'self.home_open_button = QPushButton("Open Project…")' in PROJECT_EDITOR


def test_clip_browser_supports_multi_add_and_context_menu_actions():
    assert "QFileDialog.getOpenFileNames(" in PROJECT_EDITOR
    assert 'self.home_add_clips_button = QPushButton("+ Add Clips…")' in PROJECT_EDITOR
    assert "self.list.customContextMenuRequested.connect(self._show_clip_context_menu)" in PROJECT_EDITOR
    assert 'edit_item = menu.addAction("Edit")' in PROJECT_EDITOR
    assert 'info_item = menu.addAction("View Clip Info")' in PROJECT_EDITOR
    assert 'remove_item = menu.addAction("Remove From Project")' in PROJECT_EDITOR


def test_double_click_or_context_edit_can_wait_for_preview_then_open_automatically():
    assert "self.pending_clip_edit = (clip.id, str(initial_mode))" in PROJECT_EDITOR
    assert 'pending_snapshot.state == "succeeded"' in PROJECT_EDITOR
    assert "QTimer.singleShot(" in PROJECT_EDITOR
    assert "explicit_clip_id=clip_id" in PROJECT_EDITOR


def test_file_menu_can_open_an_arbitrary_project_and_save_as_arbitrary_destination():
    assert 'self.open_project_action = QAction("&Open Project…", self)' in PROJECT_EDITOR
    assert "QFileDialog.getOpenFileName(" in PROJECT_EDITOR
    assert "nonlocal session, project_path" in PROJECT_EDITOR
    assert "project_path = target_path" in PROJECT_EDITOR
    assert "session = ProjectSession(loaded, path=project_path)" in PROJECT_EDITOR
    assert "QFileDialog.getSaveFileName(" in PROJECT_EDITOR


def test_saved_project_references_source_media_with_absolute_paths(tmp_path, monkeypatch):
    work = tmp_path / "work"
    work.mkdir()
    monkeypatch.chdir(work)
    project = Project()
    project.add_clip("media/drive.OSV", source_identity_value=None)
    output = tmp_path / "projects" / "tour.json"
    save_project(project, output, create_backup=False)
    data = json.loads(output.read_text(encoding="utf-8"))
    stored = Path(data["clips"][0]["source"])
    assert stored.is_absolute()
    assert stored == (work / "media" / "drive.OSV").resolve(strict=False)
