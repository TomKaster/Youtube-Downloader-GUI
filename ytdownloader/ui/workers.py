"""Background work: metadata lookups and downloads run on a thread pool."""

from __future__ import annotations

import itertools
import logging
import shutil
import tempfile
import threading
import time
from enum import Enum

import yt_dlp
from PySide6.QtCore import QObject, QRunnable, Signal
from yt_dlp.postprocessor import PostProcessor
from yt_dlp.utils import DownloadCancelled, DownloadError

from ytdownloader.core.fetch import MediaInfo, YdlLogger, clean_error, fetch_info
from ytdownloader.core.options import DownloadRequest, build_ydl_options, output_dir_for
from ytdownloader.core.tools import data_dir

log = logging.getLogger(__name__)
_ids = itertools.count(1)


# ---------------------------------------------------------------- fetching
class FetchSignals(QObject):
    done = Signal(int, object)      # token, MediaInfo
    failed = Signal(int, str)       # token, message


class FetchTask(QRunnable):
    def __init__(self, token: int, url: str):
        super().__init__()
        self.token, self.url = token, url
        self.signals = FetchSignals()

    def run(self) -> None:
        try:
            info: MediaInfo = fetch_info(self.url)
            self.signals.done.emit(self.token, info)
        except Exception as e:  # noqa: BLE001 - anything yt-dlp throws goes to the UI
            log.info("Fetch failed for %s: %s", self.url, e)
            self.signals.failed.emit(self.token, clean_error(e))


# --------------------------------------------------------------- downloading
class JobState(str, Enum):
    QUEUED = "queued"
    DOWNLOADING = "downloading"
    PROCESSING = "processing"
    DONE = "done"
    FAILED = "failed"
    CANCELLED = "cancelled"

    @property
    def active(self) -> bool:
        return self in (JobState.QUEUED, JobState.DOWNLOADING, JobState.PROCESSING)


_PP_LABELS = {
    "Merger": "Merging video and audio…",
    "FFmpegMerger": "Merging video and audio…",
    "ExtractAudio": "Converting audio…",
    "FFmpegExtractAudio": "Converting audio…",
    "EmbedThumbnail": "Embedding thumbnail…",
    "FFmpegMetadata": "Writing metadata…",
    "Metadata": "Writing metadata…",
    "FFmpegEmbedSubtitle": "Embedding subtitles…",
    "EmbedSubtitle": "Embedding subtitles…",
    "FFmpegThumbnailsConvertor": "Preparing thumbnail…",
    "ThumbnailsConvertor": "Preparing thumbnail…",
    "FixupM3u8": "Fixing up file…",
}


class JobSignals(QObject):
    state = Signal(int, str, str)            # job id, JobState value, detail text
    progress = Signal(int, float, str)       # job id, fraction 0..1 (or -1 unknown), detail
    meta = Signal(int, str, str)             # job id, title, thumbnail url
    finished = Signal(int, str)              # job id, final file path


