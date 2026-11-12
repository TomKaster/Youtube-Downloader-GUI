"""Launcher used for `py run.py` and as the PyInstaller entry point."""

from ytdownloader.app import main

if __name__ == "__main__":
    raise SystemExit(main())
