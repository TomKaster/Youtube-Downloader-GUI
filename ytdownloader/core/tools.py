"""Locating the external programs yt-dlp relies on (ffmpeg, Deno)."""

from __future__ import annotations

import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path


def app_dir() -> Path:
    """Folder the program lives in (next to the .exe when packaged)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parents[2]


def bundle_dir() -> Path | None:
    """Temp folder PyInstaller unpacks bundled files into, if running packaged."""
    meipass = getattr(sys, "_MEIPASS", None)
    return Path(meipass) if meipass else None


def add_bundled_tools_to_path() -> None:
    """Put bundled / side-by-side deno.exe and ffmpeg.exe ahead of the system PATH.

    Checked in order: files packed into the .exe, a bin\\ folder next to the
    program (where build.ps1 downloads them), and the program folder itself.
    """
    candidates = []
    if (b := bundle_dir()) is not None:
        candidates.append(b)
    candidates += [app_dir() / "bin", app_dir()]
    dirs = [str(d) for d in candidates if d.is_dir()]
    os.environ["PATH"] = os.pathsep.join(dirs + [os.environ.get("PATH", "")])


@dataclass(frozen=True)
class ToolStatus:
    ffmpeg_dir: str | None
    deno: str | None

    @property
    def has_ffmpeg(self) -> bool:
        return self.ffmpeg_dir is not None

    @property
    def has_deno(self) -> bool:
        return self.deno is not None


def detect_tools() -> ToolStatus:
    ffmpeg = shutil.which("ffmpeg")
    return ToolStatus(
        ffmpeg_dir=str(Path(ffmpeg).parent) if ffmpeg else None,
        deno=shutil.which("deno"),
    )


def default_download_dir() -> Path:
    return Path.home() / "Downloads"


def data_dir() -> Path:
    """Per-user folder for the log file."""
    base = os.environ.get("LOCALAPPDATA") or str(Path.home())
    d = Path(base) / "YT Downloader"
    d.mkdir(parents=True, exist_ok=True)
    return d
