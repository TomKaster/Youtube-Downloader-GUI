"""Persistent user preferences (stored in the Windows registry via QSettings)."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSettings

from ytdownloader import APP_NAME, ORG_NAME
from ytdownloader.core.tools import default_download_dir


class Settings:
    _DEFAULTS = {
        "output_dir": str(default_download_dir()),
        "max_concurrent": 2,
        "embed_thumbnail": True,
        "embed_metadata": True,
        "subtitles": False,
        "subtitle_langs": "en",
        "prefer_h264": False,
        "theme": "system",          # system | light | dark
        "auto_fetch": True,
        "playlist_subfolder": True,
        "last_mode": "video",
        "last_height": 0,            # 0 = best
        "last_audio_codec": "mp3",
        "last_bitrate": 192,
    }

    def __init__(self) -> None:
        self._q = QSettings(ORG_NAME, APP_NAME)

    def get(self, key: str):
        default = self._DEFAULTS[key]
        return self._q.value(key, default, type=type(default))

    def set(self, key: str, value) -> None:
        self._q.setValue(key, value)

    # Convenience accessors
    @property
    def output_dir(self) -> Path:
        p = Path(self.get("output_dir"))
        return p if str(p) else default_download_dir()

    @property
    def subtitle_lang_list(self) -> list[str]:
        return [s.strip() for s in self.get("subtitle_langs").split(",") if s.strip()] or ["en"]

    def geometry(self):
        return self._q.value("window_geometry")

    def save_geometry(self, data) -> None:
        self._q.setValue("window_geometry", data)
