"""Native drag feedback for the Project arrangement timeline."""


def clip_drag_pixmap(thumbnail, title, duration):
    """A bounded thumbnail card, independent of the timeline's zoom level."""
    from PySide6.QtCore import Qt, QRect
    from PySide6.QtGui import QColor, QFont, QPainter, QPixmap

    pixmap = QPixmap(224, 152)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    try:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QColor("#8bb4ff"))
        painter.setBrush(QColor("#202b40"))
        painter.drawRoundedRect(1, 1, 222, 150, 8, 8)
        image_rect = QRect(8, 8, 208, 98)
        painter.fillRect(image_rect, QColor("#111318"))
        if not thumbnail.isNull():
            image = thumbnail.scaled(image_rect.size(), Qt.AspectRatioMode.KeepAspectRatio,
                                     Qt.TransformationMode.SmoothTransformation)
            painter.drawPixmap(image_rect.center() - image.rect().center(), image)
        else:
            painter.setPen(QColor("#c8ced7"))
            painter.drawText(image_rect, Qt.AlignmentFlag.AlignCenter, "Video clip")
        painter.setFont(QFont("Sans Serif", 10))
        painter.setPen(QColor("#ffffff"))
        title = painter.fontMetrics().elidedText(str(title), Qt.TextElideMode.ElideMiddle, 208)
        painter.drawText(QRect(8, 110, 208, 18), Qt.AlignmentFlag.AlignLeft, title)
        painter.setPen(QColor("#bbc9df"))
        painter.drawText(QRect(8, 130, 208, 18), Qt.AlignmentFlag.AlignLeft,
                         f"{float(duration):.2f}s · Move clip")
    finally:
        painter.end()
    return pixmap
