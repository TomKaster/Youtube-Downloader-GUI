"""Small reusable widgets."""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import QFrame, QLabel, QSizePolicy, QToolButton


class ElidedLabel(QLabel):
    """Single-line label that shows '…' instead of growing the window."""

    def __init__(self, text: str = "", parent=None):
        super().__init__(parent)
        self._full = text
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.setText(text)

    def setText(self, text: str) -> None:  # noqa: N802 (Qt naming)
        self._full = text or ""
        self.setToolTip(self._full if len(self._full) > 40 else "")
        self._elide()

    def fullText(self) -> str:  # noqa: N802
        return self._full

    def resizeEvent(self, e):  # noqa: N802
        super().resizeEvent(e)
        self._elide()

    def _elide(self) -> None:
        fm = self.fontMetrics()
        super().setText(fm.elidedText(self._full, Qt.TextElideMode.ElideRight, max(self.width(), 20)))

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        return QSize(20, super().minimumSizeHint().height())


def icon_button(glyph: str, tooltip: str, parent=None) -> QToolButton:
    b = QToolButton(parent)
    b.setObjectName("IconButton")
    b.setText(glyph)
    b.setToolTip(tooltip)
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    b.setAutoRaise(True)
    return b


def card(parent=None) -> QFrame:
    f = QFrame(parent)
    f.setObjectName("Card")
    return f


def repolish(w) -> None:
    w.style().unpolish(w)
    w.style().polish(w)
