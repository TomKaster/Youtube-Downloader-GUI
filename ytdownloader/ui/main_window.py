"""The main application window."""

from __future__ import annotations

import os
import re
from dataclasses import replace
from pathlib import Path

from PySide6.QtCore import QSize, Qt, QThreadPool, QTimer
from PySide6.QtGui import QCloseEvent, QGuiApplication, QImage, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication, QButtonGroup, QComboBox, QHBoxLayout, QLabel, QLineEdit, QListWidget,
    QListWidgetItem, QMainWindow, QMessageBox, QPushButton, QStackedWidget, QStatusBar,
    QVBoxLayout, QWidget,
)

from ytdownloader import APP_NAME
from ytdownloader.core.fetch import MediaInfo, format_duration, height_label
from ytdownloader.core.options import AUDIO_FORMATS, MP3_BITRATES, DownloadRequest, Mode
from ytdownloader.core.tools import ToolStatus
from ytdownloader.ui import theme
from ytdownloader.ui.icons import app_icon
from ytdownloader.ui.queue_item import QueueItem
from ytdownloader.ui.settings import Settings
from ytdownloader.ui.settings_dialog import SettingsDialog
from ytdownloader.ui.theme import Glyph
from ytdownloader.ui.thumbnails import ThumbnailLoader, rounded_cover
from ytdownloader.ui.widgets import ElidedLabel, card, icon_button
from ytdownloader.ui.workers import DownloadJob, FetchTask, JobState

PREVIEW_THUMB = QSize(176, 99)
DEFAULT_HEIGHTS = [2160, 1440, 1080, 720, 480, 360]
URL_RE = re.compile(r"^(https?://)?([\w-]+\.)+[a-z]{2,}(/\S*)?$", re.IGNORECASE)


def _safe_folder_name(name: str) -> str:
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name).strip(" .")
    return name[:120] or "Playlist"


