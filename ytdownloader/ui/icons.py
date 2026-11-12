"""App icon, drawn in code so no image files are needed.

`py -m ytdownloader.ui.icons assets\\icon.ico` writes a .ico for PyInstaller.
"""

from __future__ import annotations

import sys

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QIcon, QImage, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap


def _draw(size: int) -> QImage:
    img = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(Qt.GlobalColor.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    s = size / 64.0

    grad = QLinearGradient(0, 0, 0, size)
    grad.setColorAt(0, QColor("#f2585d"))
    grad.setColorAt(1, QColor("#c9343a"))
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QBrush(grad))
    p.drawRoundedRect(QRectF(2 * s, 2 * s, 60 * s, 60 * s), 14 * s, 14 * s)

    # Down arrow
    arrow = QPainterPath()
    arrow.moveTo(QPointF(27 * s, 13 * s))
    arrow.lineTo(QPointF(37 * s, 13 * s))
    arrow.lineTo(QPointF(37 * s, 30 * s))
    arrow.lineTo(QPointF(45 * s, 30 * s))
    arrow.lineTo(QPointF(32 * s, 44 * s))
    arrow.lineTo(QPointF(19 * s, 30 * s))
    arrow.lineTo(QPointF(27 * s, 30 * s))
    arrow.closeSubpath()
    p.setBrush(QColor("white"))
    p.drawPath(arrow)

    # Tray line
    pen = QPen(QColor("white"), 5 * s, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
    p.setPen(pen)
    p.drawLine(QPointF(18 * s, 51 * s), QPointF(46 * s, 51 * s))
    p.end()
    return img


def app_icon() -> QIcon:
    icon = QIcon()
    for size in (16, 20, 24, 32, 40, 48, 64, 128, 256):
        icon.addPixmap(QPixmap.fromImage(_draw(size)))
    return icon


def export_ico(path: str) -> bool:
    return _draw(256).save(path, "ICO")


if __name__ == "__main__":
    from PySide6.QtGui import QGuiApplication

    _app = QGuiApplication(sys.argv)
    target = sys.argv[1] if len(sys.argv) > 1 else "icon.ico"
    ok = export_ico(target)
    print(("Wrote " if ok else "Failed to write ") + target)
    sys.exit(0 if ok else 1)
