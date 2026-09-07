"""Presentation model for the compact Project Clip strip.

This module stays GUI-framework agnostic so importing the CLI/project modules does
not require a display stack.  ``create_qt_clip_strip_model`` is the adapter
boundary and imports PySide6 only when the desktop workspace is actually opened.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ClipStripEntry:
    clip_id: str
    source: str
    title: str
    subtitle: str
    tooltip: str
    source_status: str | None = None
    preview_status: str | None = None
    thumbnail_path: str | None = None


def build_clip_strip_entries(rows, preview_states=None, thumbnail_paths=None):
    preview_states = dict(preview_states or {})
    thumbnail_paths = dict(thumbnail_paths or {})
    entries = []
    preview_labels = {
        "succeeded": "Ready",
        "queued": "Preparing",
        "running": "Preparing",
        "cancelling": "Preparing",
        "failed": "Preview failed",
        "cancelled": "Preview cancelled",
    }

    for fallback_number, row in enumerate(rows, start=1):
        clip_id = str(row.get("clip_id", ""))
        source = str(row.get("source", ""))
        source_name = row.get("source_name") or Path(source).name
        number = int(row.get("number", fallback_number))
        duration = row.get("duration")
        source_duration = row.get("source_duration", duration)
        duration_text = "--:--" if duration is None else f"{float(duration):.1f}s"
        source_duration_text = (
            "--:--" if source_duration is None else f"{float(source_duration):.1f}s"
        )
        cameras = int(row.get("camera_position_count", 0))
        preview_status = preview_states.get(clip_id)
        preview_label = preview_labels.get(preview_status, "")

        subtitle = f"File {source_duration_text}"
        if (
            duration is not None
            and source_duration is not None
            and abs(float(duration) - float(source_duration)) > 1e-6
        ):
            subtitle += f"  ·  Clip {duration_text}"
        subtitle += f"  ·  {cameras} Camera Position"
        if cameras != 1:
            subtitle += "s"
        if preview_label:
            subtitle += f"  ·  {preview_label}"

        source_status = row.get("source_status") or {}
        status_message = str(source_status.get("message", "")).strip()
        trim_out = row.get("trim_out")
        trim_out_text = "source end" if trim_out is None else f"{float(trim_out):.3f}s"
        tooltip_lines = [
            source_name,
            source,
            f"Source length: {source_duration_text}",
            f"Active Clip length: {duration_text}",
            f"Trim: {float(row.get('trim_in', 0.0)):.3f}s → {trim_out_text}",
            f"Camera Positions: {cameras}",
        ]
        if status_message:
            tooltip_lines.append(status_message)

        entries.append(
            ClipStripEntry(
                clip_id=clip_id,
                source=source,
                title=f"Clip {number:02d}",
                subtitle=subtitle,
                tooltip="\n".join(tooltip_lines),
                source_status=source_status.get("status"),
                preview_status=preview_status,
                thumbnail_path=thumbnail_paths.get(clip_id),
            )
        )

    return entries


def create_qt_clip_strip_model(*, parent=None):
    """Create the Qt adapter lazily at the desktop boundary."""
    from PySide6.QtCore import QAbstractListModel, QModelIndex, Qt
    from PySide6.QtGui import QIcon

    class QtClipStripModel(QAbstractListModel):
        ClipIdRole = int(Qt.ItemDataRole.UserRole) + 1
        SourceRole = ClipIdRole + 1
        SourceStatusRole = ClipIdRole + 2
        PreviewStatusRole = ClipIdRole + 3

        def __init__(self, parent=None):
            super().__init__(parent)
            self._entries = []
            self._icon_cache = {}

        def rowCount(self, parent=QModelIndex()):  # noqa: N802 - Qt API
            return 0 if parent.isValid() else len(self._entries)

        def set_rows(self, rows, preview_states=None, thumbnail_paths=None):
            entries = build_clip_strip_entries(rows, preview_states, thumbnail_paths)
            self.beginResetModel()
            self._entries = entries
            self._icon_cache = {}
            self.endResetModel()

        def entry(self, index):
            if not index.isValid() or not (0 <= index.row() < len(self._entries)):
                return None
            return self._entries[index.row()]

        def clip_id_for_index(self, index):
            entry = self.entry(index)
            return None if entry is None else entry.clip_id

        def index_for_clip_id(self, clip_id):
            if clip_id is None:
                return QModelIndex()
            for row_number, entry in enumerate(self._entries):
                if entry.clip_id == clip_id:
                    return self.index(row_number, 0)
            return QModelIndex()

        def data(self, index, role=Qt.ItemDataRole.DisplayRole):
            entry = self.entry(index)
            if entry is None:
                return None
            if role == Qt.ItemDataRole.DisplayRole:
                return f"{entry.title}\n{entry.subtitle}"
            if role == Qt.ItemDataRole.ToolTipRole:
                return entry.tooltip
            if role == Qt.ItemDataRole.DecorationRole and entry.thumbnail_path:
                icon = self._icon_cache.get(entry.thumbnail_path)
                if icon is None:
                    icon = QIcon(entry.thumbnail_path)
                    self._icon_cache[entry.thumbnail_path] = icon
                return icon
            if role == self.ClipIdRole:
                return entry.clip_id
            if role == self.SourceRole:
                return entry.source
            if role == self.SourceStatusRole:
                return entry.source_status
            if role == self.PreviewStatusRole:
                return entry.preview_status
            return None

        def roleNames(self):  # noqa: N802 - Qt API
            roles = super().roleNames()
            roles.update({
                self.ClipIdRole: b"clipId",
                self.SourceRole: b"source",
                self.SourceStatusRole: b"sourceStatus",
                self.PreviewStatusRole: b"previewStatus",
            })
            return roles

    return QtClipStripModel(parent=parent)
