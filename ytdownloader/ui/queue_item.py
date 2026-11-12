"""One row in the downloads list."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QProgressBar, QVBoxLayout

from ytdownloader.ui.theme import Glyph
from ytdownloader.ui.thumbnails import rounded_cover
from ytdownloader.ui.widgets import ElidedLabel, icon_button, repolish
from ytdownloader.ui.workers import JobState

THUMB = QSize(112, 63)


class QueueItem(QFrame):
    cancel_requested = Signal(int)
    retry_requested = Signal(int)
    remove_requested = Signal(int)

    def __init__(self, job_id: int, title: str, summary: str, parent=None):
        super().__init__(parent)
        self.setObjectName("Card")
        self.job_id = job_id
        self.state = JobState.QUEUED
        self.file_path: str | None = None
        self.output_dir: Path | None = None

        row = QHBoxLayout(self)
        row.setContentsMargins(10, 10, 10, 10)
        row.setSpacing(12)

        self.thumb = QLabel()
        self.thumb.setObjectName("Thumb")
        self.thumb.setFixedSize(THUMB)
        self.thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        row.addWidget(self.thumb)

        mid = QVBoxLayout()
        mid.setSpacing(4)
        self.title = ElidedLabel(title)
        self.title.setStyleSheet("font-weight: 600;")
        self.summary = summary
        self.detail = ElidedLabel(summary + " · Waiting…")
        self.detail.setObjectName("Muted")
        self.bar = QProgressBar()
        self.bar.setRange(0, 1000)
        self.bar.setValue(0)
        self.bar.setTextVisible(False)
        self.bar.setProperty("state", "muted")
        mid.addStretch()
        mid.addWidget(self.title)
        mid.addWidget(self.detail)
        mid.addSpacing(2)
        mid.addWidget(self.bar)
        mid.addStretch()
        row.addLayout(mid, 1)

        self.btn_open = icon_button(Glyph.PLAY, "Open file")
        self.btn_folder = icon_button(Glyph.FOLDER, "Show in folder")
        self.btn_retry = icon_button(Glyph.RETRY, "Try again")
        self.btn_cancel = icon_button(Glyph.CANCEL, "Cancel")
        self.btn_remove = icon_button(Glyph.CANCEL, "Remove from list")
        self.btn_open.clicked.connect(self._open_file)
        self.btn_folder.clicked.connect(self._show_in_folder)
        self.btn_retry.clicked.connect(lambda: self.retry_requested.emit(self.job_id))
        self.btn_cancel.clicked.connect(lambda: self.cancel_requested.emit(self.job_id))
        self.btn_remove.clicked.connect(lambda: self.remove_requested.emit(self.job_id))
        for b in (self.btn_open, self.btn_folder, self.btn_retry, self.btn_cancel, self.btn_remove):
            row.addWidget(b, 0, Qt.AlignmentFlag.AlignVCenter)
        self._update_buttons()

    # ------------------------------------------------------------- updates
    def set_thumbnail(self, img: QImage) -> None:
        self.thumb.setPixmap(rounded_cover(img, THUMB, 6, self.devicePixelRatioF()))

    def set_title(self, title: str) -> None:
        if title:
            self.title.setText(title)

    def set_progress(self, frac: float, text: str) -> None:
        if self.state is JobState.PROCESSING:
            # A pre-download step (e.g. thumbnail prep) finished; bytes are flowing now.
            self.state = JobState.DOWNLOADING
            self.bar.setRange(0, 1000)
        if self.state is not JobState.DOWNLOADING:
            return
        if frac < 0:
            self.bar.setRange(0, 0)  # busy animation
        else:
            if self.bar.maximum() == 0:
                self.bar.setRange(0, 1000)
            self.bar.setValue(int(frac * 1000))
        if text:
            self.detail.setText(f"{self.summary} · {text}")

    def set_state(self, state: JobState, text: str) -> None:
        self.state = state
        self.detail.setObjectName("Muted")
        bar_state = ""
        if state is JobState.QUEUED:
            self.bar.setRange(0, 1000)
            self.bar.setValue(0)
            bar_state = "muted"
            self.detail.setText(f"{self.summary} · Waiting…")
        elif state is JobState.DOWNLOADING:
            self.detail.setText(f"{self.summary} · {text}")
        elif state is JobState.PROCESSING:
            self.bar.setRange(0, 0)
            self.detail.setText(f"{self.summary} · {text}")
        elif state is JobState.DONE:
            self.bar.setRange(0, 1000)
            self.bar.setValue(1000)
            bar_state = "done"
            name = Path(self.file_path).name if self.file_path else "Done"
            self.detail.setObjectName("Success")
            self.detail.setText(f"Saved · {name}")
        elif state is JobState.FAILED:
            self.bar.setRange(0, 1000)
            self.bar.setValue(1000)
            bar_state = "error"
            self.detail.setObjectName("Error")
            self.detail.setText(text or "Failed")
            self.detail.setToolTip(text)
        elif state is JobState.CANCELLED:
            self.bar.setRange(0, 1000)
            bar_state = "muted"
            self.detail.setText(f"{self.summary} · Cancelled")
        self.bar.setProperty("state", bar_state)
        repolish(self.bar)
        repolish(self.detail)
        self._update_buttons()

    def _update_buttons(self) -> None:
        s = self.state
        done = s is JobState.DONE
        self.btn_open.setVisible(done and bool(self.file_path))
        self.btn_folder.setVisible(done)
        self.btn_retry.setVisible(s in (JobState.FAILED, JobState.CANCELLED))
        self.btn_cancel.setVisible(s.active)
        self.btn_remove.setVisible(not s.active)

    # ------------------------------------------------------------- actions
    def _open_file(self) -> None:
        if self.file_path and Path(self.file_path).exists():
            os.startfile(self.file_path)  # noqa: S606

    def _show_in_folder(self) -> None:
        if self.file_path and Path(self.file_path).exists():
            subprocess.Popen(["explorer", "/select,", os.path.normpath(self.file_path)])  # noqa: S603,S607
        elif self.output_dir and self.output_dir.exists():
            os.startfile(self.output_dir)  # noqa: S606

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(400, THUMB.height() + 22)
