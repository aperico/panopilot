from __future__ import annotations

from pathlib import Path


def _assets_dir() -> Path:
    return Path(__file__).resolve().parent / "assets"


def application_icon_path() -> Path:
    return _assets_dir() / "panopilot_icon.svg"


def wordmark_logo_path() -> Path:
    return _assets_dir() / "panopilot_logo.svg"


def set_application_icon(app) -> None:
    if app is None:
        return
    from PySide6.QtGui import QIcon
    app.setWindowIcon(QIcon(str(application_icon_path())))


def render_svg_pixmap(svg_path, *, width: int, height: int):
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QPainter, QPixmap
    from PySide6.QtSvg import QSvgRenderer

    pixmap = QPixmap(width, height)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    renderer = QSvgRenderer(str(svg_path))
    renderer.render(painter)
    painter.end()
    return pixmap
