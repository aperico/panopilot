"""
PanoPilot multi-Clip project organizer.

0.18 deliberately separates two editing scales:

Project Organizer
    ordered Clip instances: import / reorder / remove

Clip Editor
    one Clip's trim + View Path + Camera Positions

The organizer launches the existing Clip Editor for the selected Clip. This
keeps the proven 0.17.1 reframing UI stable while introducing the sequential
multi-Clip project model with transactional Undo/Redo and explicit Save.
"""
from __future__ import annotations

from pathlib import Path
import sys
import time

from .project import load_project
from .session import ProjectSession
from .source import probe_source
from .timeline import build_project_timeline


WINDOW_TITLE = "PanoPilot — Project"


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
):
    """
    Import distinct sources in the provided order.

    Repeated source instances are intentionally not supported yet. Existing
    sources are reported as skipped rather than duplicated.
    """
    added = []
    skipped = []

    for source in sources:
        source = str(source)

        if session.project.clips_for_source(
            source
        ):
            skipped.append(
                {
                    "source": source,
                    "reason": "already-in-project",
                }
            )
            continue

        transaction = session.add_clip(
            source
        )

        operation = (
            transaction.get("result")
            or {}
        )

        if transaction.get("changed"):
            added.append(
                operation.get("clip_id")
            )

    return {
        "added_clip_ids": [
            value
            for value in added
            if value is not None
        ],
        "skipped": skipped,
        **session.state(),
    }


def clip_list_rows(
    project,
    durations=None,
):
    durations = durations or {}
    rows = []

    for index, clip in enumerate(
        project.clips
    ):
        duration = durations.get(
            clip.id
        )

        if duration is None:
            resolved_out = (
                clip.trim_out_source_time
            )
            clip_duration = None
        else:
            resolved_out = (
                clip.resolved_trim_out(
                    duration
                )
            )
            clip_duration = (
                resolved_out
                - clip.trim_in_source_time
            )

        rows.append(
            {
                "index": index,
                "number": index + 1,
                "clip_id": clip.id,
                "source": clip.source,
                "source_name": Path(
                    clip.source
                ).name,
                "trim_in": float(
                    clip.trim_in_source_time
                ),
                "trim_out": (
                    float(resolved_out)
                    if resolved_out is not None
                    else None
                ),
                "duration": (
                    float(clip_duration)
                    if clip_duration is not None
                    else None
                ),
                "camera_position_count": len(
                    clip.camera_positions
                ),
            }
        )

    return rows


