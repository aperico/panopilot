"""
PanoPilot multi-Clip project organizer.

0.18 deliberately separates two editing scales:

Project Organizer
    ordered Clip instances: import / reorder / remove

Clip Editor
    one Clip's trim + View Path + Camera Positions

PanoPilot 0.46 turns the Iteration-2 foundation into a focus-first workspace.
The reframed output owns the main canvas; Project Clips remain immediately
available in a compact horizontal strip, while Project/export settings and
fine camera controls use progressive disclosure.  The Clip strip is backed by
a Qt model rather than duplicating Project state inside a convenience widget.
"""
from __future__ import annotations

from pathlib import Path
import json
import sys
import time

from .cache import PreviewProfile, ensure_preview_cache
from .branding import application_icon_path, render_svg_pixmap, set_application_icon, wordmark_logo_path
from .clip_strip import create_qt_clip_strip_model
from .desktop_theme import apply_workspace_theme
from .export_ui import (
    build_export_summary,
    show_export_completion_dialog,
    show_export_error_dialog,
)
from .jobs import BackgroundJobManager
from .output_profile import output_profile_for_project
from .project import load_project, project_source_statuses
from .project_export import export_project_video
from .source_validation import validate_source_recording
from .session import ProjectSession
from .source import probe_source
from .timeline import build_project_timeline
from .timeline_navigation import TimelineViewport, proportional_clip_widths
from .arrange_presenter import build_arrange_view_state
from .arrange_drag import clip_drag_pixmap
from .thumbnails import ensure_video_thumbnail, thumbnail_path_for_video
from .workspace_presenter import (
    build_workspace_view_state,
    clip_list_rows,
)


WINDOW_TITLE = "PanoPilot — Project"


def absolute_source_path(source, *, project_path=None):
    """Resolve a media reference to an absolute path for GUI sessions.

    New imports are normally absolute already. For legacy relative references,
    prefer the historical working-directory interpretation when it exists, then
    try project-relative resolution before falling back to the working directory.
    """
    value = Path(str(source)).expanduser()
    if value.is_absolute():
        return value.resolve(strict=False)
    cwd_candidate = value.resolve(strict=False)
    if cwd_candidate.exists():
        return cwd_candidate
    if project_path is not None:
        project_candidate = (Path(project_path).expanduser().parent / value).resolve(strict=False)
        if project_candidate.exists():
            return project_candidate
    return cwd_candidate


def normalize_project_source_paths(project, *, project_path=None):
    """Normalize loaded GUI-session source references without changing media identity."""
    for clip in project.clips:
        clip.source = str(absolute_source_path(clip.source, project_path=project_path))
    return project


def source_duration(source):
    probe = probe_source(source)
    value = (
        probe.get("format", {})
        .get("duration")
    )

    if value is None:
        raise RuntimeError(
            f"Could not determine duration for {source}"
        )

    return float(value)


def import_sources_into_session(
    session,
    sources,
    *,
    validate=False,
    decode_smoke=True,
):
    """Validate and import each selected Source Recording independently."""
    added = []
    skipped = []
    rejected = []

    for source in sources:
        source = str(source)

        if session.project.clips_for_source(source):
            skipped.append({"source": source, "reason": "already-in-project"})
            continue

        acceptance = (
            validate_source_recording(source, decode_smoke=decode_smoke)
            if validate
            else None
        )
        if acceptance is not None and not acceptance.accepted:
            rejected.append({
                "source": source,
                "reason": acceptance.reason,
            })
            continue

        transaction = session.add_clip(
            source,
            source_identity_value=(acceptance.identity if acceptance is not None else None),
        )
        operation = transaction.get("result") or {}
        if transaction.get("changed"):
            added.append(operation.get("clip_id"))

    return {
        "added_clip_ids": [value for value in added if value is not None],
        "skipped": skipped,
        "rejected": rejected,
        **session.state(),
    }


