from pathlib import Path

from ytdownloader.core.fetch import clean_error, format_duration
from ytdownloader.core.options import DownloadRequest, Mode, build_ydl_options

OUT = Path("C:/out")


def keys(opts):
    return [p["key"] for p in opts.get("postprocessors", [])]


def test_video_best_with_ffmpeg_merges_to_mp4():
    o = build_ydl_options(DownloadRequest("u", Mode.VIDEO, OUT), "C:/ff")
    assert o["format"] == "bv*+ba/b"
    assert o["merge_output_format"] == "mp4"
    assert not any(s.startswith("res:") for s in o["format_sort"])
    assert o["ffmpeg_location"] == "C:/ff"


def test_video_height_cap_and_h264():
    o = build_ydl_options(DownloadRequest("u", Mode.VIDEO, OUT, max_height=720, prefer_h264=True), "ff")
    assert o["format_sort"][:2] == ["res:720", "vcodec:h264"]


def test_video_without_ffmpeg_uses_single_file_and_no_postprocessors():
    o = build_ydl_options(DownloadRequest("u", Mode.VIDEO, OUT, subtitles=True), None)
    assert o["format"] == "b"
    assert "merge_output_format" not in o
    assert "postprocessors" not in o


def test_audio_mp3_bitrate_and_thumbnail_order():
    o = build_ydl_options(DownloadRequest("u", Mode.AUDIO, OUT, audio_codec="mp3", audio_bitrate=320), "ff")
    pp = o["postprocessors"]
    assert keys(o) == ["FFmpegThumbnailsConvertor", "FFmpegExtractAudio", "FFmpegMetadata", "EmbedThumbnail"]
    assert pp[1]["preferredcodec"] == "mp3" and pp[1]["preferredquality"] == "320"
    assert o["writethumbnail"] is True


def test_wav_skips_thumbnail_embed():
    o = build_ydl_options(DownloadRequest("u", Mode.AUDIO, OUT, audio_codec="wav"), "ff")
    assert "EmbedThumbnail" not in keys(o)
    assert "writethumbnail" not in o


def test_subtitles_and_subfolder():
    o = build_ydl_options(DownloadRequest("u", Mode.VIDEO, OUT, subtitles=True, subtitle_langs=["en", "de"],
                                          subfolder="My List"), "ff")
    assert "FFmpegEmbedSubtitle" in keys(o)
    assert o["subtitleslangs"] == ["en", "de"]
    assert Path(o["paths"]["home"]) == OUT / "My List"
    assert "temp" not in o["paths"]
    assert build_ydl_options(DownloadRequest("u", Mode.VIDEO, OUT), "ff", "C:/t")["paths"]["temp"] == "C:/t"


def test_clean_error():
    assert clean_error("\x1b[0;31mERROR:\x1b[0m [youtube] abc_123: Video unavailable") == "Video unavailable"
    assert format_duration(3725) == "1:02:05"
    assert format_duration(65) == "1:05"
