from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXPLORE = (ROOT / "src" / "panopilot" / "explore.py").read_text()
THEME = (ROOT / "src" / "panopilot" / "desktop_theme.py").read_text()


def test_timeline_navigation_widgets_exist_before_signal_wiring():
    """Opening the Clip Editor must not access timeline_scroll before creation."""
    created = EXPLORE.index(
        "self.timeline_scroll = QScrollBar(Qt.Orientation.Horizontal)"
    )
    connected = EXPLORE.index(
        "self.timeline_scroll.valueChanged.connect(self._timeline_scroll_changed)"
    )
    zoom_created = EXPLORE.index('self.timeline_zoom_out = QPushButton("−")')
    zoom_connected = EXPLORE.index(
        "self.timeline_zoom_out.clicked.connect(lambda: self._zoom_timeline(-1.0))"
    )
    assert created < connected
    assert zoom_created < zoom_connected


def test_embedded_editor_host_has_explicit_dark_theme_fallback():
    """An empty/constructing editor host must never inherit a light system palette."""
    assert "QWidget#editorHost" in THEME
    assert "QWidget#panopilotEditor QWidget" in THEME
    assert "background-color: #171a1f" in THEME
    assert "color: #f1f3f5" in THEME
    assert "QMessageBox {" in THEME
    assert "QMessageBox QLabel" in THEME
