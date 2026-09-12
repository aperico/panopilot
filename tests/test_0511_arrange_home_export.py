from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "src" / "panopilot" / "project_editor.py").read_text(encoding="utf-8")


def arrange_block():
    start = SOURCE.index("    class ArrangeTimelineWidget")
    end = SOURCE.index("        def _preview_profile", start)
    return SOURCE[start:end]


def test_arrange_has_only_project_workflow_navigation_and_compact_track():
    block = arrange_block()
    assert 'self.back_button = QPushButton("← Project")' in block
    assert 'QPushButton("Reframe")' not in block
    assert 'QPushButton("Trim")' not in block
    assert 'QPushButton("Arrange")' not in block
    assert "self.scroll.setFixedHeight(100)" in block
    assert "card.setFixedHeight(84)" in block


def test_arrange_uses_one_centered_aspect_preserving_thumbnail_per_clip():
    block = arrange_block()
    assert "self.thumbnail = QLabel()" in block
    assert "self.thumbnail.setScaledContents(False)" in block
    assert "Qt.AspectRatioMode.KeepAspectRatio" in block
    assert "self.thumbnail.setFixedHeight(56)" in block
    assert "for _ in range(count)" not in block
    assert "thumb_layout" not in block


def test_home_exposes_edit_alongside_context_actions_and_final_export():
    assert 'self.home_edit_button = QPushButton("Edit Selected Clip")' in SOURCE
    assert 'self.home_export_button = QPushButton("Export Final Video…")' in SOURCE
    assert 'edit_item = menu.addAction("Edit")' in SOURCE
    assert 'info_item = menu.addAction("View Clip Info")' in SOURCE
    assert 'remove_item = menu.addAction("Remove From Project")' in SOURCE
    assert "self.home_export_button.clicked.connect(self._export_project)" in SOURCE


def test_double_click_opens_the_clicked_clip_not_stale_current_selection():
    assert "self.list.doubleClicked.connect(self._edit_clip_index)" in SOURCE
    assert "def _edit_clip_index(self, index):" in SOURCE
    assert "clip_id = self.clip_model.clip_id_for_index(index)" in SOURCE
    assert "self._edit_selected(explicit_clip_id=clip_id)" in SOURCE


def test_top_level_export_menu_exposes_final_video_export():
    assert 'self.export_action = QAction("Export &Final Video…", self)' in SOURCE
    assert 'export_menu = self.menuBar().addMenu("E&xport")' in SOURCE
    assert "export_menu.addAction(self.export_action)" in SOURCE
