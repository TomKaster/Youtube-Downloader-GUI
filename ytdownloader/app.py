"""Application entry point."""

from __future__ import annotations

import logging
import sys
import traceback
from logging.handlers import RotatingFileHandler

from ytdownloader import APP_NAME, ORG_NAME, __version__
from ytdownloader.core.tools import add_bundled_tools_to_path, data_dir, detect_tools


def _setup_logging() -> None:
    handler = RotatingFileHandler(data_dir() / "log.txt", maxBytes=1_000_000, backupCount=2,
                                  encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(handler)


def _set_windows_app_id() -> None:
    """Makes the taskbar show our icon instead of python.exe's."""
    if sys.platform == "win32":
        try:
            import ctypes

            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(f"{ORG_NAME}.YTDownloader")
        except Exception:  # noqa: BLE001
            pass


def main() -> int:
    _setup_logging()
    log = logging.getLogger("ytdownloader")
    log.info("Starting %s %s", APP_NAME, __version__)
    add_bundled_tools_to_path()
    _set_windows_app_id()

    from PySide6.QtWidgets import QApplication, QMessageBox

    from ytdownloader.ui import theme
    from ytdownloader.ui.icons import app_icon
    from ytdownloader.ui.main_window import MainWindow
    from ytdownloader.ui.settings import Settings

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(ORG_NAME)
    app.setApplicationVersion(__version__)
    app.setWindowIcon(app_icon())

    def excepthook(exc_type, exc, tb):
        log.error("Unhandled error", exc_info=(exc_type, exc, tb))
        QMessageBox.critical(None, APP_NAME, "Something went wrong:\n\n"
                             + "".join(traceback.format_exception_only(exc_type, exc)).strip()
                             + f"\n\nDetails were saved to {data_dir() / 'log.txt'}")
    sys.excepthook = excepthook

    settings = Settings()
    theme.apply_theme(app, settings.get("theme"))
    tools = detect_tools()
    log.info("ffmpeg: %s | deno: %s", tools.ffmpeg_dir, tools.deno)

    win = MainWindow(settings, tools)
    win.show()
    return app.exec()