def run_project_editor(
    project_path,
    *,
    import_sources=None,
    view_long_edge=800,
    preview_fps=20.0,
    cache_dir=None,
    rebuild_preview=False,
    audio_enabled=True,
):
    """
    Open the multi-Clip project organizer.

    Return:
      {"action": "close"}
    or
      {"action": "edit", "clip_id": "..."}
    or
      {"action": "preview"}
    or
      {"action": "export", "output": "...mp4"}
    """
    project_path = Path(project_path).expanduser().resolve(strict=False)
    project = normalize_project_source_paths(
        load_project(project_path),
        project_path=project_path,
    )
    session = ProjectSession(
        project,
        path=project_path,
    )

    initial_import_sources = list(
        import_sources or []
    )
    initial_import = {
        "added_clip_ids": [],
        "skipped": [],
        "rejected": [],
    }

    try:
        from PySide6.QtCore import QEventLoop, QTimer, Qt, QSize, QMimeData, QPoint
        from PySide6.QtGui import QAction, QIcon, QKeySequence, QDrag, QPixmap
        from PySide6.QtWidgets import (
            QApplication,
            QAbstractItemView,
            QComboBox,
            QCheckBox,
            QFileDialog,
            QDialog,
            QDialogButtonBox,
            QFormLayout,
            QHBoxLayout,
            QLabel,
            QLineEdit,
            QLayout,
            QListView,
            QFrame,
            QGridLayout,
            QMessageBox,
            QMainWindow,
            QMenu,
            QPushButton,
            QProgressBar,
            QScrollArea,
            QSlider,
            QSizePolicy,
            QVBoxLayout,
            QWidget,
        )
    except ImportError as exc:
        raise RuntimeError(
            "PySide6 is required for the PanoPilot project editor. "
            "Reinstall PanoPilot with 'pip install -e .'."
        ) from exc

    state = {
        "action": "close",
        "clip_id": None,
        "output": None,
    }

    duration_cache = {}

    def duration_for_clip(clip):
        if clip.id in duration_cache:
            return duration_cache[clip.id]

        source_status = next(
            (item for item in project_source_statuses(session.project) if item["clip_id"] == clip.id),
            None,
        )
        if source_status is not None and source_status["status"] != "ok":
            duration_cache[clip.id] = None
            return None

        try:
            value = source_duration(
                clip.source
            )
        except Exception:
            value = None

        duration_cache[clip.id] = value
        return value

    class ArrangeTimelineWidget(QWidget):
        """Single-track Project Clip arrangement surface.

        This deliberately stays narrower than an NLE: one sequential track,
        duration-proportional cards, drag/drop reorder, and shared timeline
        zoom/pan semantics. There is no playback surface in Arrange mode.
        """
        MIME_TYPE = "application/x-panopilot-clip-id"

        class ClipCard(QFrame):
            def __init__(self, owner, row, thumbnail_path=None):
                super().__init__()
                self.owner = owner
                self.row = row
                self.clip_id = str(row.clip_id)
                self._press_pos = None
                self._thumbnail_path = thumbnail_path
                self._thumbnail_pixmap = (
                    QPixmap(str(thumbnail_path))
                    if thumbnail_path and Path(thumbnail_path).is_file()
                    else QPixmap()
                )
                self.setObjectName("arrangeClipCard")
                self.setAcceptDrops(True)
                self.setCursor(Qt.CursorShape.OpenHandCursor)
                self.setMinimumWidth(72)
                layout = QVBoxLayout(self)
                layout.setContentsMargins(6, 5, 6, 5)
                layout.setSpacing(4)
                self.header = QLabel(
                    f"{row.order:02d}  {row.source_name}  ·  {row.duration:.2f}s"
                )
                self.header.setObjectName("secondaryText")
                self.header.setWordWrap(False)
                self.header.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
                layout.addWidget(self.header)
                self.thumbnail = QLabel()
                self.thumbnail.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
                self.thumbnail.setAlignment(Qt.AlignmentFlag.AlignCenter)
                self.thumbnail.setScaledContents(False)
                self.thumbnail.setFixedHeight(56)
                self.thumbnail.setStyleSheet("background:#111318; border:1px solid #303640;")
                layout.addWidget(self.thumbnail, 0, Qt.AlignmentFlag.AlignHCenter)
                self._update_thumbnail()

            def _update_thumbnail(self):
                # Arrange uses one representative thumbnail per Clip. The image
                # stays centered and aspect-preserving regardless of Clip width.
                if self._thumbnail_pixmap.isNull():
                    self.thumbnail.clear()
                    return
                self.thumbnail.setPixmap(
                    self._thumbnail_pixmap.scaled(
                        96,
                        54,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                )

            def set_selected(self, selected):
                self.setProperty("selected", bool(selected))
                self.style().unpolish(self)
                self.style().polish(self)
                self.update()

            def mousePressEvent(self, event):
                if event.button() == Qt.MouseButton.LeftButton:
                    self._press_pos = event.position().toPoint()
                    self.owner.select_clip(self.clip_id)
                    self.setCursor(Qt.CursorShape.ClosedHandCursor)
                super().mousePressEvent(event)

            def mouseMoveEvent(self, event):
                if (
                    self._press_pos is not None
                    and event.buttons() & Qt.MouseButton.LeftButton
                    and (event.position().toPoint() - self._press_pos).manhattanLength() >= QApplication.startDragDistance()
                ):
                    mime = QMimeData()
                    mime.setData(self.owner.MIME_TYPE, self.clip_id.encode("utf-8"))
                    drag = QDrag(self)
                    drag.setMimeData(mime)
                    ghost = clip_drag_pixmap(
                        self._thumbnail_pixmap, self.row.source_name, self.row.duration
                    )
                    drag.setPixmap(ghost)
                    drag.setHotSpot(QPoint(ghost.width() // 2, 48))
                    self.setProperty("dragging", True)
                    self.style().unpolish(self)
                    self.style().polish(self)
                    self.update()
                    try:
                        drag.exec(Qt.DropAction.MoveAction)
                    finally:
                        # A successful reorder may rebuild/delete the old cards
                        # while Qt's native drag event loop is still active.
                        from shiboken6 import isValid
                        self._press_pos = None
                        if isValid(self):
                            self.setProperty("dragging", False)
                            self.setCursor(Qt.CursorShape.OpenHandCursor)
                            self.style().unpolish(self)
                            self.style().polish(self)
                            self.update()
                else:
                    super().mouseMoveEvent(event)

            def mouseReleaseEvent(self, event):
                self._press_pos = None
                self.setCursor(Qt.CursorShape.OpenHandCursor)
                super().mouseReleaseEvent(event)

            def dragEnterEvent(self, event):
                if event.mimeData().hasFormat(self.owner.MIME_TYPE):
                    event.acceptProposedAction()
                else:
                    event.ignore()

            def dragMoveEvent(self, event):
                if event.mimeData().hasFormat(self.owner.MIME_TYPE):
                    self.setProperty("dropSide", "after" if event.position().x() >= self.width() / 2 else "before")
                    self.style().unpolish(self)
                    self.style().polish(self)
                    self.update()
                    event.acceptProposedAction()
                else:
                    event.ignore()

            def _clear_drop_hint(self):
                self.setProperty("dropSide", "")
                self.style().unpolish(self)
                self.style().polish(self)
                self.update()

            def dragLeaveEvent(self, event):
                self._clear_drop_hint()
                event.accept()

            def dropEvent(self, event):
                self._clear_drop_hint()
                if not event.mimeData().hasFormat(self.owner.MIME_TYPE):
                    event.ignore()
                    return
                try:
                    source_id = bytes(event.mimeData().data(self.owner.MIME_TYPE)).decode("utf-8")
                except Exception:
                    event.ignore()
                    return
                after = float(event.position().x()) >= self.width() / 2.0
                self.owner.drop_clip(source_id, self.clip_id, after=after)
                event.acceptProposedAction()

            def resizeEvent(self, event):
                super().resizeEvent(event)
                self._update_thumbnail()

        class ScrollArea(QScrollArea):
            def __init__(self, owner):
                super().__init__()
                self.owner = owner

            def wheelEvent(self, event):
                self.owner.handle_wheel(event)

        def __init__(self, *, reorder_callback, back_callback):
            super().__init__()
            self.setObjectName("arrangeWorkspace")
            self.reorder_callback = reorder_callback
            self.back_callback = back_callback
            self.rows = []
            self.thumbnail_paths = {}
            self.selected_clip_id = None
            self.cards = []
            self._scroll_sync = False
            self.timeline_view = TimelineViewport(0.0)

            root = QVBoxLayout(self)
            root.setContentsMargins(8, 7, 8, 7)
            root.setSpacing(8)

            top = QHBoxLayout()
            top.setSpacing(6)
            self.back_button = QPushButton("← Project")
            top.addWidget(self.back_button)
            top.addStretch(1)
            root.addLayout(top)

            info = QLabel(
                "Arrange Clips · drag clips to reorder · wheel zooms · Shift+wheel pans horizontally"
            )
            info.setObjectName("secondaryText")
            root.addWidget(info)

            self.scroll = self.ScrollArea(self)
            self.scroll.setWidgetResizable(False)
            self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
            self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            self.scroll.setFrameShape(QFrame.Shape.NoFrame)
            self.content = QWidget()
            self.content.setObjectName("arrangeTrack")
            self.track_layout = QHBoxLayout(self.content)
            self.track_layout.setContentsMargins(4, 4, 4, 4)
            self.track_layout.setSpacing(4)
            self.track_layout.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            self.scroll.setWidget(self.content)
            self.scroll.setFixedHeight(100)
            root.addWidget(self.scroll, 0)

            nav = QHBoxLayout()
            nav.setSpacing(5)
            self.zoom_out_button = QPushButton("−")
            self.fit_button = QPushButton("Fit")
            self.zoom_in_button = QPushButton("+")
            for button in (self.zoom_out_button, self.fit_button, self.zoom_in_button):
                button.setFixedHeight(28)
            self.zoom_label = QLabel("1.0×")
            self.zoom_label.setObjectName("secondaryText")
            nav.addStretch(1)
            nav.addWidget(self.zoom_out_button)
            nav.addWidget(self.fit_button)
            nav.addWidget(self.zoom_in_button)
            nav.addWidget(self.zoom_label)
            root.addLayout(nav)
            root.addStretch(1)

            self.back_button.clicked.connect(self.back_callback)
            self.zoom_out_button.clicked.connect(lambda: self.zoom_steps(-1.0))
            self.zoom_in_button.clicked.connect(lambda: self.zoom_steps(+1.0))
            self.fit_button.clicked.connect(self.fit)
            self.scroll.horizontalScrollBar().valueChanged.connect(self._scrollbar_changed)

        def _clear_cards(self):
            while self.track_layout.count():
                item = self.track_layout.takeAt(0)
                widget = item.widget()
                if widget is not None:
                    widget.deleteLater()
            self.cards = []

        def set_project(self, arrange_state, *, thumbnail_paths=None, selected_clip_id=None):
            old_duration = self.timeline_view.duration
            old_snapshot = self.timeline_view.snapshot()
            self.rows = list(arrange_state.rows)
            self.thumbnail_paths = dict(thumbnail_paths or {})
            self.selected_clip_id = (
                str(selected_clip_id)
                if selected_clip_id is not None
                else (self.rows[0].clip_id if self.rows else None)
            )
            self.timeline_view = TimelineViewport(float(arrange_state.total_duration))
            if old_duration > 0.0 and abs(old_duration - self.timeline_view.duration) <= 1e-6:
                self.timeline_view.set_window(
                    old_snapshot["visible_start"],
                    old_snapshot["visible_duration"],
                )
            self._clear_cards()
            for row in self.rows:
                card = self.ClipCard(
                    self,
                    row,
                    self.thumbnail_paths.get(row.clip_id),
                )
                self.track_layout.addWidget(card)
                self.cards.append(card)
            self._update_selection()
            self._update_geometry()

        def select_clip(self, clip_id):
            self.selected_clip_id = str(clip_id)
            self._update_selection()

        def _update_selection(self):
            for card in self.cards:
                card.set_selected(card.clip_id == self.selected_clip_id)
        def drop_clip(self, source_id, target_id, *, after=False):
            ids = [row.clip_id for row in self.rows]
            if source_id not in ids or target_id not in ids or source_id == target_id:
                return
            source_index = ids.index(source_id)
            target_index = ids.index(target_id) + (1 if after else 0)
            if source_index < target_index:
                target_index -= 1
            target_index = max(0, min(target_index, len(ids) - 1))
            self.reorder_callback(source_id, target_index)
            self.selected_clip_id = source_id

        def _update_geometry(self):
            viewport_width = max(1, self.scroll.viewport().width())
            ratio = max(1.0, self.timeline_view.zoom_ratio)
            content_width = max(viewport_width, int(round(viewport_width * ratio)))
            durations = [row.duration for row in self.rows]
            widths = proportional_clip_widths(
                durations,
                total_pixel_width=max(1, content_width - 8 - max(0, len(durations) - 1) * 4),
                minimum_width=72,
            )
            actual_content_width = max(
                viewport_width,
                sum(widths) + max(0, len(widths) - 1) * 4 + 8,
            )
            track_height = 92
            self.content.setFixedSize(actual_content_width, track_height)
            for card, width in zip(self.cards, widths):
                card.setFixedWidth(int(width))
                card.setFixedHeight(84)
            self.zoom_label.setText(f"{self.timeline_view.zoom_ratio:.1f}×")
            self._sync_scrollbar_from_view()

        def _sync_scrollbar_from_view(self):
            bar = self.scroll.horizontalScrollBar()
            maximum = max(0, bar.maximum())
            denominator = max(1e-9, self.timeline_view.duration - self.timeline_view.visible_duration)
            fraction = (
                0.0
                if denominator <= 1e-9
                else self.timeline_view.visible_start / denominator
            )
            self._scroll_sync = True
            try:
                bar.setValue(int(round(maximum * max(0.0, min(1.0, fraction)))))
            finally:
                self._scroll_sync = False

        def _scrollbar_changed(self, value):
            if self._scroll_sync or self.timeline_view.is_fitted:
                return
            bar = self.scroll.horizontalScrollBar()
            maximum = max(1, bar.maximum())
            fraction = max(0.0, min(1.0, float(value) / float(maximum)))
            available = max(0.0, self.timeline_view.duration - self.timeline_view.visible_duration)
            self.timeline_view.visible_start = fraction * available

        def zoom_steps(self, steps, *, anchor_time=None):
            if anchor_time is None:
                anchor_time = (
                    self.timeline_view.visible_start
                    + self.timeline_view.visible_duration / 2.0
                )
            self.timeline_view.zoom_steps(float(steps), anchor_time=anchor_time)
            self._update_geometry()

        def fit(self):
            self.timeline_view.fit()
            self._update_geometry()

        def handle_wheel(self, event):
            delta = event.angleDelta()
            pixel = event.pixelDelta()
            shift = bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier)
            if shift or abs(pixel.x()) > abs(pixel.y()):
                amount = (
                    -float(pixel.x())
                    if not pixel.isNull() and pixel.x()
                    else -float(delta.y()) / 120.0 * 0.18 * self.timeline_view.visible_duration
                )
                if pixel.isNull() or not pixel.x():
                    self.timeline_view.pan_seconds(amount)
                else:
                    self.timeline_view.pan_seconds(
                        amount / max(1.0, self.scroll.viewport().width()) * self.timeline_view.visible_duration
                    )
                self._sync_scrollbar_from_view()
                event.accept()
                return
            steps = float(delta.y()) / 120.0 if delta.y() else float(pixel.y()) / 30.0
            if steps:
                x = float(event.position().x())
                fraction = max(0.0, min(1.0, x / max(1.0, float(self.scroll.viewport().width()))))
                anchor = self.timeline_view.time_for_fraction(fraction)
                self.zoom_steps(steps, anchor_time=anchor)
            event.accept()

        def resizeEvent(self, event):
            super().resizeEvent(event)
            QTimer.singleShot(0, self._update_geometry)

    class ProjectWidget(QMainWindow):
        def __init__(self):
            super().__init__()

            self.setWindowTitle(
                WINDOW_TITLE
            )
            set_application_icon(QApplication.instance())
            self.setWindowIcon(QIcon(str(application_icon_path())))
            # Initial geometry is only a fallback; the main Project workspace
            # opens maximized by default and remains fully resizable.
            self.resize(1180, 720)
            self.setMinimumSize(720, 480)
            self.clip_editor_active = False
            self.workspace_mode = "home"
            self.pending_workspace_mode = None
            self.pending_clip_edit = None
            self.arrange_widget = None

            self.background_jobs = BackgroundJobManager(
                max_workers=2
            )
            self.preview_job_keys = {}
            self.import_job_sources = {}
            self.handled_import_jobs = set()
            self.export_job_key = None
            self.handled_export_jobs = set()
            self.last_preview_states = {}

            self.setObjectName("panopilotWorkspace")
            apply_workspace_theme(self)

            # Project/export controls live in a modeless Settings dialog rather
            # than consuming permanent workspace height. The Project name is
            # persisted metadata and can also be edited directly on the Home
            # screen.
            self.settings_name_edit = QLineEdit()
            self.settings_name_edit.setMaxLength(120)
            self.settings_name_edit.setToolTip("Human-readable Project name stored in the project file.")
            self.aspect_combo = QComboBox()
            self.aspect_combo.addItem("Landscape 16:9", "16:9")
            self.aspect_combo.addItem("Vertical 9:16", "9:16")
            self.resolution_combo = QComboBox()
            self.resolution_combo.addItem("720p HD", "720p")
            self.resolution_combo.addItem("1080p Full HD", "1080p")
            self.resolution_combo.addItem("1440p QHD", "1440p")
            self.resolution_combo.addItem("2160p 4K UHD", "2160p")
            self.resolution_combo.setToolTip(
                "Larger frames take longer to export and create larger files. "
                "Available detail depends on the recording and how far you zoom in."
            )
            self.fps_combo = QComboBox()
            self.fps_combo.addItem("Auto (60 fps recommended)", "auto")
            self.fps_combo.addItem("24 fps", "24")
            self.fps_combo.addItem("25 fps", "25")
            self.fps_combo.addItem("30 fps", "30")
            self.fps_combo.addItem("50 fps", "50")
            self.fps_combo.addItem("60 fps", "60")
            self.fps_combo.setToolTip(
                "Final video frame rate. Auto is recommended and selects "
                "the highest broadly device-friendly rate up to 60 fps."
            )
            self.quality_combo = QComboBox()
            self.quality_combo.addItem("Standard", "standard")
            self.quality_combo.addItem("High (recommended)", "high")
            self.quality_combo.addItem("Very High", "very-high")
            self.quality_combo.addItem("Master (largest file)", "master")
            self.quality_combo.setToolTip(
                "High balances detail and file size. Very High and Master create larger "
                "files with less compression. Master is still a lossy video format."
            )

            self.stabilization_slider = QSlider(Qt.Orientation.Horizontal)
            self.stabilization_slider.setRange(0, 100)
            self.stabilization_slider.setMinimumWidth(260)
            self.stabilization_slider.setToolTip(
                "High-rate adaptive gyro stabilization. 0% = horizon leveling "
                "only; 70% = strong gimbal-like shake suppression; "
                "100% = maximum stabilization with adaptive follow during fast turns."
            )
            self.stabilization_value = QLabel()
            self.stabilization_value.setMinimumWidth(48)
            self.stabilization_value.setAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )

            self.settings_dialog = QDialog(self)
            self.settings_dialog.setWindowTitle("PanoPilot — Project Settings")
            self.settings_dialog.setModal(False)
            self.settings_dialog.setMinimumWidth(460)
            self.settings_dialog.setObjectName("settingsDialog")
            settings_form = QFormLayout(self.settings_dialog)
            settings_form.setContentsMargins(16, 14, 16, 14)
            settings_form.setSpacing(10)
            settings_form.addRow("Project name", self.settings_name_edit)
            settings_form.addRow("Output frame", self.aspect_combo)
            settings_form.addRow("Output size", self.resolution_combo)
            settings_form.addRow("Frame rate", self.fps_combo)
            settings_form.addRow("Export quality", self.quality_combo)
            stabilization_row = QWidget()
            stabilization_layout = QHBoxLayout(stabilization_row)
            stabilization_layout.setContentsMargins(0, 0, 0, 0)
            stabilization_layout.setSpacing(8)
            stabilization_layout.addWidget(self.stabilization_slider, 1)
            stabilization_layout.addWidget(self.stabilization_value)
            settings_form.addRow("Stabilization", stabilization_row)
            settings_buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
            settings_buttons.rejected.connect(self.settings_dialog.close)
            settings_form.addRow(settings_buttons)

            # Fixed bottom status / information bar. Project metadata and all
            # background-work reporting live here instead of above the viewer.
            self.context_status = QLabel("Ready")
            self.context_status.setObjectName("statusContext")
            self.project_info = QLabel()
            self.project_info.setObjectName("workspaceSummary")
            self.project_info.setMinimumWidth(0)
            self.project_info.setSizePolicy(
                QSizePolicy.Policy.Ignored,
                QSizePolicy.Policy.Preferred,
            )
            self.work_status = QLabel("Idle")
            self.work_status.setObjectName("secondaryText")
            self.work_status.setWordWrap(False)
            self.work_status.setMinimumWidth(0)
            self.work_status.setMaximumWidth(170)
            self.work_status.setSizePolicy(
                QSizePolicy.Policy.Ignored,
                QSizePolicy.Policy.Preferred,
            )
            self.export_progress = QProgressBar()
            self.export_progress.setRange(0, 1000)
            self.export_progress.setValue(0)
            self.export_progress.setFixedWidth(104)
            self.export_progress.setMaximumHeight(18)
            self.export_progress.setVisible(False)
            self.abort_export_button = QPushButton("Abort")
            self.abort_export_button.setObjectName("statusAction")
            self.abort_export_button.setFixedWidth(64)
            self.abort_export_button.setVisible(False)
            self.abort_export_button.clicked.connect(self._abort_export)

            status_bar = self.statusBar()
            status_bar.setObjectName("workspaceStatusBar")
            # The native window frame already provides resize affordances. Avoid
            # consuming the right edge of the status bar with an extra size grip.
            status_bar.setSizeGripEnabled(False)
            # Context/project text is intentionally shrinkable. Export progress and
            # Abort are permanent compact controls, so they remain fully visible
            # even when the window is narrow.
            status_bar.addWidget(self.context_status, 1)
            status_bar.addWidget(self.project_info, 2)
            status_bar.addPermanentWidget(self.work_status)
            status_bar.addPermanentWidget(self.export_progress)
            status_bar.addPermanentWidget(self.abort_export_button)

            # Project Home Clip browser. Clips live at the bottom of the Home
            # workspace, wrap into rows, and scroll vertically as the project grows.
            self.clip_model = create_qt_clip_strip_model(parent=self)
            self.list = QListView()
            self.list.setObjectName("clipStrip")
            self.list.setModel(self.clip_model)
            self.list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
            self.list.setViewMode(QListView.ViewMode.IconMode)
            self.list.setFlow(QListView.Flow.LeftToRight)
            self.list.setWrapping(True)
            self.list.setResizeMode(QListView.ResizeMode.Adjust)
            self.list.setMovement(QListView.Movement.Static)
            self.list.setUniformItemSizes(True)
            self.list.setIconSize(QSize(128, 72))
            self.list.setGridSize(QSize(210, 118))
            self.list.setMinimumHeight(118)
            self.list.setMaximumHeight(180)
            self.list.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
            self.list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            self.list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            self.list.doubleClicked.connect(self._edit_clip_index)
            self.list.customContextMenuRequested.connect(self._show_clip_context_menu)
            self.list.selectionModel().selectionChanged.connect(
                lambda *_args: self._update_clip_menu_visibility()
            )

            # Classic desktop command surface. Persistent commands belong in
            # menus; the central workspace is reserved for media and context.
            self.open_project_action = QAction("&Open Project…", self)
            self.open_project_action.setShortcut(QKeySequence.StandardKey.Open)
            self.add_action = QAction("&Add Clips…", self)
            self.add_action.setShortcut(QKeySequence("Ctrl+I"))
            self.save_action = QAction("&Save Project", self)
            self.save_action.setShortcut(QKeySequence.StandardKey.Save)
            self.save_as_action = QAction("Save Project &As…", self)
            self.save_as_action.setShortcut(QKeySequence("Ctrl+Shift+S"))
            self.export_action = QAction("Export &Final Video…", self)
            self.export_action.setShortcut(QKeySequence("Ctrl+E"))
            self.close_clip_action = QAction("Close Clip Editor", self)
            self.close_clip_action.setEnabled(False)
            self.close_project_action = QAction("&Close Project", self)
            self.close_project_action.setShortcut(QKeySequence.StandardKey.Close)

            self.undo_action = QAction("&Undo", self)
            self.undo_action.setShortcut(QKeySequence.StandardKey.Undo)
            self.redo_action = QAction("&Redo", self)
            self.redo_action.setShortcut(QKeySequence.StandardKey.Redo)

            self.edit_action = QAction("&Edit Selected Clip", self)
            self.edit_action.setShortcut(QKeySequence("Return"))
            self.arrange_action = QAction("&Arrange Clips", self)
            self.arrange_action.setShortcut(QKeySequence("Ctrl+Shift+A"))
            self.remove_action = QAction("&Remove Selected Clip", self)
            self.remove_action.setShortcut(QKeySequence(Qt.Key.Key_Delete))
            self.move_earlier_action = QAction("Move Earlier", self)
            self.move_earlier_action.setShortcut(QKeySequence("Alt+Left"))
            self.move_later_action = QAction("Move Later", self)
            self.move_later_action.setShortcut(QKeySequence("Alt+Right"))

            self.preview_action = QAction("&Preview Project", self)
            self.focus_action = QAction("&Focus Viewer", self)
            self.focus_action.setCheckable(True)
            self.focus_action.setShortcut(QKeySequence("F11"))
            self.show_clips_action = QAction("Show &Clip Browser", self)
            self.show_clips_action.setCheckable(True)
            self.show_clips_action.setChecked(True)
            self.settings_action = QAction("&Project Settings…", self)
            self.settings_action.setShortcut(QKeySequence("Ctrl+,"))

            file_menu = self.menuBar().addMenu("&File")
            file_menu.addAction(self.open_project_action)
            file_menu.addAction(self.add_action)
            file_menu.addSeparator()
            file_menu.addAction(self.save_action)
            file_menu.addAction(self.save_as_action)
            file_menu.addSeparator()
            file_menu.addAction(self.export_action)
            file_menu.addSeparator()
            file_menu.addAction(self.close_clip_action)
            file_menu.addAction(self.close_project_action)

            edit_menu = self.menuBar().addMenu("&Edit")
            edit_menu.addAction(self.undo_action)
            edit_menu.addAction(self.redo_action)

            clip_menu = self.menuBar().addMenu("&Clip")
            clip_menu.addAction(self.edit_action)
            clip_menu.addAction(self.arrange_action)
            self.clip_selection_separator = clip_menu.addSeparator()
            clip_menu.addAction(self.remove_action)
            clip_menu.addAction(self.move_earlier_action)
            clip_menu.addAction(self.move_later_action)

            view_menu = self.menuBar().addMenu("&View")
            view_menu.addAction(self.preview_action)
            view_menu.addSeparator()
            view_menu.addAction(self.focus_action)
            view_menu.addAction(self.show_clips_action)

            settings_menu = self.menuBar().addMenu("&Settings")
            settings_menu.addAction(self.settings_action)

            export_menu = self.menuBar().addMenu("E&xport")
            export_menu.addAction(self.export_action)

            self.open_project_action.triggered.connect(self._open_project)
            self.add_action.triggered.connect(self._add_files)
            self.save_action.triggered.connect(self._save)
            self.save_as_action.triggered.connect(self._save_as)
            self.export_action.triggered.connect(self._export_project)
            self.close_clip_action.triggered.connect(self._close_active_editor)
            self.close_project_action.triggered.connect(self.close)
            self.undo_action.triggered.connect(self._undo)
            self.redo_action.triggered.connect(self._redo)
            self.edit_action.triggered.connect(lambda _checked=False: self._edit_selected())
            self.arrange_action.triggered.connect(lambda _checked=False: self._show_arrange_mode())
            self.remove_action.triggered.connect(self._remove_selected)
            self.move_earlier_action.triggered.connect(lambda: self._move_selected(-1))
            self.move_later_action.triggered.connect(lambda: self._move_selected(+1))
            self.preview_action.triggered.connect(self._preview_project)
            self.focus_action.toggled.connect(self._focus_toggled)
            self.show_clips_action.toggled.connect(self._show_clips_toggled)
            self.settings_action.triggered.connect(self._show_project_settings)

            self.settings_name_edit.editingFinished.connect(
                lambda: self._commit_project_name(self.settings_name_edit.text())
            )
            self.aspect_combo.currentIndexChanged.connect(self._aspect_changed)
            self.resolution_combo.currentIndexChanged.connect(self._resolution_changed)
            self.fps_combo.currentIndexChanged.connect(self._fps_changed)
            self.quality_combo.currentIndexChanged.connect(self._quality_changed)
            self.stabilization_slider.valueChanged.connect(self._stabilization_preview)
            self.stabilization_slider.sliderReleased.connect(self._stabilization_committed)

            self.editor_host = QWidget()
            self.editor_host.setObjectName("editorHost")
            self.editor_host.setSizePolicy(
                QSizePolicy.Policy.Expanding,
                QSizePolicy.Policy.Expanding,
            )
            self.editor_host_layout = QVBoxLayout(self.editor_host)
            self.editor_host_layout.setContentsMargins(0, 0, 0, 0)

            # Home explains the next step and keeps clip editing discoverable.
            # Shared actions preserve the same behavior as menus and shortcuts.
            self.home_panel = QFrame()
            self.home_panel.setObjectName("projectHome")
            home_layout = QVBoxLayout(self.home_panel)
            home_layout.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)
            home_layout.setContentsMargins(22, 14, 22, 12)
            home_layout.setSpacing(10)
            home_layout.addStretch(1)

            self.home_logo_label = QLabel()
            self.home_logo_label.setObjectName("brandWordmark")
            self.home_logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.home_logo_label.setToolTip("PanoPilot")
            self.home_logo_label.setPixmap(
                render_svg_pixmap(wordmark_logo_path(), width=180, height=50)
            )
            self.home_logo_label.setFixedSize(190, 54)
            self.home_logo_label.setScaledContents(False)
            logo_row = QHBoxLayout()
            logo_row.addStretch(1)
            logo_row.addWidget(self.home_logo_label, 0)
            logo_row.addStretch(1)
            home_layout.addLayout(logo_row)

            self.home_name_edit = QLineEdit()
            self.home_name_edit.setObjectName("projectNameEdit")
            self.home_name_edit.setMaxLength(120)
            self.home_name_edit.setAccessibleName("Project name")
            self.home_name_edit.setMinimumWidth(0)
            self.home_name_edit.setMaximumWidth(760)
            self.home_name_edit.setMinimumHeight(42)
            self.home_name_edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.home_name_edit.setToolTip("Edit the Project name stored in this project file.")
            self.home_name_edit.editingFinished.connect(
                lambda: self._commit_project_name(self.home_name_edit.text())
            )
            name_row = QHBoxLayout()
            name_row.addStretch(1)
            name_row.addWidget(self.home_name_edit, 1)
            name_row.addStretch(1)
            home_layout.addLayout(name_row)

            self.home_path_label = QLabel()
            self.home_path_label.setTextFormat(Qt.TextFormat.PlainText)
            self.home_path_label.setObjectName("secondaryText")
            self.home_path_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.home_path_label.setWordWrap(True)
            home_layout.addWidget(self.home_path_label)
            self.home_summary_label = QLabel()
            self.home_summary_label.setObjectName("workspaceSummary")
            self.home_summary_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.home_summary_label.setWordWrap(True)
            home_layout.addWidget(self.home_summary_label)

            self.home_heading = QLabel()
            self.home_heading.setTextFormat(Qt.TextFormat.PlainText)
            self.home_heading.setObjectName("workspaceTitle")
            self.home_heading.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.home_heading.setWordWrap(True)
            home_layout.addWidget(self.home_heading)
            self.home_hint = QLabel()
            self.home_hint.setObjectName("secondaryText")
            self.home_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.home_hint.setWordWrap(True)
            home_layout.addWidget(self.home_hint)

            self.home_start_button = QPushButton("Add your first clips…")
            self.home_start_button.setObjectName("primaryAction")
            self.home_start_button.clicked.connect(self._add_files)
            home_layout.addWidget(self.home_start_button, 0, Qt.AlignmentFlag.AlignHCenter)

            self.home_workflow = QWidget()
            self.home_workflow.setMaximumWidth(580)
            home_actions = QGridLayout(self.home_workflow)
            home_actions.setContentsMargins(0, 4, 0, 4)
            home_actions.setSpacing(8)
            self.home_edit_button = QPushButton("Edit Selected Clip")
            self.home_edit_button.setObjectName("primaryAction")
            self.home_edit_button.clicked.connect(lambda: self.edit_action.trigger())
            self.home_arrange_button = QPushButton("Arrange Clips")
            self.home_arrange_button.setToolTip("Choose the order of clips in your final video")
            self.home_export_button = QPushButton("Export Final Video…")
            self.home_preview_button = QPushButton("Preview Project")
            self.home_preview_button.setToolTip("Watch your clips in order before exporting")
            self.home_arrange_button.clicked.connect(lambda _checked=False: self._show_arrange_mode())
            self.home_export_button.clicked.connect(self._export_project)
            self.home_preview_button.clicked.connect(lambda: self.preview_action.trigger())
            home_actions.addWidget(self.home_edit_button, 0, 0)
            home_actions.addWidget(self.home_arrange_button, 0, 1)
            home_actions.addWidget(self.home_preview_button, 1, 0)
            home_actions.addWidget(self.home_export_button, 1, 1)
            home_actions.setColumnStretch(0, 1)
            home_actions.setColumnStretch(1, 1)
            workflow_row = QHBoxLayout()
            workflow_row.addStretch(1)
            workflow_row.addWidget(self.home_workflow, 1)
            workflow_row.addStretch(1)
            home_layout.addLayout(workflow_row)

            utilities = QHBoxLayout()
            utilities.addStretch(1)
            self.home_open_button = QPushButton("Open Project…")
            self.home_settings_button = QPushButton("Project Settings…")
            for button in (self.home_open_button, self.home_settings_button):
                button.setObjectName("quietAction")
                utilities.addWidget(button)
            self.home_open_button.clicked.connect(self._open_project)
            self.home_settings_button.clicked.connect(self._show_project_settings)
            utilities.addStretch(1)
            home_layout.addLayout(utilities)
            home_layout.addStretch(1)
            self.home_scroll = QScrollArea()
            self.home_scroll.setObjectName("homeScroll")
            self.home_scroll.setWidgetResizable(True)
            self.home_scroll.setFrameShape(QFrame.Shape.NoFrame)
            self.home_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            self.home_scroll.setWidget(self.home_panel)
            self.editor_placeholder = self.home_scroll
            self.editor_host_layout.addWidget(self.home_scroll, 1)

            self.clip_strip_frame = QFrame()
            self.clip_strip_frame.setObjectName("clipStripFrame")
            clip_strip_layout = QVBoxLayout(self.clip_strip_frame)
            clip_strip_layout.setContentsMargins(10, 7, 10, 8)
            clip_strip_layout.setSpacing(6)
            clip_header = QHBoxLayout()
            clips_label = QLabel("Clips")
            clips_label.setObjectName("workspaceTitle")
            clip_header.addWidget(clips_label)
            clip_header.addStretch(1)
            self.home_add_clips_button = QPushButton("+ Add Clips…")
            self.home_add_clips_button.setToolTip("Add one or more DJI Osmo 360 recordings")
            self.home_add_clips_button.clicked.connect(self._add_files)
            clip_header.addWidget(self.home_add_clips_button)
            clip_strip_layout.addLayout(clip_header)
            clip_strip_layout.addWidget(self.list)

            central = QWidget()
            central.setObjectName("workspaceCentral")
            self.setCentralWidget(central)
            layout = QVBoxLayout(central)
            layout.setContentsMargins(6, 6, 6, 4)
            layout.setSpacing(6)
            layout.addWidget(self.editor_host, 1)
            # Clip browser belongs at the bottom of Project Home.
            layout.addWidget(self.clip_strip_frame, 0)


            self._refresh()
            self._schedule_preview_jobs()

            self.background_timer = QTimer(
                self
            )
            self.background_timer.setInterval(
                150
            )
            self.background_timer.timeout.connect(
                self._poll_background_jobs
            )
            self.background_timer.start()

            if initial_import_sources:
                existing = {
                    str(
                        Path(clip.source).expanduser().resolve(
                            strict=False
                        )
                    )
                    for clip in session.project.clips
                }
                for source in initial_import_sources:
                    resolved = str(
                        Path(source).expanduser().resolve(
                            strict=False
                        )
                    )
                    if resolved in existing:
                        initial_import["skipped"].append(
                            {
                                "source": str(source),
                                "reason": "already-in-project",
                            }
                        )
                    else:
                        self._queue_import_validation(
                            absolute_source_path(source, project_path=project_path)
                        )

            if initial_import.get("rejected"):
                details = "\n".join(
                    f"• {Path(item['source']).name}: {item['reason']}"
                    for item in initial_import["rejected"]
                )
                QMessageBox.warning(
                    self,
                    "PanoPilot — Unsupported sources",
                    "Some selected recordings could not be accepted:\n\n" + details,
                )

            if (
                initial_import["skipped"]
            ):
                names = ", ".join(
                    Path(item["source"]).name
                    for item
                    in initial_import["skipped"]
                )
                QMessageBox.information(
                    self,
                    "PanoPilot — Duplicate sources skipped",
                    (
                        "These sources were already present and were not "
                        f"duplicated:\n{names}\n\n"
                        "Repeated instances of the same source are not "
                        "part of Iteration 1."
                    ),
                )

        def _preview_profile(self):
            return PreviewProfile(
                width=1280,
                height=640,
                fps=20.0,
                with_audio=True,
                stabilization_amount=float(
                    session.project.stabilization_amount
                ),
            )

        def _preview_job_key(self, clip):
            profile = self._preview_profile()
            return (
                f"preview:{clip.id}:"
                f"{profile.stabilization_amount:.4f}:"
                f"{profile.width}x{profile.height}@{profile.fps:.3f}"
            )

        def _schedule_preview_job(self, clip, *, replace=False):
            statuses = {
                item["clip_id"]: item
                for item in project_source_statuses(
                    session.project
                )
            }
            source_status = statuses.get(
                clip.id,
                {},
            ).get("status")
            if source_status not in (
                "ok",
                "unverified",
            ):
                return None

            key = self._preview_job_key(
                clip
            )
            self.preview_job_keys[
                clip.id
            ] = key
            profile = self._preview_profile()

            def task(context):
                def progress(event):
                    context.progress(
                        event
                    )

                entry = ensure_preview_cache(
                    clip.source,
                    profile=profile,
                    progress_callback=progress,
                    cancel_callback=(
                        lambda: context.cancelled
                    ),
                )
                if not context.cancelled:
                    ensure_video_thumbnail(
                        entry.video_path,
                        width=160,
                        height=90,
                    )
                return entry

            return self.background_jobs.submit(
                key,
                f"Preview — {Path(clip.source).name}",
                task,
                replace=replace,
            )

        def _schedule_preview_jobs(self, *, replace=False):
            for clip in session.project.clips:
                self._schedule_preview_job(
                    clip,
                    replace=replace,
                )

        def _restart_preview_jobs(self):
            self.background_jobs.cancel_all(
                prefix="preview:"
            )
            self.preview_job_keys.clear()
            self._schedule_preview_jobs(
                replace=True
            )

        def _preview_snapshot(self, clip_id):
            key = self.preview_job_keys.get(
                str(clip_id)
            )
            if key is None:
                return None
            return self.background_jobs.snapshot(
                key
            )

        def _preview_ready(self, clip_id):
            snapshot = self._preview_snapshot(
                clip_id
            )
            return bool(
                snapshot is not None
                and snapshot.state
                == "succeeded"
            )

        def _queue_import_validation(self, source):
            source = str(absolute_source_path(source, project_path=project_path))
            key = (
                "import:"
                + str(
                    Path(source).expanduser().resolve(
                        strict=False
                    )
                )
            )
            self.import_job_sources[
                key
            ] = source

            def task(context):
                context.progress(
                    {
                        "stage": "validate-source",
                        "message": (
                            "Validating "
                            + Path(source).name
                        ),
                    }
                )
                return validate_source_recording(
                    source,
                    decode_smoke=True,
                )

            self.background_jobs.submit(
                key,
                f"Validate — {Path(source).name}",
                task,
                replace=True,
            )

        def _poll_background_jobs(self):
            snapshots = (
                self.background_jobs.snapshots()
            )

            # Import acceptance is applied on the GUI thread only.
            imported_clip_ids = []
            rejected = []
            for key, source in list(
                self.import_job_sources.items()
            ):
                snapshot = snapshots.get(
                    key
                )
                if (
                    snapshot is None
                    or not snapshot.terminal
                    or key
                    in self.handled_import_jobs
                ):
                    continue

                self.handled_import_jobs.add(
                    key
                )
                if snapshot.state == "succeeded":
                    acceptance = snapshot.result
                    if acceptance.accepted:
                        transaction = session.add_clip(
                            source,
                            source_identity_value=(
                                acceptance.identity
                            ),
                        )
                        operation = (
                            transaction.get("result")
                            or {}
                        )
                        if transaction.get(
                            "changed"
                        ):
                            clip_id = operation.get(
                                "clip_id"
                            )
                            if clip_id:
                                imported_clip_ids.append(
                                    clip_id
                                )
                                clip = session.project.clip_for_id(
                                    clip_id
                                )
                                if clip is not None:
                                    self._schedule_preview_job(
                                        clip
                                    )
                    else:
                        rejected.append(
                            f"{Path(source).name}: {acceptance.reason}"
                        )
                elif snapshot.state == "failed":
                    rejected.append(
                        f"{Path(source).name}: {snapshot.message}"
                    )

            if imported_clip_ids:
                self._refresh(
                    imported_clip_ids[-1]
                )
            if rejected:
                QMessageBox.warning(
                    self,
                    "PanoPilot — Unsupported sources",
                    "Some recordings could not be accepted:\n\n"
                    + "\n".join(
                        "• " + value
                        for value in rejected
                    ),
                )

            current_preview_keys = set(
                self.preview_job_keys.values()
            )
            active_preview = [
                snapshot
                for key, snapshot in snapshots.items()
                if key in current_preview_keys
                and snapshot.active
            ]
            failed_preview = [
                snapshot
                for key, snapshot in snapshots.items()
                if key in current_preview_keys
                and snapshot.state == "failed"
            ]
            active_import = [
                snapshot
                for key, snapshot in snapshots.items()
                if key.startswith("import:")
                and snapshot.active
            ]

            export_snapshot = (
                snapshots.get(
                    self.export_job_key
                )
                if self.export_job_key
                else None
            )

            if (
                export_snapshot is not None
                and export_snapshot.active
            ):
                event = (
                    export_snapshot.progress_event
                    or {}
                )
                percent = event.get(
                    "percent"
                )
                if percent is not None:
                    self.export_progress.setValue(
                        int(
                            max(
                                0,
                                min(
                                    1000,
                                    round(
                                        float(percent)
                                        * 10.0
                                    ),
                                ),
                            )
                        )
                    )
                self.export_progress.setVisible(
                    True
                )
                self.abort_export_button.setVisible(
                    True
                )
                self.work_status.setText("Exporting…")
                self.work_status.setToolTip(
                    "Export running from the saved Project snapshot — "
                    + export_snapshot.message
                    + ". You may continue editing; new edits apply to the next export."
                )
                self.export_action.setEnabled(
                    False
                )
            else:
                self.export_progress.setVisible(
                    False
                )
                self.abort_export_button.setVisible(
                    False
                )

                if active_import:
                    self.work_status.setText("Validating media…")
                    self.work_status.setToolTip(
                        active_import[0].message + " — editing remains available."
                    )
                elif active_preview:
                    self.work_status.setText(
                        f"Preparing {len(active_preview)} preview(s)…"
                    )
                    self.work_status.setToolTip(
                        "Ready Clips remain usable while previews are prepared."
                    )
                elif failed_preview:
                    self.work_status.setText(
                        f"{len(failed_preview)} preview failure(s)"
                    )
                    self.work_status.setToolTip(
                        "Other ready Clips remain available."
                    )
                else:
                    self.work_status.setText("Idle")
                    self.work_status.setToolTip("")

                self.export_action.setEnabled(
                    bool(session.project.clips)
                    and not self.clip_editor_active
                )

            if (
                export_snapshot is not None
                and export_snapshot.terminal
                and self.export_job_key
                not in self.handled_export_jobs
            ):
                self.handled_export_jobs.add(
                    self.export_job_key
                )
                self.export_progress.setVisible(
                    False
                )
                self.abort_export_button.setVisible(
                    False
                )
                self.export_action.setEnabled(
                    bool(session.project.clips)
                    and not self.clip_editor_active
                )

                if export_snapshot.state == "succeeded":
                    show_export_completion_dialog(
                        export_snapshot.result
                    )
                elif export_snapshot.state == "failed":
                    show_export_error_dialog(
                        export_snapshot.error,
                        output=(
                            export_snapshot.progress_event.get(
                                "output",
                                "",
                            )
                        ),
                    )
                elif export_snapshot.state == "cancelled":
                    QMessageBox.information(
                        self,
                        "PanoPilot — Export aborted",
                        "Export was aborted safely. No partial final MP4 was kept.",
                    )

                self.work_status.setText("Idle")
                self.work_status.setToolTip("")

            preview_states = {
                clip.id: (
                    self._preview_snapshot(clip.id).state
                    if self._preview_snapshot(clip.id) is not None
                    else None
                )
                for clip in session.project.clips
            }
            if preview_states != self.last_preview_states:
                self.last_preview_states = preview_states
                self._refresh(
                    self._selected_clip_id()
                )

            if self.pending_clip_edit is not None and not self.clip_editor_active:
                pending_clip_id, pending_mode = self.pending_clip_edit
                pending_snapshot = self._preview_snapshot(pending_clip_id)
                if pending_snapshot is not None and pending_snapshot.state == "succeeded":
                    self.pending_clip_edit = None
                    QTimer.singleShot(
                        0,
                        lambda clip_id=pending_clip_id, mode=pending_mode: self._edit_selected(
                            initial_mode=mode, explicit_clip_id=clip_id
                        ),
                    )
                elif pending_snapshot is not None and pending_snapshot.state == "failed":
                    self.pending_clip_edit = None
                    QMessageBox.warning(
                        self,
                        "PanoPilot — Clip Editor unavailable",
                        (
                            "The selected Clip preview could not be prepared.\n\n"
                            + pending_snapshot.message
                        ),
                    )

        def _abort_export(self):
            if self.export_job_key is None:
                return
            self.background_jobs.cancel(
                self.export_job_key
            )

        def _selected_clip_id(self):
            selection_model = self.list.selectionModel()
            if selection_model is None:
                return None
            indexes = selection_model.selectedIndexes()
            if not indexes:
                return None
            return self.clip_model.clip_id_for_index(indexes[0])

        def _update_clip_menu_visibility(self):
            """Hide selection-only Clip commands when no Clip is selected."""
            has_selection = self._selected_clip_id() is not None
            selection_actions_visible = (
                has_selection
                and not self.clip_editor_active
                and self.workspace_mode == "home"
            )
            for action in (
                self.edit_action,
                self.remove_action,
                self.move_earlier_action,
                self.move_later_action,
            ):
                action.setVisible(selection_actions_visible)
            self.clip_selection_separator.setVisible(selection_actions_visible)
            self.edit_action.setEnabled(selection_actions_visible)
            self.remove_action.setEnabled(selection_actions_visible)
            clip_ids = [clip.id for clip in session.project.clips]
            index = clip_ids.index(self._selected_clip_id()) if has_selection else -1
            self.move_earlier_action.setEnabled(selection_actions_visible and index > 0)
            self.move_later_action.setEnabled(selection_actions_visible and index < len(clip_ids) - 1)
            self._update_home_guidance()

        def _update_home_guidance(self):
            has_clips = bool(session.project.clips)
            self.home_logo_label.setVisible(not has_clips)
            self.home_path_label.setVisible(not has_clips)
            selected = session.project.clip_for_id(self._selected_clip_id())
            self.home_start_button.setVisible(not has_clips)
            self.home_workflow.setVisible(has_clips)
            self.home_edit_button.setEnabled(self.edit_action.isEnabled())
            if not has_clips:
                self.home_heading.setText("Start with your 360° recordings")
                self.home_hint.setText("Add clips, choose your views, then arrange and export your video.")
            elif selected is None:
                self.home_heading.setText("Choose a clip to edit")
                self.home_hint.setText("Select a clip below to reframe it or trim its start and end.")
            else:
                name = Path(selected.source).name
                self.home_heading.setText(self.home_heading.fontMetrics().elidedText(
                    f"Edit {name}", Qt.TextElideMode.ElideMiddle, 500
                ))
                self.home_heading.setToolTip(name)
                snapshot = self._preview_snapshot(selected.id)
                source_status = next(
                    (item for item in project_source_statuses(session.project)
                     if item["clip_id"] == selected.id), {}
                )
                if source_status.get("status") not in ("ok", "unverified"):
                    hint = "Recording unavailable. Right-click the clip and choose View Clip Info for details."
                    self.edit_action.setEnabled(False)
                    self.home_edit_button.setEnabled(False)
                elif snapshot is not None and snapshot.state == "failed":
                    hint = "Preview preparation failed. Choose Edit Selected Clip to retry."
                elif snapshot is not None and snapshot.state in ("queued", "running"):
                    hint = "Preparing the preview. Choose Edit Selected Clip to open it when ready."
                else:
                    hint = "Reframe and trim this clip. Then arrange your clips and preview the project."
                self.home_hint.setText(hint)
            self.home_edit_button.setToolTip(
                f"Reframe and trim {Path(selected.source).name}" if selected else "Select a clip below"
            )

        def _edit_clip_index(self, index):
            """Open the exact Clip that was double-clicked.

            Do not rely on QListView.currentIndex() having updated before the
            doubleClicked signal is delivered.
            """
            clip_id = self.clip_model.clip_id_for_index(index)
            if clip_id is None:
                return
            self._select_clip_id(clip_id)
            self._edit_selected(explicit_clip_id=clip_id)

        def _show_clip_context_menu(self, point):
            index = self.list.indexAt(point)
            clip_id = self.clip_model.clip_id_for_index(index)
            if clip_id is None:
                return
            self._select_clip_id(clip_id)

            menu = QMenu(self.list)
            edit_item = menu.addAction("Edit")
            info_item = menu.addAction("View Clip Info")
            menu.addSeparator()
            remove_item = menu.addAction("Remove From Project")
            selected = menu.exec(self.list.viewport().mapToGlobal(point))
            if selected is edit_item:
                self._edit_selected(explicit_clip_id=clip_id)
            elif selected is info_item:
                self._view_clip_info(clip_id)
            elif selected is remove_item:
                self._remove_selected()

        def _view_clip_info(self, clip_id):
            clip = session.project.clip_for_id(str(clip_id))
            if clip is None:
                return
            duration = duration_for_clip(clip)
            source_name = Path(clip.source).name
            if duration is None:
                source_duration_text = "Unavailable"
                active_length_text = "Unavailable"
            else:
                source_duration_text = f"{duration:.3f} s"
                try:
                    active_length_text = f"{clip.clip_duration(duration):.3f} s"
                except Exception:
                    active_length_text = "Unavailable"
            trim_out = (
                "Source end"
                if clip.trim_out_source_time is None
                else f"{float(clip.trim_out_source_time):.3f} s"
            )
            QMessageBox.information(
                self,
                "PanoPilot — Clip Info",
                (
                    f"{source_name}\n\n"
                    f"Source length: {source_duration_text}\n"
                    f"Active Clip length: {active_length_text}\n"
                    f"Trim: {float(clip.trim_in_source_time):.3f} s → {trim_out}\n"
                    f"Camera Positions: {len(clip.camera_positions)}\n\n"
                    f"Source file:\n{clip.source}"
                ),
            )

        def _select_clip_id(self, clip_id):
            index = self.clip_model.index_for_clip_id(clip_id)
            if not index.isValid():
                return
            self.list.setCurrentIndex(index)
            self.list.scrollTo(
                index,
                QAbstractItemView.ScrollHint.EnsureVisible,
            )

        def _active_editor(self):
            return getattr(self.editor_host, "_panopilot_editor_widget", None)

        def _show_project_settings(self):
            if self.clip_editor_active:
                return
            self.settings_dialog.show()
            self.settings_dialog.raise_()
            self.settings_dialog.activateWindow()

        def _show_clips_toggled(self, checked):
            self.clip_strip_frame.setVisible(
                bool(checked)
                and not self.focus_action.isChecked()
                and not self.clip_editor_active
                and self.workspace_mode == "home"
            )

        def _focus_toggled(self, checked):
            checked = bool(checked)
            self.focus_action.setText(
                "Exit Focus Viewer" if checked else "Focus Viewer"
            )
            self.clip_strip_frame.setVisible(
                (not checked)
                and self.show_clips_action.isChecked()
                and not self.clip_editor_active
                and self.workspace_mode == "home"
            )

        def _show_home(self):
            self.workspace_mode = "home"
            if self.arrange_widget is not None:
                self.editor_host_layout.removeWidget(self.arrange_widget)
                self.arrange_widget.setParent(None)
                self.arrange_widget.deleteLater()
                self.arrange_widget = None
            self.editor_placeholder.show()
            self.clip_strip_frame.setVisible(
                self.show_clips_action.isChecked()
                and not self.focus_action.isChecked()
                and not self.clip_editor_active
            )
            self.context_status.setText("Ready")
            self._refresh()

        def _show_arrange_mode(self, selected_clip_id=None):
            if self.clip_editor_active:
                self.pending_workspace_mode = ("arrange", selected_clip_id)
                editor = self._active_editor()
                if editor is not None:
                    editor.close()
                return
            if not session.project.clips:
                QMessageBox.information(
                    self,
                    "PanoPilot — Arrange Clips",
                    "Add at least one Clip before opening Arrange mode.",
                )
                return
            durations = {}
            for clip in session.project.clips:
                value = duration_for_clip(clip)
                if value is None:
                    QMessageBox.warning(
                        self,
                        "PanoPilot — Arrange unavailable",
                        f"Could not determine the duration of {Path(clip.source).name}.",
                    )
                    return
                durations[clip.id] = value
            if selected_clip_id is None:
                selected_clip_id = self._selected_clip_id()
            self.workspace_mode = "arrange"
            self.editor_placeholder.hide()
            self.clip_strip_frame.hide()
            if self.arrange_widget is None:
                self.arrange_widget = ArrangeTimelineWidget(
                    reorder_callback=self._arrange_reorder,
                    back_callback=self._show_home,
                )
                self.editor_host_layout.addWidget(self.arrange_widget, 1)
            self.context_status.setText("Arrange Clips")
            self._refresh(selected_clip_id)

        def _arrange_reorder(self, clip_id, new_index):
            session.move_clip(str(clip_id), int(new_index))
            self._refresh(str(clip_id))

        def _request_arrange_from_editor(self, clip_id=None):
            self.pending_workspace_mode = ("arrange", clip_id)
            editor = self._active_editor()
            if editor is not None:
                editor.close()

        def _close_active_editor(self):
            editor = self._active_editor()
            if editor is not None:
                editor.close()
            elif self.workspace_mode == "arrange":
                self._show_home()

        def _refresh(self, selected_clip_id=None):
            if selected_clip_id is None:
                selected_clip_id = (
                    self._selected_clip_id()
                )

            durations = {}

            for clip in session.project.clips:
                value = duration_for_clip(clip)
                if value is not None:
                    durations[clip.id] = value

            rows = clip_list_rows(
                session.project,
                durations,
            )
            preview_states = {
                row["clip_id"]: (
                    self._preview_snapshot(row["clip_id"]).state
                    if self._preview_snapshot(row["clip_id"]) is not None
                    else None
                )
                for row in rows
            }
            thumbnail_paths = {}
            for row in rows:
                snapshot = self._preview_snapshot(row["clip_id"])
                if snapshot is None or snapshot.state != "succeeded":
                    continue
                entry = snapshot.result
                video_path = getattr(entry, "video_path", None)
                if video_path is None:
                    continue
                candidate = thumbnail_path_for_video(video_path)
                if candidate.is_file():
                    thumbnail_paths[row["clip_id"]] = str(candidate)

            self.clip_model.set_rows(
                rows,
                preview_states=preview_states,
                thumbnail_paths=thumbnail_paths,
            )

            if rows:
                self._select_clip_id(
                    selected_clip_id or rows[0]["clip_id"]
                )

            presentation = build_workspace_view_state(
                session.project,
                durations,
                dirty=session.dirty,
            )
            stabilization_percent = presentation.stabilization_percent
            self.project_info.setText(presentation.summary)
            self.project_info.setToolTip(presentation.summary)
            self.home_summary_label.setText(
                f"{len(session.project.clips)} clips · "
                f"{session.project.output_resolution} · {presentation.fps_summary}"
            )
            self.home_path_label.setText(Path(project_path).name)
            self.home_path_label.setToolTip(str(project_path))
            self.home_name_edit.setToolTip(f"Edit the project name.\nProject file: {project_path}")
            for name_edit in (self.home_name_edit, self.settings_name_edit):
                if name_edit.text() != session.project.name:
                    name_edit.blockSignals(True)
                    name_edit.setText(session.project.name)
                    name_edit.blockSignals(False)

            aspect_index = self.aspect_combo.findData(session.project.output_aspect)
            if aspect_index >= 0 and self.aspect_combo.currentIndex() != aspect_index:
                self.aspect_combo.blockSignals(True)
                self.aspect_combo.setCurrentIndex(aspect_index)
                self.aspect_combo.blockSignals(False)

            resolution_index = self.resolution_combo.findData(
                session.project.output_resolution
            )
            if (
                resolution_index >= 0
                and self.resolution_combo.currentIndex()
                != resolution_index
            ):
                self.resolution_combo.blockSignals(
                    True
                )
                self.resolution_combo.setCurrentIndex(
                    resolution_index
                )
                self.resolution_combo.blockSignals(
                    False
                )

            fps_index = self.fps_combo.findData(
                session.project.output_fps
            )
            if (
                fps_index >= 0
                and self.fps_combo.currentIndex()
                != fps_index
            ):
                self.fps_combo.blockSignals(
                    True
                )
                self.fps_combo.setCurrentIndex(
                    fps_index
                )
                self.fps_combo.blockSignals(
                    False
                )

            quality_index = self.quality_combo.findData(
                session.project.output_quality
            )
            if (
                quality_index >= 0
                and self.quality_combo.currentIndex()
                != quality_index
            ):
                self.quality_combo.blockSignals(
                    True
                )
                self.quality_combo.setCurrentIndex(
                    quality_index
                )
                self.quality_combo.blockSignals(
                    False
                )

            if self.stabilization_slider.value() != stabilization_percent:
                self.stabilization_slider.blockSignals(True)
                self.stabilization_slider.setValue(stabilization_percent)
                self.stabilization_slider.blockSignals(False)
            self.stabilization_value.setText(f"{stabilization_percent}%")

            active_editor = self._active_editor()
            editor_active = self.clip_editor_active and active_editor is not None

            self.undo_action.setEnabled(
                editor_active or session.can_undo
            )
            self.redo_action.setEnabled(
                editor_active or session.can_redo
            )
            self.save_action.setEnabled(
                editor_active or session.dirty
            )
            self.save_as_action.setEnabled(not self.clip_editor_active)
            self.close_clip_action.setEnabled(editor_active)
            self.close_project_action.setEnabled(not self.clip_editor_active)

            self.undo_action.setText(
                "Undo Clip Edit" if editor_active
                else (f"Undo {session.undo_label}" if session.undo_label else "Undo")
            )
            self.redo_action.setText(
                "Redo Clip Edit" if editor_active
                else (f"Redo {session.redo_label}" if session.redo_label else "Redo")
            )

            has_selection = (
                self._selected_clip_id()
                is not None
            )
            workspace_available = (
                not self.clip_editor_active
            )
            home_mode = self.workspace_mode == "home"

            self.list.setEnabled(workspace_available)
            self.settings_name_edit.setEnabled(workspace_available)
            self.aspect_combo.setEnabled(workspace_available)
            self.resolution_combo.setEnabled(workspace_available)
            self.fps_combo.setEnabled(workspace_available)
            self.quality_combo.setEnabled(workspace_available)
            self.stabilization_slider.setEnabled(workspace_available)
            self.open_project_action.setEnabled(workspace_available)
            self.add_action.setEnabled(workspace_available)
            self.home_add_clips_button.setEnabled(workspace_available and home_mode)
            self.home_open_button.setEnabled(workspace_available and home_mode)
            self.home_start_button.setEnabled(workspace_available and home_mode)
            self.home_settings_button.setEnabled(workspace_available and home_mode)
            self.remove_action.setEnabled(has_selection and workspace_available)
            self.move_earlier_action.setEnabled(has_selection and workspace_available)
            self.move_later_action.setEnabled(has_selection and workspace_available)
            self.edit_action.setEnabled(has_selection and workspace_available and home_mode)
            self.arrange_action.setEnabled(bool(session.project.clips) and workspace_available and home_mode)
            self._update_clip_menu_visibility()
            self.preview_action.setEnabled(
                bool(session.project.clips) and workspace_available
            )
            self.home_preview_button.setEnabled(self.preview_action.isEnabled() and home_mode)
            self.settings_action.setEnabled(workspace_available)
            self.show_clips_action.setEnabled(workspace_available)
            export_snapshot = (
                self.background_jobs.snapshot(
                    self.export_job_key
                )
                if self.export_job_key
                else None
            )
            self.export_action.setEnabled(
                bool(session.project.clips)
                and workspace_available
                and not (
                    export_snapshot is not None
                    and export_snapshot.active
                )
            )
            self.home_export_button.setEnabled(self.export_action.isEnabled() and home_mode)
            self.home_export_button.setToolTip(self.home_summary_label.text())
            self.clip_strip_frame.setVisible(
                bool(session.project.clips) and home_mode and workspace_available
                and self.show_clips_action.isChecked() and not self.focus_action.isChecked()
            )
            self.home_arrange_button.setEnabled(bool(session.project.clips) and workspace_available and home_mode)

            if self.arrange_widget is not None and self.workspace_mode == "arrange":
                if len(durations) == len(session.project.clips):
                    self.arrange_widget.set_project(
                        build_arrange_view_state(session.project, durations),
                        thumbnail_paths=thumbnail_paths,
                        selected_clip_id=selected_clip_id,
                    )

            suffix = " *" if session.dirty else ""
            self.setWindowTitle(f"PanoPilot — {session.project.name}{suffix}")

        def _commit_project_name(self, name):
            value = str(name).strip()
            if not value or value == session.project.name:
                self._refresh()
                return
            try:
                session.set_project_name(value)
            except Exception as exc:
                QMessageBox.critical(self, "PanoPilot — Project name failed", str(exc))
            self._refresh()

        def _aspect_changed(self, _index):
            aspect = self.aspect_combo.currentData()
            if aspect is None or aspect == session.project.output_aspect:
                return
            try:
                session.set_output_aspect(aspect)
            except Exception as exc:
                QMessageBox.critical(self, "PanoPilot — Output frame failed", str(exc))
            self._refresh()

        def _resolution_changed(self, _index):
            resolution = self.resolution_combo.currentData()
            if resolution is None:
                return
            try:
                session.set_output_resolution(
                    resolution
                )
            except Exception as exc:
                QMessageBox.critical(
                    self,
                    "PanoPilot — Output size failed",
                    str(exc),
                )
            self._refresh()

        def _fps_changed(self, _index):
            fps = self.fps_combo.currentData()
            if fps is None:
                return
            try:
                session.set_output_fps(
                    fps
                )
            except Exception as exc:
                QMessageBox.critical(
                    self,
                    "PanoPilot — Output FPS failed",
                    str(exc),
                )
            self._refresh()

        def _quality_changed(self, _index):
            quality = self.quality_combo.currentData()
            if quality is None:
                return
            try:
                session.set_output_quality(
                    quality
                )
            except Exception as exc:
                QMessageBox.critical(
                    self,
                    "PanoPilot — Export quality failed",
                    str(exc),
                )
            self._refresh()

        def _stabilization_preview(self, value):
            self.stabilization_value.setText(f"{int(value)}%")

        def _stabilization_committed(self):
            amount = self.stabilization_slider.value() / 100.0
            try:
                session.set_stabilization_amount(amount)
            except Exception as exc:
                QMessageBox.critical(
                    self, "PanoPilot — Stabilization failed", str(exc)
                )
                self._refresh()
                return
            self._refresh()
            self._restart_preview_jobs()

        def _confirm_project_switch(self):
            if not session.dirty:
                return True
            box = QMessageBox(self)
            box.setWindowTitle("PanoPilot — Unsaved project changes")
            box.setText("Save changes before opening another Project?")
            box.setInformativeText(
                "Only one Project is edited at a time. Opening another Project closes the current session."
            )
            box.setStandardButtons(
                QMessageBox.StandardButton.Save
                | QMessageBox.StandardButton.Discard
                | QMessageBox.StandardButton.Cancel
            )
            box.setDefaultButton(QMessageBox.StandardButton.Save)
            choice = box.exec()
            if choice == QMessageBox.StandardButton.Save:
                return bool(self._save())
            if choice == QMessageBox.StandardButton.Discard:
                return True
            return False

        def _open_project(self):
            nonlocal session, project_path
            if self.clip_editor_active:
                return False
            export_snapshot = (
                self.background_jobs.snapshot(self.export_job_key)
                if self.export_job_key
                else None
            )
            if export_snapshot is not None and export_snapshot.active:
                QMessageBox.information(
                    self,
                    "PanoPilot — Export in progress",
                    "Finish or cancel the active export before opening another Project.",
                )
                return False
            if not self._confirm_project_switch():
                return False

            selected, _filter = QFileDialog.getOpenFileName(
                self,
                "Open PanoPilot Project",
                str(Path(project_path).parent),
                "PanoPilot Project (*.json);;All files (*)",
            )
            if not selected:
                return False

            target_path = Path(selected).expanduser().resolve(strict=False)
            try:
                loaded = normalize_project_source_paths(
                    load_project(target_path),
                    project_path=target_path,
                )
            except Exception as exc:
                QMessageBox.critical(
                    self,
                    "PanoPilot — Open Project failed",
                    str(exc),
                )
                return False

            # Discard project-specific background state before switching the
            # authoritative ProjectSession. Old worker completions are ignored.
            self.background_jobs.cancel_all()
            self.preview_job_keys.clear()
            self.import_job_sources.clear()
            self.handled_import_jobs.clear()
            self.export_job_key = None
            self.handled_export_jobs.clear()
            self.last_preview_states = {}
            self.pending_clip_edit = None
            duration_cache.clear()

            project_path = target_path
            session = ProjectSession(loaded, path=project_path)
            self.settings_dialog.close()
            if self.arrange_widget is not None:
                self.editor_host_layout.removeWidget(self.arrange_widget)
                self.arrange_widget.setParent(None)
                self.arrange_widget.deleteLater()
                self.arrange_widget = None
            self.workspace_mode = "home"
            self.editor_placeholder.show()
            self.clip_strip_frame.setVisible(self.show_clips_action.isChecked())
            self.context_status.setText(f"Opened: {project_path.name}")
            self._refresh()
            self._schedule_preview_jobs()
            return True

        def _add_files(self):
            paths, _filter = QFileDialog.getOpenFileNames(
                self,
                "Add DJI Osmo 360 recordings",
                "",
                "DJI Osmo 360 (*.OSV *.osv);;All files (*)",
            )

            if not paths:
                return

            existing = {
                str(
                    Path(clip.source).expanduser().resolve(
                        strict=False
                    )
                )
                for clip in session.project.clips
            }
            skipped = []

            for source in paths:
                resolved = str(
                    Path(source).expanduser().resolve(
                        strict=False
                    )
                )
                if resolved in existing:
                    skipped.append(
                        Path(source).name
                    )
                    continue
                self._queue_import_validation(
                    absolute_source_path(source, project_path=project_path)
                )

            if skipped:
                QMessageBox.information(
                    self,
                    "PanoPilot — Duplicate sources skipped",
                    "Already in project: "
                    + ", ".join(skipped),
                )

            self.work_status.setText("Validating media…")
            self.work_status.setToolTip(
                "Validating selected recordings; existing ready Clips remain usable."
            )

        def _remove_selected(self):
            clip_id = (
                self._selected_clip_id()
            )

            if clip_id is None:
                return

            clip = session.project.clip_for_id(
                clip_id
            )

            if clip is None:
                return

            choice = QMessageBox.question(
                self,
                "PanoPilot — Remove Clip",
                (
                    f"Remove '{Path(clip.source).name}' from the project?\n\n"
                    "The source recording will not be modified or deleted. "
                    "This operation can be undone."
                ),
            )

            if choice != QMessageBox.StandardButton.Yes:
                return

            index = (
                session.project.clip_index(
                    clip_id
                )
                or 0
            )

            preview_key = self.preview_job_keys.pop(
                clip_id,
                None,
            )
            if preview_key is not None:
                self.background_jobs.cancel(
                    preview_key
                )

            session.remove_clip(
                clip_id
            )

            selected = None

            if session.project.clips:
                selected = session.project.clips[
                    min(
                        index,
                        len(
                            session.project.clips
                        )
                        - 1,
                    )
                ].id

            self._refresh(
                selected
            )

        def _move_selected(self, delta):
            clip_id = (
                self._selected_clip_id()
            )

            if clip_id is None:
                return

            session.move_clip_by(
                clip_id,
                delta,
            )
            self._refresh(
                clip_id
            )

        def _undo(self):
            editor = self._active_editor()
            if editor is not None:
                editor._undo_edit()
                return
            selected = self._selected_clip_id()
            session.undo()
            self._refresh(selected)

        def _redo(self):
            editor = self._active_editor()
            if editor is not None:
                editor._redo_edit()
                return
            selected = self._selected_clip_id()
            session.redo()
            self._refresh(selected)

        def _save(self):
            editor = self._active_editor()
            if editor is not None:
                return editor._save_project()
            try:
                session.save(project_path)
            except Exception as exc:
                QMessageBox.critical(
                    self,
                    "PanoPilot — Save failed",
                    str(exc),
                )
                return False

            self._refresh()
            return True

        def _save_as(self):
            nonlocal project_path
            if self.clip_editor_active:
                return False
            current = Path(project_path)
            suggested_name = (
                "".join(
                    ch if ch.isalnum() or ch in ("-", "_") else "-"
                    for ch in session.project.name.lower()
                ).strip("-")
                or current.stem
                or "panopilot-project"
            ) + ".json"
            suggested = str(current.parent / suggested_name)
            target, _filter = QFileDialog.getSaveFileName(
                self,
                "Save PanoPilot Project As",
                suggested,
                "PanoPilot Project (*.json);;All files (*)",
            )
            if not target:
                return False
            target_path = Path(target).expanduser().resolve(strict=False)
            if target_path.suffix.lower() != ".json":
                target_path = target_path.with_suffix(".json")
            try:
                session.save(target_path)
            except Exception as exc:
                QMessageBox.critical(self, "PanoPilot — Save As failed", str(exc))
                return False
            project_path = target_path
            self.context_status.setText(f"Saved As: {target_path.name}")
            self._refresh()
            return True

        def _save_before_child_window(
            self,
            *,
            purpose,
        ):
            if not session.dirty:
                return True

            choice = QMessageBox.question(
                self,
                f"PanoPilot — Save before {purpose}",
                (
                    "Project changes must be saved before "
                    f"{purpose.lower()}.\n\nSave now?"
                ),
                (
                    QMessageBox.StandardButton.Save
                    | QMessageBox.StandardButton.Cancel
                ),
                QMessageBox.StandardButton.Save,
            )

            if (
                choice
                != QMessageBox.StandardButton.Save
            ):
                return False

            return bool(
                self._save()
            )

        def _source_validation_failures(self, clip_ids=None):
            selected = set(str(value) for value in clip_ids) if clip_ids is not None else None
            return [
                item
                for item in project_source_statuses(session.project)
                if (selected is None or item["clip_id"] in selected)
                and item["status"] != "ok"
            ]

        def _show_source_validation_failures(self, failures, purpose):
            if not failures:
                return False
            details = "\n".join(
                f"• {item['clip_id']}: {Path(item['source']).name} — {item['status']}\n  {item['message']}"
                for item in failures
            )
            QMessageBox.warning(
                self,
                "PanoPilot — Source validation blocked",
                f"{purpose} cannot continue because referenced media is missing, unreadable, or changed:\n\n{details}",
            )
            return True

        def _export_project(self):
            if not session.project.clips:
                return

            if self.focus_action.isChecked():
                self.focus_action.setChecked(False)

            failures = self._source_validation_failures()
            if self._show_source_validation_failures(failures, "Project Export"):
                return

            if not self._save_before_child_window(
                purpose="Project Export"
            ):
                return

            default_output = str(
                project_path.with_name(
                    f"{project_path.stem}-"
                    f"{session.project.output_resolution}-"
                    f"{int(round(output_profile_for_project(session.project).fps))}fps-"
                    f"{session.project.output_quality}.mp4"
                )
            )
            output, _filter = (
                QFileDialog.getSaveFileName(
                    self,
                    "Export PanoPilot Project",
                    default_output,
                    "MP4 video (*.mp4)",
                )
            )

            if not output:
                return

            output_path = Path(
                output
            )

            if output_path.suffix.lower() != ".mp4":
                output_path = (
                    output_path.with_suffix(
                        ".mp4"
                    )
                )

            durations = {}
            for clip in session.project.clips:
                duration = duration_for_clip(
                    clip
                )
                if duration is not None:
                    durations[clip.id] = duration

            timeline_duration = None
            if len(durations) == len(
                session.project.clips
            ):
                spans = build_project_timeline(
                    session.project,
                    durations,
                )
                timeline_duration = (
                    spans[-1].timeline_end
                    if spans
                    else 0.0
                )

            export_summary = build_export_summary(
                session.project,
                output_path,
                timeline_duration=(
                    timeline_duration
                ),
            )

            confirmation = QMessageBox(
                self
            )
            confirmation.setWindowTitle(
                "PanoPilot — Export Project"
            )
            confirmation.setIcon(
                QMessageBox.Icon.Question
            )
            confirmation.setText(
                "Ready to export?"
            )
            confirmation.setInformativeText(
                export_summary["text"]
                + "\n\nFile size depends on video content. "
                "The source recordings are never modified."
            )
            export_now = confirmation.addButton(
                "Export",
                QMessageBox.ButtonRole.AcceptRole,
            )
            confirmation.addButton(
                "Cancel",
                QMessageBox.ButtonRole.RejectRole,
            )
            confirmation.setDefaultButton(
                export_now
            )
            extra_smoothing_check = QCheckBox("Extra smoothing for final video (slower)")
            extra_smoothing_check.setEnabled(session.project.stabilization_amount > 0.0)
            extra_smoothing_check.setToolTip(
                "Analyzes remaining motion and renders again from the 360° source. "
                "Final framing may differ slightly from the preview. "
                "Enable stabilization in Project Settings first."
            )
            confirmation.setCheckBox(extra_smoothing_check)
            confirmation.exec()

            if (
                confirmation.clickedButton()
                is not export_now
            ):
                return

            extra_smoothing = extra_smoothing_check.isChecked()

            job_key = (
                "export:"
                + str(
                    time.monotonic_ns()
                )
            )
            self.export_job_key = job_key

            # Freeze the exact saved Project state used by this export. The
            # Organizer remains editable while rendering, so later Save actions
            # must not change an already-running export.
            snapshot_path = output_path.with_name(
                "."
                + output_path.stem
                + ".panopilot-export-snapshot-"
                + str(time.monotonic_ns())
                + ".json"
            )
            snapshot_payload = (
                json.dumps(
                    session.project.to_dict(),
                    indent=2,
                )
                + "\n"
            )

            def export_task(context):
                context.check_cancelled()
                snapshot_path.write_text(
                    snapshot_payload,
                    encoding="utf-8",
                )
                try:
                    result = export_project_video(
                        snapshot_path,
                        output_path,
                        visual_stabilization=extra_smoothing,
                        visual_stabilization_mode="spherical",
                        progress_callback=(
                            context.progress
                        ),
                        cancel_callback=(
                            lambda: context.cancelled
                        ),
                    )
                    result["project"] = str(
                        project_path
                    )
                    return result
                finally:
                    snapshot_path.unlink(
                        missing_ok=True
                    )

            self.background_jobs.submit(
                job_key,
                f"Export — {output_path.name}",
                export_task,
            )
            self.export_progress.setValue(
                0
            )
            self.export_progress.setVisible(
                True
            )
            self.abort_export_button.setVisible(
                True
            )
            self.export_action.setEnabled(
                False
            )
            self.work_status.setText("Exporting…")
            self.work_status.setToolTip(
                "Export started from the saved Project snapshot. "
                "You may continue editing; new edits affect the next export."
            )

        def _preview_project(self):
            if not session.project.clips:
                return

            failures = self._source_validation_failures()
            if self._show_source_validation_failures(failures, "Project Preview"):
                return

            not_ready = [
                clip
                for clip in session.project.clips
                if not self._preview_ready(clip.id)
            ]
            if not_ready:
                self._schedule_preview_jobs()
                QMessageBox.information(
                    self,
                    "PanoPilot — Project preview preparing",
                    (
                        f"{len(not_ready)} Clip preview(s) are still preparing in the background. "
                        "You can continue editing any Clip marked PREVIEW READY and start Project Preview when all Clips are ready."
                    ),
                )
                return

            if not self._save_before_child_window(
                purpose="Project Preview"
            ):
                return

            state["action"] = "preview"
            state["clip_id"] = None
            self.close()

        def _edit_selected(self, initial_mode="reframe", explicit_clip_id=None):
            nonlocal session

            clip_id = (
                str(explicit_clip_id)
                if explicit_clip_id is not None
                else self._selected_clip_id()
            )

            if clip_id is None:
                return

            clip = session.project.clip_for_id(
                clip_id
            )

            if clip is None:
                return

            failures = self._source_validation_failures(
                [clip.id]
            )
            if self._show_source_validation_failures(
                failures,
                "Clip editing",
            ):
                return

            preview_snapshot = self._preview_snapshot(clip.id)
            if not self._preview_ready(clip.id):
                # One user gesture is enough: remember the requested Clip and
                # open it automatically as soon as its prepared preview is ready.
                self.pending_clip_edit = (clip.id, str(initial_mode))
                if preview_snapshot is not None and preview_snapshot.state == "failed":
                    self._schedule_preview_job(clip, replace=True)
                else:
                    self._schedule_preview_job(clip)
                self.context_status.setText(
                    f"Preparing Clip Editor: {Path(clip.source).name}"
                )
                self.work_status.setText("Preparing Clip…")
                self.work_status.setToolTip(
                    "The Clip Editor will open automatically when preparation completes."
                )
                return

            self.pending_clip_edit = None

            if not self._save_before_child_window(
                purpose="Clip editing"
            ):
                return

            # 0.46 embedded editor: the Project workspace keeps the one Qt
            # application event loop.  The editor reports completion through
            # a callback instead of starting a nested QEventLoop.
            self.clip_editor_active = True
            self.workspace_mode = "clip"
            self.editor_placeholder.hide()
            self.clip_strip_frame.hide()
            self.context_status.setText(
                f"Editing: {Path(clip.source).name}"
            )
            self._refresh(selected_clip_id=clip.id)

            try:
                from .explore import explore_osv

                explore_osv(
                    clip.source,
                    project_path=project_path,
                    clip_id=clip.id,
                    source_time=clip.trim_in_source_time,
                    view_long_edge=view_long_edge,
                    preview_fps=preview_fps,
                    cache_dir=cache_dir,
                    rebuild_preview=rebuild_preview,
                    audio_enabled=audio_enabled,
                    initial_mode=initial_mode,
                    arrange_callback=lambda clip_id=clip.id: (
                        self._request_arrange_from_editor(clip_id)
                    ),
                    embed_host=self.editor_host,
                    on_closed=lambda result, clip_id=clip.id: (
                        self._clip_editor_closed(clip_id, result)
                    ),
                )
                self._refresh(selected_clip_id=clip.id)
            except Exception as exc:
                self.clip_editor_active = False
                self.workspace_mode = "home"
                self.editor_placeholder.show()
                self.clip_strip_frame.setVisible(
                    self.show_clips_action.isChecked()
                    and not self.focus_action.isChecked()
                )
                QMessageBox.critical(
                    self,
                    "PanoPilot — Clip Editor failed",
                    str(exc),
                )
                self._refresh(selected_clip_id=clip.id)

        def _clip_editor_closed(self, clip_id, result):
            nonlocal session

            self.clip_editor_active = False
            self.workspace_mode = "home"
            self.editor_placeholder.show()
            self.clip_strip_frame.setVisible(
                self.show_clips_action.isChecked()
                and not self.focus_action.isChecked()
            )

            # The Clip Editor saves through its own ProjectSession. Reload the
            # authoritative project once the child view has closed.
            session = ProjectSession(
                load_project(project_path),
                path=project_path,
            )
            pending = self.pending_workspace_mode
            self.pending_workspace_mode = None
            if pending is not None and pending[0] == "arrange":
                self._show_arrange_mode(pending[1] or clip_id)
                return
            self._refresh(selected_clip_id=clip_id)

            camera_count = int(
                (result or {}).get("camera_position_count", 0)
            )
            self.context_status.setText(
                f"Ready · {camera_count} Camera Position(s) in last edited Clip"
            )


        def closeEvent(self, event):
            if self.clip_editor_active:
                QMessageBox.information(
                    self,
                    "PanoPilot — Clip Editor active",
                    "Close the active Clip Editor before closing the Project.",
                )
                event.ignore()
                return

            export_snapshot = (
                self.background_jobs.snapshot(
                    self.export_job_key
                )
                if self.export_job_key
                else None
            )
            if (
                export_snapshot is not None
                and export_snapshot.active
            ):
                choice = QMessageBox.question(
                    self,
                    "PanoPilot — Export is running",
                    (
                        "An export is still running in the background. "
                        "Cancel it and close the Project Organizer?"
                    ),
                )
                if choice != QMessageBox.StandardButton.Yes:
                    event.ignore()
                    return
                self.background_jobs.cancel(
                    self.export_job_key
                )

            if session.dirty:
                box = QMessageBox(
                    self
                )
                box.setWindowTitle(
                    "PanoPilot — Unsaved project changes"
                )
                box.setText(
                    "Save project changes before closing?"
                )
                box.setInformativeText(
                    "Discard leaves the existing project file unchanged."
                )
                box.setStandardButtons(
                    QMessageBox.StandardButton.Save
                    | QMessageBox.StandardButton.Discard
                    | QMessageBox.StandardButton.Cancel
                )
                box.setDefaultButton(
                    QMessageBox.StandardButton.Save
                )

                choice = box.exec()

                if (
                    choice
                    == QMessageBox.StandardButton.Save
                ):
                    if not self._save():
                        event.ignore()
                        return
                elif (
                    choice
                    == QMessageBox.StandardButton.Discard
                ):
                    session.discard_to_saved()
                else:
                    event.ignore()
                    return

            self.background_timer.stop()
            self.background_jobs.cancel_all()
            self.background_jobs.shutdown(
                cancel=True,
                wait=False,
            )
            event.accept()
            window_loop.quit()

    app = QApplication.instance()

    if app is None:
        app = QApplication(
            sys.argv[:1]
        )
        app.setApplicationName(
            "PanoPilot"
        )

    # The workflow intentionally alternates top-level windows. Keep the
    # QApplication alive when the organizer closes to launch a Clip Editor.
    app.setQuitOnLastWindowClosed(
        False
    )

    window_loop = QEventLoop()

    widget = ProjectWidget()
    widget.showMaximized()
    widget.raise_()
    widget.activateWindow()
    if session.project.clips:
        widget.list.setFocus()
    else:
        widget.home_start_button.setFocus()

    window_loop.exec()

    return {
        **state,
        "project_path": str(
            project_path
        ),
        "clip_count": len(
            session.project.clips
        ),
        "dirty": bool(
            session.dirty
        ),
    }
