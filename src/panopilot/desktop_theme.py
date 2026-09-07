"""Shared Qt presentation styling for the PanoPilot desktop workspace.

The theme module intentionally contains no Project/domain behavior. Widgets opt in
through object names so presentation changes do not leak into editing semantics.

0.47 makes foreground/background contrast explicit instead of relying on the host
Qt/GNOME palette. 0.48 extends that contract to the native menu bar, status bar,
and Project Settings dialog. 0.49 adds the compact editor navigation/control rail. 0.50 normalizes nested editor panel spacing and filmstrip treatment.
"""
from __future__ import annotations


WORKSPACE_STYLESHEET = r"""
QMainWindow#panopilotWorkspace,
QWidget#panopilotWorkspace,
QWidget#workspaceCentral,
QWidget#editorHost,
QWidget#panopilotEditor,
QDialog#settingsDialog,
QFrame#projectHome,
QWidget#arrangeWorkspace,
QWidget#arrangeTrack {
    background: #171a1f;
    color: #f1f3f5;
}

/* The embedded editor host must never fall back to the system light palette,
   including during editor construction/error recovery. Child container widgets
   use the same dark surface unless a more specific panel/canvas rule overrides it. */
QWidget#editorHost,
QWidget#panopilotEditor,
QWidget#panopilotEditor QWidget {
    background-color: #171a1f;
    color: #f1f3f5;
}


QMenuBar {
    color: #f1f3f5;
    background: #20242b;
    border-bottom: 1px solid #303640;
    padding: 1px 3px;
}
QMenuBar::item {
    color: #f1f3f5;
    background: transparent;
    padding: 5px 9px;
}
QMenuBar::item:selected,
QMenuBar::item:pressed {
    color: #ffffff;
    background: #333a44;
}
QMenu {
    color: #f1f3f5;
    background: #252a31;
    border: 1px solid #414956;
    padding: 4px;
}
QMenu::item {
    color: #f1f3f5;
    padding: 6px 28px 6px 22px;
}
QMenu::item:selected {
    color: #ffffff;
    background: #31578f;
}
QMenu::item:disabled {
    color: #737c88;
}
QMenu::separator {
    height: 1px;
    background: #414956;
    margin: 4px 8px;
}

/* Error/info dialogs can be created while an embedded editor is failing.
   Theme the QMessageBox surface explicitly so light system backgrounds never
   combine with PanoPilot's light foreground colors. */
QMessageBox {
    background: #20242b;
    color: #f1f3f5;
}
QMessageBox QLabel {
    background: transparent;
    color: #f1f3f5;
}
QMessageBox QPushButton {
    min-width: 76px;
    min-height: 28px;
    color: #f1f3f5;
    background: #292f37;
    border: 1px solid #414956;
    border-radius: 6px;
    padding: 4px 10px;
}
QMessageBox QPushButton:hover {
    background: #333a44;
    border-color: #586474;
}

QStatusBar#workspaceStatusBar {
    color: #d9dee6;
    background: #20242b;
    border-top: 1px solid #303640;
    min-height: 24px;
}
QStatusBar#workspaceStatusBar::item {
    border: none;
}
QLabel#statusContext {
    color: #d9dee6;
    padding-left: 4px;
}
QPushButton#statusAction {
    min-height: 18px;
    max-height: 20px;
    padding: 1px 7px;
}

QMainWindow#panopilotWorkspace QLabel,
QWidget#panopilotWorkspace QLabel,
QWidget#panopilotEditor QLabel,
QDialog#settingsDialog QLabel,
QMainWindow#panopilotWorkspace QCheckBox,
QWidget#panopilotWorkspace QCheckBox,
QWidget#panopilotEditor QCheckBox,
QMainWindow#panopilotWorkspace QRadioButton,
QWidget#panopilotWorkspace QRadioButton,
QWidget#panopilotEditor QRadioButton {
    color: #f1f3f5;
}

QFrame#topBar,
QFrame#clipStripFrame,
QFrame#settingsPanel,
QFrame#workPanel,
QFrame#editorControls,
QFrame#modePanel {
    background: #20242b;
    border: 1px solid #303640;
    border-radius: 8px;
}

QLabel#workspaceTitle {
    color: #ffffff;
    font-size: 18px;
    font-weight: 650;
}
QLabel#workspaceSummary,
QLabel#secondaryText,
QLabel#editorSecondaryText {
    color: #aeb6c2;
}
QLabel#modeHint {
    color: #c8ced7;
    padding-left: 4px;
}

QLabel#brandWordmark {
    background: transparent;
    border: none;
    padding-bottom: 2px;
}

QMainWindow#panopilotWorkspace QPushButton,
QWidget#panopilotWorkspace QPushButton,
QWidget#panopilotEditor QPushButton,
QDialog#settingsDialog QPushButton,
QMainWindow#panopilotWorkspace QToolButton,
QWidget#panopilotWorkspace QToolButton,
QWidget#panopilotEditor QToolButton,
QWidget#panopilotWorkspace QComboBox,
QMainWindow#panopilotWorkspace QComboBox,
QDialog#settingsDialog QComboBox,
QWidget#panopilotEditor QComboBox,
QWidget#panopilotWorkspace QLineEdit,
QMainWindow#panopilotWorkspace QLineEdit,
QDialog#settingsDialog QLineEdit {
    min-height: 28px;
    color: #f1f3f5;
    background: #292f37;
    border: 1px solid #414956;
    border-radius: 6px;
    padding: 4px 9px;
}
QWidget#panopilotWorkspace QPushButton:hover,
QWidget#panopilotEditor QPushButton:hover,
QWidget#panopilotWorkspace QToolButton:hover,
QWidget#panopilotEditor QToolButton:hover,
QWidget#panopilotWorkspace QComboBox:hover,
QWidget#panopilotEditor QComboBox:hover {
    background: #333a44;
    border-color: #586474;
}
QWidget#panopilotWorkspace QPushButton:disabled,
QWidget#panopilotEditor QPushButton:disabled,
QWidget#panopilotWorkspace QToolButton:disabled,
QWidget#panopilotEditor QToolButton:disabled,
QWidget#panopilotWorkspace QComboBox:disabled,
QWidget#panopilotEditor QComboBox:disabled {
    color: #737c88;
    background: #22272e;
    border-color: #303640;
}
QWidget#panopilotWorkspace QComboBox QAbstractItemView,
QWidget#panopilotEditor QComboBox QAbstractItemView {
    color: #f1f3f5;
    background: #252a31;
    selection-color: #ffffff;
    selection-background-color: #31578f;
    border: 1px solid #414956;
}


QToolButton#backToProjectAction {
    color: #e7eaf0;
    background: transparent;
    border: 1px solid #414956;
    border-radius: 6px;
    padding: 3px 9px;
    font-weight: 600;
}
QToolButton#backToProjectAction:hover {
    color: #ffffff;
    background: #2a3038;
    border-color: #586474;
}

QPushButton#primaryAction {
    background: #3f7cff;
    color: #ffffff;
    border: 1px solid #6698ff;
    border-radius: 6px;
    padding: 5px 12px;
    font-weight: 650;
}
QPushButton#primaryAction:hover {
    background: #4d86ff;
}
QPushButton#primaryAction:pressed {
    background: #336eea;
}

QPushButton#quietAction,
QToolButton#quietAction {
    color: #e7eaf0;
    background: transparent;
    border: 1px solid #414956;
    border-radius: 6px;
    padding: 4px 9px;
}
QPushButton#quietAction:hover,
QToolButton#quietAction:hover {
    background: #2a3038;
}

QPushButton#modeAction {
    color: #c8ced7;
    background: #252a31;
    border: 1px solid #3a424e;
    padding: 5px 14px;
    font-weight: 600;
}
QPushButton#modeAction:checked {
    color: #ffffff;
    background: #31578f;
    border-color: #6595e8;
}

QListView#clipStrip {
    color: #f1f3f5;
    background: transparent;
    border: none;
    outline: none;
}
QListView#clipStrip::item {
    color: #f1f3f5;
    background: #262b33;
    border: 1px solid #353c47;
    border-radius: 7px;
    padding: 5px 8px;
    margin: 2px;
}
QListView#clipStrip::item:selected {
    color: #ffffff;
    background: #2d4774;
    border: 1px solid #6b9cff;
}
QListView#clipStrip::item:hover:!selected {
    background: #2c323b;
}

QFrame#reframeTools,
QFrame#trimTools {
    background: #1e2228;
    border: 1px solid #303640;
    border-radius: 7px;
}
QFrame#advancedCameraPanel {
    background: transparent;
    border: none;
}
QFrame#timelineThumbnails {
    background: #111318;
    border: 1px solid #303640;
    border-radius: 4px;
}


QWidget#panopilotWorkspace QLineEdit:focus,
QDialog#settingsDialog QLineEdit:focus {
    color: #ffffff;
    background: #2d333c;
    border-color: #6b9cff;
}


QLineEdit#projectNameEdit {
    min-height: 38px;
    font-size: 20px;
    font-weight: 650;
    padding: 7px 12px;
}

QFrame#projectHome {
    background: #171a1f;
    border: none;
}
QWidget#arrangeWorkspace {
    background: #171a1f;
}
QWidget#arrangeTrack {
    background: #111318;
}
QFrame#arrangeClipCard {
    background: #242a31;
    border: 1px solid #3a424e;
    border-radius: 7px;
}
QFrame#arrangeClipCard[selected="true"] {
    background: #293d5e;
    border: 2px solid #6b9cff;
}
QFrame#arrangeClipCard:hover {
    background: #2d333c;
}


QScrollBar:vertical {
    background: #171a1f;
    width: 13px;
    margin: 0;
}
QScrollBar::handle:vertical {
    background: #586474;
    min-height: 28px;
    border-radius: 5px;
}
QScrollBar::handle:vertical:hover {
    background: #6c7888;
}
QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical {
    height: 0;
    background: transparent;
}

QScrollBar:horizontal {
    background: #171a1f;
    height: 13px;
    margin: 0;
}
QScrollBar::handle:horizontal {
    background: #586474;
    min-width: 28px;
    border-radius: 5px;
}
QScrollBar::handle:horizontal:hover {
    background: #6c7888;
}
QScrollBar::add-line:horizontal,
QScrollBar::sub-line:horizontal {
    width: 0;
    background: transparent;
}

QProgressBar {
    color: #ffffff;
    background: #171a1f;
    border: 1px solid #414956;
    border-radius: 4px;
    text-align: center;
}
QProgressBar::chunk {
    background: #3f7cff;
    border-radius: 3px;
}

QSlider::groove:horizontal {
    height: 5px;
    background: #3b424c;
    border-radius: 2px;
}
QSlider::handle:horizontal {
    width: 14px;
    margin: -5px 0;
    background: #d8dde5;
    border: 1px solid #ffffff;
    border-radius: 7px;
}
QSlider::sub-page:horizontal {
    background: #4d83d7;
    border-radius: 2px;
}
"""


def apply_workspace_theme(widget) -> None:
    """Apply PanoPilot's scoped desktop stylesheet to a workspace root."""
    widget.setStyleSheet(WORKSPACE_STYLESHEET)
