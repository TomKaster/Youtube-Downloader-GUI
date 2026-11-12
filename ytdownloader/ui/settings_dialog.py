"""Settings window."""

from __future__ import annotations

import os

import yt_dlp.version
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout,
    QGroupBox, QHBoxLayout, QLabel, QLineEdit, QPushButton, QSpinBox, QVBoxLayout,
)

from ytdownloader import __version__
from ytdownloader.core.tools import ToolStatus, data_dir
from ytdownloader.ui.settings import Settings

THEMES = [("Match Windows", "system"), ("Light", "light"), ("Dark", "dark")]


class SettingsDialog(QDialog):
    def __init__(self, settings: Settings, tools: ToolStatus, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setMinimumWidth(520)
        self.s = settings

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(12)

        # --- Saving
        save = QGroupBox("Saving")
        f = QFormLayout(save)
        row = QHBoxLayout()
        self.folder = QLineEdit(str(settings.output_dir))
        browse = QPushButton("Browse…")
        browse.clicked.connect(self._browse)
        row.addWidget(self.folder, 1)
        row.addWidget(browse)
        f.addRow("Download folder", row)
        self.concurrent = QSpinBox()
        self.concurrent.setRange(1, 6)
        self.concurrent.setValue(settings.get("max_concurrent"))
        self.concurrent.setFixedWidth(80)
        f.addRow("Downloads at once", self.concurrent)
        self.playlist_folder = QCheckBox("Put playlist downloads in their own folder")
        self.playlist_folder.setChecked(settings.get("playlist_subfolder"))
        f.addRow("", self.playlist_folder)
        root.addWidget(save)

        # --- Files
        files = QGroupBox("Files")
        v = QVBoxLayout(files)
        self.thumb = QCheckBox("Embed thumbnail as cover art")
        self.thumb.setChecked(settings.get("embed_thumbnail"))
        self.meta = QCheckBox("Embed title, artist, chapters and other metadata")
        self.meta.setChecked(settings.get("embed_metadata"))
        self.h264 = QCheckBox("Prefer H.264 video (plays everywhere; may limit quality to 1080p)")
        self.h264.setChecked(settings.get("prefer_h264"))
        subs_row = QHBoxLayout()
        self.subs = QCheckBox("Embed subtitles in videos, languages:")
        self.subs.setChecked(settings.get("subtitles"))
        self.langs = QLineEdit(settings.get("subtitle_langs"))
        self.langs.setPlaceholderText("en, es, de")
        self.langs.setMaximumWidth(140)
        self.langs.setEnabled(self.subs.isChecked())
        self.subs.toggled.connect(self.langs.setEnabled)
        subs_row.addWidget(self.subs)
        subs_row.addWidget(self.langs)
        subs_row.addStretch()
        for w in (self.thumb, self.meta, self.h264):
            v.addWidget(w)
        v.addLayout(subs_row)
        root.addWidget(files)

        # --- Behaviour
        app = QGroupBox("App")
        f2 = QFormLayout(app)
        self.theme = QComboBox()
        for label, value in THEMES:
            self.theme.addItem(label, value)
        self.theme.setCurrentIndex(max(0, [t[1] for t in THEMES].index(settings.get("theme"))))
        f2.addRow("Theme", self.theme)
        self.auto_fetch = QCheckBox("Look up links automatically when pasted")
        self.auto_fetch.setChecked(settings.get("auto_fetch"))
        f2.addRow("", self.auto_fetch)
        root.addWidget(app)

        # --- About / diagnostics
        about = QGroupBox("About")
        a = QVBoxLayout(about)
        a.addWidget(QLabel(f"YT Downloader {__version__} · yt-dlp {yt_dlp.version.__version__}"))
        a.addWidget(self._tool_label("ffmpeg", tools.ffmpeg_dir,
                                     "needed for audio conversion and high-quality video"))
        a.addWidget(self._tool_label("Deno", tools.deno,
                                     "needed by yt-dlp to unlock YouTube downloads"))
        log_btn = QPushButton("Open log folder")
        log_btn.clicked.connect(lambda: os.startfile(data_dir()))  # noqa: S606
        row2 = QHBoxLayout()
        row2.addWidget(log_btn)
        row2.addStretch()
        a.addLayout(row2)
        root.addWidget(about)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Save).setObjectName("Primary")
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    @staticmethod
    def _tool_label(name: str, where: str | None, why: str) -> QLabel:
        if where:
            lbl = QLabel(f"✓  {name} found: {where}")
            lbl.setObjectName("Success")
        else:
            lbl = QLabel(f"⚠  {name} not found — {why}. See the README.")
            lbl.setObjectName("Warning")
        lbl.setWordWrap(True)
        return lbl

    def _browse(self) -> None:
        d = QFileDialog.getExistingDirectory(self, "Choose download folder", self.folder.text())
        if d:
            self.folder.setText(os.path.normpath(d))

    def _save(self) -> None:
        s = self.s
        s.set("output_dir", self.folder.text().strip() or str(s.output_dir))
        s.set("max_concurrent", self.concurrent.value())
        s.set("playlist_subfolder", self.playlist_folder.isChecked())
        s.set("embed_thumbnail", self.thumb.isChecked())
        s.set("embed_metadata", self.meta.isChecked())
        s.set("prefer_h264", self.h264.isChecked())
        s.set("subtitles", self.subs.isChecked())
        s.set("subtitle_langs", self.langs.text().strip() or "en")
        s.set("theme", self.theme.currentData())
        s.set("auto_fetch", self.auto_fetch.isChecked())
        self.accept()
