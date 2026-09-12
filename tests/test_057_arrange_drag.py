from types import SimpleNamespace

import pytest

from test_056_home_workflow import home_window


def test_drag_has_thumbnail_hotspot_and_restores_cancelled_card(home_window, monkeypatch):
    from PySide6 import QtGui
    from PySide6.QtCore import QPointF, Qt, QEvent
    from PySide6.QtGui import QColor, QMouseEvent, QPixmap

    captured = {}

    class Drag:
        def __init__(self, parent):
            self.parent = parent
        def setMimeData(self, mime):
            captured["mime"] = mime
        def setPixmap(self, pixmap):
            captured["pixmap"] = pixmap
        def setHotSpot(self, point):
            captured["hotspot"] = point
        def exec(self, action):
            assert self.parent.property("dragging") is True
            assert action == Qt.DropAction.MoveAction
            return Qt.DropAction.IgnoreAction

    monkeypatch.setattr(QtGui, "QDrag", Drag)

    def check(w, app):
        w._show_arrange_mode()
        card = w.arrange_widget.cards[0]
        thumb = QPixmap(160, 90)
        thumb.fill(QColor("#ee3388"))
        card._thumbnail_pixmap = thumb
        card._update_thumbnail()
        card.mousePressEvent(QMouseEvent(QEvent.Type.MouseButtonPress, QPointF(10, 10),
                             QPointF(10, 10), Qt.MouseButton.LeftButton,
                             Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier))
        card.mouseMoveEvent(QMouseEvent(QEvent.Type.MouseMove, QPointF(50, 20),
                            QPointF(50, 20), Qt.MouseButton.NoButton,
                            Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier))
        ghost = captured["pixmap"]
        assert (ghost.width(), ghost.height()) == (224, 152)
        assert ghost.toImage().pixelColor(112, 50).name() == "#ee3388"
        assert ghost.rect().contains(captured["hotspot"])
        assert bytes(captured["mime"].data(w.arrange_widget.MIME_TYPE)).decode() == card.clip_id
        assert card.property("dragging") is False
        assert card._press_pos is None
        assert card.cursor().shape() == Qt.CursorShape.OpenHandCursor
        mime = captured["mime"]
        for x, side in [(1, "before"), (card.width()-1, "after")]:
            card.dragMoveEvent(SimpleNamespace(mimeData=lambda: mime,
                               position=lambda: QPointF(x, 10), acceptProposedAction=lambda: None))
            assert card.property("dropSide") == side
        card.dragLeaveEvent(SimpleNamespace(accept=lambda: None))
        assert card.property("dropSide") == ""
    home_window(2, check)


def test_drag_fallback_is_visible_without_a_prepared_thumbnail(home_window):
    from PySide6.QtGui import QPixmap
    from panopilot.arrange_drag import clip_drag_pixmap

    def check(w, app):
        ghost = clip_drag_pixmap(QPixmap(), "A long source filename.OSV", 3.2)
        assert not ghost.isNull()
        assert ghost.toImage().pixelColor(10, 10).alpha() == 255
    home_window(1, check)
