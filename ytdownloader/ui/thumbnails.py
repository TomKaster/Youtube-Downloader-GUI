"""Async thumbnail loading with a small in-memory cache."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QObject, QSize, Qt, QUrl
from PySide6.QtGui import QImage, QPainter, QPainterPath, QPixmap
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest


class ThumbnailLoader(QObject):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._net = QNetworkAccessManager(self)
        self._cache: dict[str, QImage] = {}
        self._waiting: dict[str, list[Callable[[QImage], None]]] = {}

    def load(self, url: str, callback: Callable[[QImage], None]) -> None:
        if not url:
            return
        if url in self._cache:
            callback(self._cache[url])
            return
        if url in self._waiting:
            self._waiting[url].append(callback)
            return
        self._waiting[url] = [callback]
        req = QNetworkRequest(QUrl(url))
        req.setAttribute(QNetworkRequest.Attribute.RedirectPolicyAttribute,
                         QNetworkRequest.RedirectPolicy.NoLessSafeRedirectPolicy)
        reply = self._net.get(req)
        reply.finished.connect(lambda r=reply, u=url: self._done(u, r))

    def _done(self, url: str, reply: QNetworkReply) -> None:
        callbacks = self._waiting.pop(url, [])
        img = QImage()
        if reply.error() == QNetworkReply.NetworkError.NoError:
            img.loadFromData(reply.readAll())
        reply.deleteLater()
        if img.isNull():
            return
        self._cache[url] = img
        for cb in callbacks:
            try:
                cb(img)
            except RuntimeError:
                pass  # the widget was deleted while we were downloading


def rounded_cover(img: QImage, size: QSize, radius: float, dpr: float = 1.0) -> QPixmap:
    """Scale/crop to fill `size` and round the corners."""
    w, h = int(size.width() * dpr), int(size.height() * dpr)
    scaled = img.scaled(w, h, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                        Qt.TransformationMode.SmoothTransformation)
    x = (scaled.width() - w) // 2
    y = (scaled.height() - h) // 2
    scaled = scaled.copy(x, y, w, h)

    out = QPixmap(w, h)
    out.fill(Qt.GlobalColor.transparent)
    p = QPainter(out)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    path = QPainterPath()
    path.addRoundedRect(0, 0, w, h, radius * dpr, radius * dpr)
    p.setClipPath(path)
    p.drawImage(0, 0, scaled)
    p.end()
    out.setDevicePixelRatio(dpr)
    return out