def run_project_editor(
    project_path,
    *,
    import_sources=None,
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
    project_path = Path(project_path)
    project = load_project(project_path)
    session = ProjectSession(
        project,
        path=project_path,
    )

    initial_import = (
        import_sources_into_session(
            session,
            import_sources or [],
        )
    )

    try:
        from PySide6.QtCore import QEventLoop, Qt
        from PySide6.QtWidgets import (
            QApplication,
            QFileDialog,
            QHBoxLayout,
            QLabel,
            QListWidget,
            QListWidgetItem,
            QMessageBox,
            QPushButton,
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

        try:
            value = source_duration(
                clip.source
            )
        except Exception:
            value = None

        duration_cache[clip.id] = value
        return value

    class ProjectWidget(QWidget):
        def __init__(self):
            super().__init__()

            self.setWindowTitle(
                WINDOW_TITLE
            )
            self.resize(920, 520)

            self.title = QLabel(
                "Project Clips — sequential playback order"
            )
            self.title.setStyleSheet(
                "font-size: 17px; font-weight: 600;"
            )

            self.summary = QLabel()
            self.summary.setWordWrap(True)

            self.list = QListWidget()
            self.list.setSelectionMode(
                QListWidget.SelectionMode.SingleSelection
            )
            self.list.itemDoubleClicked.connect(
                lambda _item: self._edit_selected()
            )

            self.add_button = QPushButton(
                "Add OSV Files…"
            )
            self.remove_button = QPushButton(
                "Remove"
            )
            self.up_button = QPushButton(
                "Move Up"
            )
            self.down_button = QPushButton(
                "Move Down"
            )
            self.preview_button = QPushButton(
                "Preview Project"
            )
            self.export_button = QPushButton(
                "Export Project…"
            )
            self.edit_button = QPushButton(
                "Edit Selected Clip"
            )
            self.undo_button = QPushButton(
                "Undo"
            )
            self.redo_button = QPushButton(
                "Redo"
            )
            self.save_button = QPushButton(
                "Save"
            )
            self.close_button = QPushButton(
                "Close"
            )

            self.add_button.clicked.connect(
                self._add_files
            )
            self.remove_button.clicked.connect(
                self._remove_selected
            )
            self.up_button.clicked.connect(
                lambda: self._move_selected(-1)
            )
            self.down_button.clicked.connect(
                lambda: self._move_selected(+1)
            )
            self.preview_button.clicked.connect(
                self._preview_project
            )
            self.export_button.clicked.connect(
                self._export_project
            )
            self.edit_button.clicked.connect(
                self._edit_selected
            )
            self.undo_button.clicked.connect(
                self._undo
            )
            self.redo_button.clicked.connect(
                self._redo
            )
            self.save_button.clicked.connect(
                self._save
            )
            self.close_button.clicked.connect(
                self.close
            )

            buttons = QHBoxLayout()
            buttons.addWidget(
                self.add_button
            )
            buttons.addWidget(
                self.remove_button
            )
            buttons.addWidget(
                self.up_button
            )
            buttons.addWidget(
                self.down_button
            )
            buttons.addStretch(1)
            buttons.addWidget(
                self.undo_button
            )
            buttons.addWidget(
                self.redo_button
            )
            buttons.addWidget(
                self.save_button
            )

            bottom = QHBoxLayout()
            bottom.addWidget(
                self.preview_button
            )
            bottom.addWidget(
                self.export_button
            )
            bottom.addWidget(
                self.edit_button
            )
            bottom.addStretch(1)
            bottom.addWidget(
                self.close_button
            )

            layout = QVBoxLayout(self)
            layout.addWidget(
                self.title
            )
            layout.addWidget(
                self.summary
            )
            layout.addLayout(
                buttons
            )
            layout.addWidget(
                self.list,
                1,
            )
            layout.addLayout(
                bottom
            )

            self._refresh()

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

        def _selected_clip_id(self):
            item = self.list.currentItem()

            if item is None:
                return None

            return item.data(
                Qt.ItemDataRole.UserRole
            )

        def _select_clip_id(self, clip_id):
            if clip_id is None:
                return

            for row in range(
                self.list.count()
            ):
                item = self.list.item(
                    row
                )

                if (
                    item.data(
                        Qt.ItemDataRole.UserRole
                    )
                    == clip_id
                ):
                    self.list.setCurrentRow(
                        row
                    )
                    return

        def _refresh(self, selected_clip_id=None):
            if selected_clip_id is None:
                selected_clip_id = (
                    self._selected_clip_id()
                )

            self.list.clear()

            durations = {}

            for clip in session.project.clips:
                value = duration_for_clip(
                    clip
                )

                if value is not None:
                    durations[clip.id] = value

            rows = clip_list_rows(
                session.project,
                durations,
            )

            for row in rows:
                duration = row["duration"]

                duration_text = (
                    f"{duration:.3f}s"
                    if duration is not None
                    else "duration unavailable"
                )

                trim_out_text = (
                    f"{row['trim_out']:.3f}s"
                    if row["trim_out"] is not None
                    else "source end"
                )

                missing = (
                    ""
                    if Path(row["source"]).is_file()
                    else "  [SOURCE MISSING]"
                )

                text = (
                    f"{row['number']:02d}   "
                    f"{row['source_name']}   "
                    f"| Clip {duration_text}   "
                    f"| In {row['trim_in']:.3f}s   "
                    f"Out {trim_out_text}   "
                    f"| Camera Positions "
                    f"{row['camera_position_count']}"
                    f"{missing}"
                )

                item = QListWidgetItem(
                    text
                )
                item.setData(
                    Qt.ItemDataRole.UserRole,
                    row["clip_id"],
                )
                item.setToolTip(
                    row["source"]
                )
                self.list.addItem(
                    item
                )

            if self.list.count():
                self._select_clip_id(
                    selected_clip_id
                    or rows[0]["clip_id"]
                )

            project_duration = 0.0
            timeline_available = (
                len(durations)
                == len(session.project.clips)
            )

            if (
                timeline_available
                and session.project.clips
            ):
                spans = build_project_timeline(
                    session.project,
                    durations,
                )
                project_duration = (
                    spans[-1].timeline_end
                    if spans
                    else 0.0
                )

            status = (
                "Modified"
                if session.dirty
                else "Saved"
            )

            duration_summary = (
                f"Project duration {project_duration:.3f}s"
                if timeline_available
                else "Project duration unavailable for one or more sources"
            )

            self.summary.setText(
                f"{len(session.project.clips)} Clip(s)   |   "
                f"{duration_summary}   |   "
                f"{status}\n"
                "Timeline order belongs to Clip instances. Reordering does "
                "not change Camera Position Source Times."
            )

            self.undo_button.setEnabled(
                session.can_undo
            )
            self.redo_button.setEnabled(
                session.can_redo
            )
            self.save_button.setEnabled(
                session.dirty
            )

            self.undo_button.setText(
                (
                    f"Undo {session.undo_label}"
                    if session.undo_label
                    else "Undo"
                )
            )
            self.redo_button.setText(
                (
                    f"Redo {session.redo_label}"
                    if session.redo_label
                    else "Redo"
                )
            )

            has_selection = (
                self._selected_clip_id()
                is not None
            )

            self.remove_button.setEnabled(
                has_selection
            )
            self.up_button.setEnabled(
                has_selection
            )
            self.down_button.setEnabled(
                has_selection
            )
            self.edit_button.setEnabled(
                has_selection
            )
            self.preview_button.setEnabled(
                bool(session.project.clips)
            )
            self.export_button.setEnabled(
                bool(session.project.clips)
            )

            suffix = (
                " *"
                if session.dirty
                else ""
            )
            self.setWindowTitle(
                WINDOW_TITLE + suffix
            )

        def _add_files(self):
            paths, _filter = (
                QFileDialog.getOpenFileNames(
                    self,
                    "Add DJI Osmo 360 recordings",
                    "",
                    (
                        "DJI Osmo 360 (*.OSV *.osv);;"
                        "All files (*)"
                    ),
                )
            )

            if not paths:
                return

            result = (
                import_sources_into_session(
                    session,
                    paths,
                )
            )

            selected = (
                result["added_clip_ids"][-1]
                if result["added_clip_ids"]
                else None
            )

            self._refresh(
                selected
            )

            if result["skipped"]:
                names = ", ".join(
                    Path(item["source"]).name
                    for item
                    in result["skipped"]
                )
                QMessageBox.information(
                    self,
                    "PanoPilot — Sources skipped",
                    (
                        "Already in project: "
                        f"{names}"
                    ),
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
            selected = (
                self._selected_clip_id()
            )
            session.undo()
            self._refresh(
                selected
            )

        def _redo(self):
            selected = (
                self._selected_clip_id()
            )
            session.redo()
            self._refresh(
                selected
            )

        def _save(self):
            try:
                session.save(
                    project_path
                )
            except Exception as exc:
                QMessageBox.critical(
                    self,
                    "PanoPilot — Save failed",
                    str(exc),
                )
                return False

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

        def _export_project(self):
            if not session.project.clips:
                return

            missing = [
                clip.source
                for clip in session.project.clips
                if not Path(clip.source).is_file()
            ]

            if missing:
                QMessageBox.warning(
                    self,
                    "PanoPilot — Source missing",
                    (
                        "Project export requires all original source "
                        "recordings. Missing:\n"
                        + "\n".join(missing)
                    ),
                )
                return

            if not self._save_before_child_window(
                purpose="Project Export"
            ):
                return

            default_output = str(
                project_path.with_suffix(
                    ".mp4"
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

            state["action"] = "export"
            state["clip_id"] = None
            state["output"] = str(
                output_path
            )
            self.close()

        def _preview_project(self):
            if not session.project.clips:
                return

            if not self._save_before_child_window(
                purpose="Project Preview"
            ):
                return

            state["action"] = "preview"
            state["clip_id"] = None
            self.close()

        def _edit_selected(self):
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

            if not Path(
                clip.source
            ).is_file():
                QMessageBox.warning(
                    self,
                    "PanoPilot — Source missing",
                    (
                        "The selected source recording cannot be found:\n"
                        f"{clip.source}"
                    ),
                )
                return

            if not self._save_before_child_window(
                purpose="Clip editing"
            ):
                return

            state["action"] = "edit"
            state["clip_id"] = clip_id
            self.close()

        def closeEvent(self, event):
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
    widget.show()
    widget.raise_()
    widget.activateWindow()

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
