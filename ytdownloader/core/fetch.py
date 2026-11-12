"""Look up a URL's title, thumbnail and available qualities without downloading."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

import yt_dlp

log = logging.getLogger(__name__)

_ANSI = re.compile(r"\x1b\[[0-9;]*m")


def clean_error(err: BaseException | str) -> str:
    """Make yt-dlp error text readable in a dialog."""
    text = _ANSI.sub("", str(err)).strip()
    text = re.sub(r"^ERROR:\s*", "", text)
    # "[youtube] abc123: Video unavailable" -> "Video unavailable"
    text = re.sub(r"^\[[^\]]+\]\s*[\w-]+:\s*", "", text)
    return text or "Unknown error"


class YdlLogger:
    """Routes yt-dlp's output into the app log instead of a console."""

    def debug(self, msg: str) -> None:
        # yt-dlp sends info-level messages to debug() too, prefixed with [x]
        log.debug(_ANSI.sub("", msg))

    def info(self, msg: str) -> None:
        log.info(_ANSI.sub("", msg))

    def warning(self, msg: str) -> None:
        log.warning(_ANSI.sub("", msg))

    def error(self, msg: str) -> None:
        log.error(_ANSI.sub("", msg))


@dataclass
class PlaylistEntry:
    url: str
    title: str


@dataclass
class MediaInfo:
    url: str
    title: str
    is_playlist: bool = False
    uploader: str | None = None
    duration: float | None = None
    thumbnail: str | None = None
    heights: list[int] = field(default_factory=list)   # available video heights, desc
    entries: list[PlaylistEntry] = field(default_factory=list)


def _best_thumbnail(info: dict) -> str | None:
    thumbs = info.get("thumbnails") or []
    # Prefer a mid-size jpg (fast to load) over the multi-MB maxres webp.
    for t in reversed(thumbs):
        u = t.get("url", "")
        if "hqdefault" in u or "mqdefault" in u:
            return u
    if thumbs:
        return thumbs[-1].get("url")
    return info.get("thumbnail")


def _entry_url(entry: dict) -> str | None:
    url = entry.get("url") or entry.get("webpage_url")
    if url and not url.startswith("http") and entry.get("ie_key") == "Youtube":
        url = f"https://www.youtube.com/watch?v={url}"
    return url


def fetch_info(url: str) -> MediaInfo:
    """Blocking. Raises yt_dlp.utils.DownloadError on failure."""
    opts = {
        "quiet": True,
        "noprogress": True,
        "skip_download": True,
        "noplaylist": True,
        "extract_flat": "in_playlist",
        "logger": YdlLogger(),
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)

    if info.get("_type") == "playlist" or "entries" in info:
        entries = []
        for e in info.get("entries") or []:
            if not e:
                continue
            u = _entry_url(e)
            if u:
                entries.append(PlaylistEntry(url=u, title=e.get("title") or u))
        thumb = _best_thumbnail(info)
        if not thumb and info.get("entries"):
            first = next((e for e in info["entries"] if e), None)
            thumb = _best_thumbnail(first) if first else None
        return MediaInfo(
            url=url,
            title=info.get("title") or "Playlist",
            is_playlist=True,
            uploader=info.get("uploader") or info.get("channel"),
            thumbnail=thumb,
            entries=entries,
        )

    heights = sorted(
        {f["height"] for f in info.get("formats") or []
         if f.get("height") and f.get("vcodec") not in (None, "none")},
        reverse=True,
    )
    return MediaInfo(
        url=info.get("webpage_url") or url,
        title=info.get("title") or url,
        uploader=info.get("uploader") or info.get("channel"),
        duration=info.get("duration"),
        thumbnail=_best_thumbnail(info),
        heights=heights,
    )


def format_duration(seconds: float | None) -> str:
    if not seconds:
        return ""
    s = int(seconds)
    h, rem = divmod(s, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def height_label(h: int) -> str:
    names = {4320: "8K", 2160: "4K", 1440: "1440p", 1080: "1080p", 720: "720p",
             480: "480p", 360: "360p", 240: "240p", 144: "144p"}
    return names.get(h, f"{h}p")
