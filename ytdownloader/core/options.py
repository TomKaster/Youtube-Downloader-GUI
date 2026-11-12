"""Turn what the user picked in the GUI into a yt-dlp options dict.

Kept free of Qt so it can be unit-tested on its own.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class Mode(str, Enum):
    VIDEO = "video"
    AUDIO = "audio"


# Audio formats offered in the GUI: label -> yt-dlp codec name.
AUDIO_FORMATS: dict[str, str] = {
    "MP3": "mp3",
    "M4A (AAC)": "m4a",
    "Opus": "opus",
    "FLAC (lossless)": "flac",
    "WAV (uncompressed)": "wav",
}
LOSSY_AUDIO = {"mp3", "m4a", "opus"}
MP3_BITRATES = (128, 192, 256, 320)

# Thumbnails can't be embedded into these containers.
NO_THUMBNAIL_EMBED = {"wav"}


@dataclass
class DownloadRequest:
    url: str
    mode: Mode
    output_dir: Path
    # Video
    max_height: int | None = None          # None = best available
    prefer_h264: bool = False               # most compatible, but often capped at 1080p
    subtitles: bool = False
    subtitle_langs: list[str] = field(default_factory=lambda: ["en"])
    # Audio
    audio_codec: str = "mp3"
    audio_bitrate: int = 192
    # Both
    embed_thumbnail: bool = True
    embed_metadata: bool = True
    subfolder: str | None = None           # e.g. playlist name
    title_hint: str | None = None          # shown in the queue before yt-dlp reports it


def output_dir_for(req: DownloadRequest) -> Path:
    out_dir = Path(req.output_dir)
    return out_dir / req.subfolder if req.subfolder else out_dir


def build_ydl_options(req: DownloadRequest, ffmpeg_dir: str | None, temp_dir: str | None = None) -> dict:
    """temp_dir: where partial files/thumbnails live until the final file is moved out."""
    opts: dict = {
        "outtmpl": "%(title)s.%(ext)s",
        "paths": {"home": str(output_dir_for(req)), **({"temp": temp_dir} if temp_dir else {})},
        "noplaylist": True,
        "windowsfilenames": True,
        "quiet": True,
        "no_warnings": False,
        "noprogress": True,
        "concurrent_fragment_downloads": 4,
        "retries": 5,
        "fragment_retries": 5,
    }
    if ffmpeg_dir:
        opts["ffmpeg_location"] = ffmpeg_dir

    postprocessors: list[dict] = []
    has_ffmpeg = ffmpeg_dir is not None

    if req.mode is Mode.VIDEO:
        sort: list[str] = []
        if req.max_height:
            sort.append(f"res:{req.max_height}")
        if req.prefer_h264:
            sort += ["vcodec:h264", "acodec:aac"]
        sort.append("ext:mp4:m4a")
        opts["format_sort"] = sort

        if has_ffmpeg:
            # Separate best video + best audio, merged into one .mp4
            opts["format"] = "bv*+ba/b"
            opts["merge_output_format"] = "mp4"
        else:
            # Without ffmpeg only pre-merged single files work (usually <=720p)
            opts["format"] = "b"

        if req.subtitles and has_ffmpeg:
            opts["writesubtitles"] = True
            opts["writeautomaticsub"] = True
            opts["subtitleslangs"] = list(req.subtitle_langs) or ["en"]
            postprocessors.append({"key": "FFmpegEmbedSubtitle", "already_have_subtitle": False})
    else:
        opts["format"] = "ba/b"
        quality = str(req.audio_bitrate) if req.audio_codec == "mp3" else "0"
        postprocessors.append({
            "key": "FFmpegExtractAudio",
            "preferredcodec": req.audio_codec,
            "preferredquality": quality,
        })

    if has_ffmpeg and req.embed_metadata:
        postprocessors.append({"key": "FFmpegMetadata", "add_metadata": True, "add_chapters": True})

    embed_thumb = (
        has_ffmpeg
        and req.embed_thumbnail
        and not (req.mode is Mode.AUDIO and req.audio_codec in NO_THUMBNAIL_EMBED)
    )
    if embed_thumb:
        opts["writethumbnail"] = True
        # YouTube thumbnails are .webp, which most players can't show embedded.
        postprocessors.insert(0, {"key": "FFmpegThumbnailsConvertor", "format": "jpg", "when": "before_dl"})
        postprocessors.append({"key": "EmbedThumbnail", "already_have_thumbnail": False})

    if postprocessors:
        opts["postprocessors"] = postprocessors
    return opts


def needs_ffmpeg(req: DownloadRequest) -> bool:
    """Audio extraction can't work at all without ffmpeg."""
    return req.mode is Mode.AUDIO