class DownloadJob(QRunnable):
    """One URL -> one file. Cancel with .cancel(); checked on every progress tick."""

    def __init__(self, request: DownloadRequest, ffmpeg_dir: str | None):
        super().__init__()
        self.setAutoDelete(False)
        self.id = next(_ids)
        self.request = request
        self.ffmpeg_dir = ffmpeg_dir
        self.signals = JobSignals()
        self._cancel = threading.Event()
        self._last_emit = 0.0
        self._part = 0
        self._parts_total = 1
        self._meta_sent = False
        self._last_pp_label = ""

    def cancel(self) -> None:
        self._cancel.set()

    @property
    def cancelled(self) -> bool:
        return self._cancel.is_set()

    # yt-dlp hooks run on this worker thread
    def _check_cancel(self) -> None:
        if self._cancel.is_set():
            raise DownloadCancelled("Cancelled by user")

    def _progress_hook(self, d: dict) -> None:
        self._check_cancel()
        info = d.get("info_dict") or {}
        if not self._meta_sent and info.get("title"):
            self._meta_sent = True
            self.signals.meta.emit(self.id, info.get("title", ""), info.get("thumbnail") or "")

        status = d.get("status")
        if status == "finished":
            self._part += 1
            return
        if status != "downloading":
            return
        self._last_pp_label = ""

        now = time.monotonic()
        if now - self._last_emit < 0.15:
            return
        self._last_emit = now

        done = d.get("downloaded_bytes") or 0
        total = d.get("total_bytes") or d.get("total_bytes_estimate")
        frac = -1.0
        if total:
            frac = min(done / total, 1.0)
        elif d.get("fragment_count"):
            frac = (d.get("fragment_index") or 0) / d["fragment_count"]

        bits = []
        if frac >= 0:
            bits.append(f"{frac * 100:.0f}%")
        if total:
            bits.append(f"{_size(done)} of {_size(total)}")
        if d.get("speed"):
            bits.append(f"{_size(d['speed'])}/s")
        if d.get("eta") is not None:
            bits.append(f"{_eta(d['eta'])} left")
        if self._parts_total > 1:
            kind = "audio" if self._part >= 1 else "video"
            bits.append(f"{kind} stream")

        # With 2 parts (video+audio), show overall progress across both.
        if frac >= 0 and self._parts_total > 1:
            frac = (min(self._part, self._parts_total - 1) + frac) / self._parts_total
        self.signals.progress.emit(self.id, frac, " · ".join(bits))

    def _pp_hook(self, d: dict) -> None:
        self._check_cancel()
        if d.get("status") == "started":
            name = d.get("postprocessor", "")
            label = _PP_LABELS.get(name)
            if label and label != self._last_pp_label:
                self._last_pp_label = label
                self.signals.state.emit(self.id, JobState.PROCESSING.value, label)

    def _pre_hook(self, info: dict) -> None:
        # Called once formats are chosen: lets us know if there are 2 streams.
        fmts = info.get("requested_formats")
        self._parts_total = len(fmts) if fmts else 1

    def run(self) -> None:
        if self.cancelled:
            self.signals.state.emit(self.id, JobState.CANCELLED.value, "Cancelled")
            return
        self.signals.state.emit(self.id, JobState.DOWNLOADING.value, "Starting…")
        temp_dir = tempfile.mkdtemp(prefix="ytdl-", dir=data_dir())
        opts = build_ydl_options(self.request, self.ffmpeg_dir, temp_dir)
        opts["logger"] = YdlLogger()
        opts["progress_hooks"] = [self._progress_hook]
        opts["postprocessor_hooks"] = [self._pp_hook]

        try:
            output_dir_for(self.request).mkdir(parents=True, exist_ok=True)
            with yt_dlp.YoutubeDL(opts) as ydl:
                # Runs after format selection, before download: tells us
                # whether there are separate video + audio streams.
                ydl.add_post_processor(_FormatPeek(self._pre_hook), when="before_dl")
                info = ydl.extract_info(self.request.url, download=True)
            path = _final_path(info)
            self.signals.finished.emit(self.id, path or "")
            self.signals.state.emit(self.id, JobState.DONE.value, "Done")
        except DownloadCancelled:
            self.signals.state.emit(self.id, JobState.CANCELLED.value, "Cancelled")
        except DownloadError as e:
            if self.cancelled:
                self.signals.state.emit(self.id, JobState.CANCELLED.value, "Cancelled")
            else:
                log.warning("Download failed for %s: %s", self.request.url, e)
                self.signals.state.emit(self.id, JobState.FAILED.value, clean_error(e))
        except Exception as e:  # noqa: BLE001
            log.exception("Unexpected error downloading %s", self.request.url)
            self.signals.state.emit(self.id, JobState.FAILED.value, clean_error(e))
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)


class _FormatPeek(PostProcessor):
    """A no-op 'before_dl' postprocessor used to peek at the chosen formats."""

    def __init__(self, callback):
        super().__init__(None)
        self._cb = callback

    def run(self, info):
        try:
            self._cb(info)
        except Exception:  # noqa: BLE001
            pass
        return [], info


def _final_path(info: dict | None) -> str | None:
    if not info:
        return None
    for d in info.get("requested_downloads") or []:
        if d.get("filepath"):
            return d["filepath"]
    return info.get("filepath") or info.get("_filename")


def _size(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit in ("B", "KB") else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} GB"


def _eta(seconds: float) -> str:
    s = int(seconds)
    if s >= 3600:
        return f"{s // 3600}h {s % 3600 // 60}m"
    if s >= 60:
        return f"{s // 60}m {s % 60:02d}s"
    return f"{s}s"