class MainWindow(QMainWindow):
    def __init__(self, settings: Settings, tools: ToolStatus):
        super().__init__()
        self.s = settings
        self.tools = tools
        self.info: MediaInfo | None = None
        self._fetch_token = 0
        self._jobs: dict[int, tuple[DownloadJob, QueueItem, QListWidgetItem]] = {}

        self.pool = QThreadPool(self)
        self.pool.setMaxThreadCount(self.s.get("max_concurrent"))
        self.fetch_pool = QThreadPool(self)
        self.fetch_pool.setMaxThreadCount(2)
        self.thumbs = ThumbnailLoader(self)

        self._fetch_timer = QTimer(self, singleShot=True, interval=450)
        self._fetch_timer.timeout.connect(self._fetch)

        self.setWindowTitle(APP_NAME)
        self.setWindowIcon(app_icon())
        self.setMinimumSize(720, 560)
        self.setAcceptDrops(True)
        self._build()
        self._restore()
        self._refresh_status()
        self._update_queue_header()

        QShortcut(QKeySequence.StandardKey.Paste, self, activated=self._paste_shortcut)
        QShortcut(QKeySequence("Ctrl+,"), self, activated=self._open_settings)
        QGuiApplication.styleHints().colorSchemeChanged.connect(self._system_theme_changed)

    # ================================================================ layout
    def _build(self) -> None:
        central = QWidget(objectName="Central")
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(20, 16, 20, 12)
        root.setSpacing(14)

        # Header
        header = QHBoxLayout()
        logo = QLabel()
        logo.setPixmap(app_icon().pixmap(28, 28))
        title = QLabel(APP_NAME, objectName="AppTitle")
        header.addWidget(logo)
        header.addSpacing(4)
        header.addWidget(title)
        header.addStretch()
        gear = icon_button(Glyph.SETTINGS, "Settings (Ctrl+,)")
        gear.clicked.connect(self._open_settings)
        header.addWidget(gear)
        root.addLayout(header)

        # Link input + preview + options, all in one card
        top = card()
        tv = QVBoxLayout(top)
        tv.setContentsMargins(16, 16, 16, 16)
        tv.setSpacing(14)

        url_row = QHBoxLayout()
        url_row.setSpacing(8)
        self.url = QLineEdit(objectName="UrlInput")
        self.url.setPlaceholderText("Paste a YouTube link (video or playlist)…")
        self.url.setClearButtonEnabled(True)
        self.url.textEdited.connect(self._url_edited)
        self.url.returnPressed.connect(self._fetch)
        paste = QPushButton("Paste")
        paste.setToolTip("Paste link from clipboard")
        paste.clicked.connect(self._paste)
        url_row.addWidget(self.url, 1)
        url_row.addWidget(paste)
        tv.addLayout(url_row)

        # Preview
        prev = QHBoxLayout()
        prev.setSpacing(14)
        self.p_thumb = QLabel(objectName="Thumb")
        self.p_thumb.setFixedSize(PREVIEW_THUMB)
        self.p_thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        prev.addWidget(self.p_thumb)
        pv = QVBoxLayout()
        pv.setSpacing(4)
        self.p_title = ElidedLabel("", )
        self.p_title.setObjectName("MediaTitle")
        self.p_meta = ElidedLabel("")
        self.p_meta.setObjectName("Muted")
        self.p_status = QLabel("")
        self.p_status.setObjectName("Muted")
        self.p_status.setWordWrap(True)
        pv.addStretch()
        pv.addWidget(self.p_title)
        pv.addWidget(self.p_meta)
        pv.addWidget(self.p_status)
        pv.addStretch()
        prev.addLayout(pv, 1)
        tv.addLayout(prev)

        # Options
        opts = QHBoxLayout()
        opts.setSpacing(8)
        self.btn_video = QPushButton("Video", objectName="SegmentLeft", checkable=True)
        self.btn_audio = QPushButton("Audio only", objectName="SegmentRight", checkable=True)
        self.mode_group = QButtonGroup(self)
        self.mode_group.setExclusive(True)
        for b in (self.btn_video, self.btn_audio):
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            self.mode_group.addButton(b)
        self.mode_group.buttonToggled.connect(lambda *_: self._mode_changed())
        seg = QHBoxLayout()
        seg.setSpacing(0)
        seg.addWidget(self.btn_video)
        seg.addWidget(self.btn_audio)
        opts.addLayout(seg)
        opts.addSpacing(8)

        self.quality = QComboBox()
        self.quality.setMinimumWidth(150)
        self.quality.setToolTip("Maximum video resolution")
        self.audio_fmt = QComboBox()
        for label, codec in AUDIO_FORMATS.items():
            self.audio_fmt.addItem(label, codec)
        self.audio_fmt.currentIndexChanged.connect(self._audio_fmt_changed)
        self.bitrate = QComboBox()
        for br in MP3_BITRATES:
            self.bitrate.addItem(f"{br} kbps", br)
        self.bitrate.setToolTip("MP3 bitrate")
        opts.addWidget(self.quality)
        opts.addWidget(self.audio_fmt)
        opts.addWidget(self.bitrate)
        opts.addStretch()

        self.btn_download = QPushButton("Download", objectName="Primary")
        self.btn_download.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_download.clicked.connect(self._start_download)
        opts.addWidget(self.btn_download)
        tv.addLayout(opts)
        root.addWidget(top)

        # Queue
        qh = QHBoxLayout()
        qh.addWidget(QLabel("Downloads", objectName="SectionTitle"))
        self.q_count = QLabel("", objectName="Muted")
        qh.addWidget(self.q_count)
        qh.addStretch()
        open_dir = QPushButton("Open folder")
        open_dir.clicked.connect(self._open_output_dir)
        self.btn_clear = QPushButton("Clear finished")
        self.btn_clear.clicked.connect(self._clear_finished)
        qh.addWidget(open_dir)
        qh.addWidget(self.btn_clear)
        root.addLayout(qh)

        self.queue = QListWidget(objectName="Queue")
        self.queue.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        self.queue.setVerticalScrollMode(QListWidget.ScrollMode.ScrollPerPixel)
        self.queue.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        empty = QWidget()
        ev = QVBoxLayout(empty)
        ev.addStretch()
        ic = QLabel(Glyph.DOWNLOAD, objectName="EmptyIcon", alignment=Qt.AlignmentFlag.AlignCenter)
        msg = QLabel("Your downloads will show up here.\nTip: you can also drag a link onto this window.",
                     objectName="EmptyState", alignment=Qt.AlignmentFlag.AlignCenter)
        ev.addWidget(ic)
        ev.addWidget(msg)
        ev.addStretch()

        self.queue_stack = QStackedWidget()
        self.queue_stack.addWidget(empty)
        self.queue_stack.addWidget(self.queue)
        root.addWidget(self.queue_stack, 1)

        # Status bar
        sb = QStatusBar()
        sb.setSizeGripEnabled(False)
        self.setStatusBar(sb)
        self.lbl_folder = QLabel()
        self.lbl_folder.setCursor(Qt.CursorShape.PointingHandCursor)
        self.lbl_folder.setToolTip("Click to change in Settings")
        self.lbl_folder.mousePressEvent = lambda _e: self._open_settings()
        self.lbl_tools = QLabel(objectName="Warning")
        sb.addWidget(self.lbl_folder, 1)
        sb.addPermanentWidget(self.lbl_tools)

        self._reset_preview()

    def _restore(self) -> None:
        if (g := self.s.geometry()) is not None:
            self.restoreGeometry(g)
        else:
            self.resize(860, 720)
        (self.btn_audio if self.s.get("last_mode") == "audio" else self.btn_video).setChecked(True)
        i = self.audio_fmt.findData(self.s.get("last_audio_codec"))
        self.audio_fmt.setCurrentIndex(max(i, 0))
        i = self.bitrate.findData(self.s.get("last_bitrate"))
        self.bitrate.setCurrentIndex(max(i, 0) if i >= 0 else 1)
        self._fill_quality(DEFAULT_HEIGHTS)
        self._mode_changed()

    # =============================================================== helpers
    @property
    def mode(self) -> Mode:
        return Mode.AUDIO if self.btn_audio.isChecked() else Mode.VIDEO

    def _refresh_status(self) -> None:
        self.lbl_folder.setText(f"Saving to  {self.s.output_dir}")
        missing = []
        if not self.tools.has_ffmpeg:
            missing.append("ffmpeg")
        if not self.tools.has_deno:
            missing.append("Deno")
        if missing:
            self.lbl_tools.setText(f"{' and '.join(missing)} not found — see Settings")
        else:
            self.lbl_tools.setText("")

    def _fill_quality(self, heights: list[int]) -> None:
        want = self.s.get("last_height")
        self.quality.blockSignals(True)
        self.quality.clear()
        top = f" ({height_label(heights[0])})" if heights and self.info and not self.info.is_playlist else ""
        self.quality.addItem(f"Best quality{top}", 0)
        for h in heights:
            if h >= 144:
                self.quality.addItem(height_label(h), h)
        idx = self.quality.findData(want)
        if idx < 0 and want:
            # Pick the best height not above the remembered one
            for i in range(1, self.quality.count()):
                if self.quality.itemData(i) <= want:
                    idx = i
                    break
        self.quality.setCurrentIndex(max(idx, 0))
        self.quality.blockSignals(False)

    def _mode_changed(self) -> None:
        video = self.mode is Mode.VIDEO
        self.quality.setVisible(video)
        self.audio_fmt.setVisible(not video)
        self.bitrate.setVisible(not video and self.audio_fmt.currentData() == "mp3")

    def _audio_fmt_changed(self) -> None:
        self._mode_changed()

    def _set_preview_thumb(self, img: QImage | None) -> None:
        if img is None:
            self.p_thumb.clear()
            self.p_thumb.setText("")
            return
        self.p_thumb.setPixmap(rounded_cover(img, PREVIEW_THUMB, 8, self.devicePixelRatioF()))

    def _reset_preview(self) -> None:
        self.info = None
        self._set_preview_thumb(None)
        self.p_thumb.setText(f"<span style='font-family:\"{theme.icon_font_family()}\"; font-size:26pt;'>"
                             f"{Glyph.VIDEO}</span>")
        self.p_title.setText("Nothing selected yet")
        self.p_meta.setText("Paste a link above, then choose Video or Audio.")
        self.p_status.setText("")
        self.btn_download.setText("Download")
        self._fill_quality(DEFAULT_HEIGHTS)

    def _set_status(self, text: str, kind: str = "Muted") -> None:
        self.p_status.setObjectName(kind)
        self.p_status.setText(text)
        self.p_status.style().unpolish(self.p_status)
        self.p_status.style().polish(self.p_status)

    # ================================================================ fetch
    def _url_edited(self, text: str) -> None:
        self.info = None
        self.btn_download.setText("Download")
        if self.s.get("auto_fetch") and URL_RE.match(text.strip()):
            self._fetch_timer.start()
        elif not text.strip():
            self._fetch_token += 1
            self._reset_preview()

    def _paste(self) -> None:
        text = QGuiApplication.clipboard().text().strip()
        if not text:
            return
        self.url.setText(text)
        self.url.setFocus()
        self._url_edited(text)
        if not self.s.get("auto_fetch"):
            return
        self._fetch_timer.stop()
        self._fetch()

    def _paste_shortcut(self) -> None:
        if self.url.hasFocus():
            self.url.paste()
        else:
            self._paste()

    def _fetch(self) -> None:
        self._fetch_timer.stop()
        url = self.url.text().strip()
        if not url:
            return
        self._fetch_token += 1
        token = self._fetch_token
        self._set_preview_thumb(None)
        self.p_title.setText("Looking up link…")
        self.p_meta.setText(url)
        self._set_status("")
        task = FetchTask(token, url)
        task.signals.done.connect(self._fetch_done)
        task.signals.failed.connect(self._fetch_failed)
        self.fetch_pool.start(task)

    def _fetch_done(self, token: int, info: MediaInfo) -> None:
        if token != self._fetch_token:
            return
        self.info = info
        self.p_title.setText(info.title)
        if info.is_playlist:
            n = len(info.entries)
            bits = [f"Playlist · {n} video{'s' if n != 1 else ''}"]
            if info.uploader:
                bits.append(info.uploader)
            self.p_meta.setText(" · ".join(bits))
            self.btn_download.setText(f"Download all ({n})")
            self._fill_quality(DEFAULT_HEIGHTS)
        else:
            bits = [b for b in (info.uploader, format_duration(info.duration)) if b]
            self.p_meta.setText(" · ".join(bits))
            self.btn_download.setText("Download")
            self._fill_quality(info.heights or DEFAULT_HEIGHTS)
        self._set_status("")
        self.thumbs.load(info.thumbnail or "", lambda img, t=token: (
            self._set_preview_thumb(img) if t == self._fetch_token else None))

    def _fetch_failed(self, token: int, message: str) -> None:
        if token != self._fetch_token:
            return
        self.info = None
        self.p_title.setText("Couldn't read that link")
        self.p_meta.setText(self.url.text().strip())
        hint = ""
        if not self.tools.has_deno:
            hint = "\nDeno isn't installed, which YouTube now requires — see the README."
        self._set_status(message + hint, "Error")

    # ============================================================= download
    def _base_request(self, url: str) -> DownloadRequest:
        mode = self.mode
        return DownloadRequest(
            url=url,
            mode=mode,
            output_dir=self.s.output_dir,
            max_height=self.quality.currentData() or None,
            prefer_h264=self.s.get("prefer_h264"),
            subtitles=self.s.get("subtitles"),
            subtitle_langs=self.s.subtitle_lang_list,
            audio_codec=self.audio_fmt.currentData(),
            audio_bitrate=self.bitrate.currentData(),
            embed_thumbnail=self.s.get("embed_thumbnail"),
            embed_metadata=self.s.get("embed_metadata"),
        )

    def _summary(self, req: DownloadRequest) -> str:
        if req.mode is Mode.VIDEO:
            q = height_label(req.max_height) if req.max_height else "Best quality"
            return f"Video · {q}"
        label = self.audio_fmt.currentText().split(" ")[0]
        if req.audio_codec == "mp3":
            return f"Audio · MP3 {req.audio_bitrate} kbps"
        return f"Audio · {label}"

    def _start_download(self) -> None:
        url = self.url.text().strip()
        if not url:
            self.url.setFocus()
            self._set_status("Paste a link first.", "Warning")
            return
        if self.mode is Mode.AUDIO and not self.tools.has_ffmpeg:
            QMessageBox.warning(
                self, "ffmpeg needed",
                "Converting to audio needs ffmpeg, which wasn't found.\n\n"
                "Put ffmpeg.exe next to this program (or in a bin folder beside it), "
                "or install it and add it to PATH.")
            return

        # Remember choices for next time
        self.s.set("last_mode", self.mode.value)
        self.s.set("last_height", self.quality.currentData() or 0)
        self.s.set("last_audio_codec", self.audio_fmt.currentData())
        self.s.set("last_bitrate", self.bitrate.currentData())

        base = self._base_request(url)
        # self.info is reset whenever the link text changes, so it always
        # belongs to the URL currently in the box.
        info = self.info

        if info and info.is_playlist:
            if not info.entries:
                self._set_status("That playlist has no videos I can download.", "Warning")
                return
            sub = _safe_folder_name(info.title) if self.s.get("playlist_subfolder") else None
            for e in info.entries:
                self._add_job(replace(base, url=e.url, subfolder=sub, title_hint=e.title), None)
        else:
            req = replace(base, title_hint=info.title if info else None)
            self._add_job(req, info.thumbnail if info else None)

        self._fetch_token += 1
        self.url.clear()
        self._reset_preview()
        self.url.setFocus()

    def _add_job(self, req: DownloadRequest, thumb_url: str | None) -> None:
        job = DownloadJob(req, self.tools.ffmpeg_dir)
        item = QueueItem(job.id, req.title_hint or req.url, self._summary(req))
        item.output_dir = Path(req.output_dir) / (req.subfolder or "")
        lw = QListWidgetItem()
        lw.setSizeHint(item.sizeHint())
        self.queue.addItem(lw)
        self.queue.setItemWidget(lw, item)
        item.cancel_requested.connect(self._cancel_job)
        item.retry_requested.connect(self._retry_job)
        item.remove_requested.connect(self._remove_job)
        if thumb_url:
            self.thumbs.load(thumb_url, item.set_thumbnail)
        self._register(job, item, lw)
        self.queue_stack.setCurrentIndex(1)
        self.queue.scrollToBottom()

    def _register(self, job: DownloadJob, item: QueueItem, lw: QListWidgetItem) -> None:
        self._jobs[job.id] = (job, item, lw)
        item.job_id = job.id
        job.signals.state.connect(self._job_state)
        job.signals.progress.connect(self._job_progress)
        job.signals.meta.connect(self._job_meta)
        job.signals.finished.connect(self._job_finished)
        item.set_state(JobState.QUEUED, "")
        self.pool.start(job)
        self._update_queue_header()

    # Job signal handlers (main thread)
    def _job_state(self, job_id: int, state: str, text: str) -> None:
        if job_id not in self._jobs:
            return
        _job, item, _lw = self._jobs[job_id]
        st = JobState(state)
        item.set_state(st, text)
        if st is JobState.DONE and not self.isActiveWindow():
            QApplication.alert(self)
        self._update_queue_header()

    def _job_progress(self, job_id: int, frac: float, text: str) -> None:
        if job_id in self._jobs:
            self._jobs[job_id][1].set_progress(frac, text)

    def _job_meta(self, job_id: int, title: str, thumb: str) -> None:
        if job_id not in self._jobs:
            return
        item = self._jobs[job_id][1]
        item.set_title(title)
        if thumb and item.thumb.pixmap().isNull():
            self.thumbs.load(thumb, item.set_thumbnail)

    def _job_finished(self, job_id: int, path: str) -> None:
        if job_id in self._jobs:
            self._jobs[job_id][1].file_path = path or None

    def _cancel_job(self, job_id: int) -> None:
        if job_id not in self._jobs:
            return
        job, item, _ = self._jobs[job_id]
        job.cancel()
        if self.pool.tryTake(job):
            # It hadn't started yet
            item.set_state(JobState.CANCELLED, "Cancelled")
        else:
            item.detail.setText(f"{item.summary} · Cancelling…")
        self._update_queue_header()

    def _retry_job(self, job_id: int) -> None:
        if job_id not in self._jobs:
            return
        old, item, lw = self._jobs.pop(job_id)
        job = DownloadJob(old.request, self.tools.ffmpeg_dir)
        self._register(job, item, lw)

    def _remove_job(self, job_id: int) -> None:
        if job_id not in self._jobs:
            return
        job, item, lw = self._jobs[job_id]
        if item.state.active:
            return
        del self._jobs[job_id]
        self.queue.takeItem(self.queue.row(lw))
        item.deleteLater()
        self._update_queue_header()

    def _clear_finished(self) -> None:
        for jid, (_j, item, _lw) in list(self._jobs.items()):
            if not item.state.active:
                self._remove_job(jid)

    def _update_queue_header(self) -> None:
        total = len(self._jobs)
        active = sum(1 for _j, it, _ in self._jobs.values() if it.state.active)
        done = sum(1 for _j, it, _ in self._jobs.values() if it.state is JobState.DONE)
        if total == 0:
            self.q_count.setText("")
            self.queue_stack.setCurrentIndex(0)
        else:
            parts = []
            if active:
                parts.append(f"{active} in progress")
            if done:
                parts.append(f"{done} done")
            self.q_count.setText(" · ".join(parts))
        self.btn_clear.setEnabled(total - active > 0)
        if active:
            self.setWindowTitle(f"{APP_NAME} — {active} downloading")
        else:
            self.setWindowTitle(APP_NAME)

    # ================================================================ misc
    def _open_output_dir(self) -> None:
        d = self.s.output_dir
        d.mkdir(parents=True, exist_ok=True)
        os.startfile(d)  # noqa: S606

    def _open_settings(self) -> None:
        dlg = SettingsDialog(self.s, self.tools, self)
        if dlg.exec():
            self.pool.setMaxThreadCount(self.s.get("max_concurrent"))
            theme.apply_theme(QApplication.instance(), self.s.get("theme"))
            self._refresh_status()

    def _system_theme_changed(self, *_):
        if self.s.get("theme") == "system":
            theme.apply_theme(QApplication.instance(), "system")

    # Drag & drop a link onto the window
    def dragEnterEvent(self, e):  # noqa: N802
        md = e.mimeData()
        if md.hasUrls() or md.hasText():
            e.acceptProposedAction()

    def dropEvent(self, e):  # noqa: N802
        md = e.mimeData()
        text = md.urls()[0].toString() if md.hasUrls() else md.text()
        text = text.strip()
        if text:
            self.url.setText(text)
            self._url_edited(text)
            self._fetch()

    def closeEvent(self, e: QCloseEvent) -> None:  # noqa: N802
        active = [j for j, it, _ in self._jobs.values() if it.state.active]
        if active:
            r = QMessageBox.question(
                self, "Downloads in progress",
                f"{len(active)} download(s) are still running. Stop them and quit?")
            if r != QMessageBox.StandardButton.Yes:
                e.ignore()
                return
            for j in active:
                j.cancel()
            self.pool.clear()
            self.pool.waitForDone(5000)
        self.s.save_geometry(self.saveGeometry())
        super().closeEvent(e)
