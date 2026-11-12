# Youtube-Downloader-GUI

**YT Downloader** is a Windows desktop app for downloading YouTube videos and audio. It started in 2022 as a command-line script and was rebuilt in 2026 as a GUI app on [yt-dlp](https://github.com/yt-dlp/yt-dlp) and Qt (PySide6).

## Features

- **Paste or drag a link**: the app looks it up and shows a preview with the thumbnail, title, channel and length.
- **Video** saved as MP4. Pick any resolution the video actually has (Best, 4K, 1440p, 1080p and lower).
- **Audio only** as MP3 (128–320 kbps), M4A, Opus, FLAC or WAV.
- **Playlists**: paste a playlist link to queue every video. By default each playlist gets its own folder.
- **Download queue** that shows progress, speed and time left. Several downloads can run at once, and each one can be cancelled or retried. When a download finishes you can open the file or show it in Explorer.
- **Cover art and tags**: the thumbnail, title, artist and chapters are embedded. Subtitles can be embedded too (optional).
- **Light and dark themes**, or match the Windows setting.
- Your settings and last choices are remembered.

## Run from source

1. Install the Python packages (Python 3.10+):
   ```
   py -m pip install -U -r requirements.txt
   ```
2. Get **Deno** (yt-dlp needs it to solve YouTube's player challenges) and **ffmpeg** (needed for audio conversion and for merging high-quality video with its audio). The quickest way is:
   ```
   powershell -ExecutionPolicy Bypass -File build.ps1 -ToolsOnly
   ```
   This downloads both into `bin\`, and the app picks them up from there. Installing them system-wide also works (`winget install DenoLand.Deno` and `winget install Gyan.FFmpeg`).
3. Start the app:
   ```
   py run.py
   ```

## Build the standalone .exe

```
powershell -ExecutionPolicy Bypass -File build.ps1
```

This produces `dist\YT Downloader.exe` (about 125 MB) with Deno and ffmpeg packed inside. **Users only need that one file.** It takes a few seconds to start because it unpacks itself first.

ffmpeg is GPL-licensed. If you distribute the .exe publicly, include a note that it bundles ffmpeg and link to its source (https://ffmpeg.org). Deno is MIT-licensed.

## Tests

```
py -m pip install -r requirements-dev.txt
py -m pytest
```

## Project layout

```
run.py                      entry point (also used by PyInstaller)
ytdownloader/
  core/                     no GUI code
    options.py              turns your choices into yt-dlp options
    fetch.py                link lookup (title, thumbnail, qualities, playlist entries)
    tools.py                finds ffmpeg / Deno, app folders
  ui/
    main_window.py          main window: link box, preview, queue
    workers.py              background lookup and download jobs (thread pool)
    queue_item.py           one row in the downloads list
    settings_dialog.py      Settings window
    theme.py                light/dark style sheet
    icons.py                app icon, drawn in code
tests/                      unit tests for the option building
```

The log is saved to `%LOCALAPPDATA%\YT Downloader\log.txt` (Settings → Open log folder).

## If it stops working

YouTube changes often. Usually the fix is to update yt-dlp: run `py -m pip install -U -r requirements.txt` from source, or rebuild the .exe with `build.ps1`. Delete `bin\` first if you also want fresh copies of Deno and ffmpeg.
