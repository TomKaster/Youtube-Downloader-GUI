"""Light and dark themes, applied as a Qt style sheet plus palette."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QFontDatabase, QGuiApplication, QPalette
from PySide6.QtWidgets import QApplication

ACCENT = "#e5484d"
ACCENT_HOVER = "#ec5d61"
ACCENT_PRESSED = "#cf3a3f"

DARK = {
    "bg": "#16171b",
    "surface": "#1f2026",
    "surface2": "#292a31",
    "border": "#34353d",
    "text": "#ecedf0",
    "muted": "#9a9ca6",
    "input": "#121317",
    "track": "#2d2e36",
    "success": "#3fb27f",
    "error": "#ff6b6b",
    "warning": "#e8b04a",
}
LIGHT = {
    "bg": "#f4f5f7",
    "surface": "#ffffff",
    "surface2": "#eef0f3",
    "border": "#dcdfe5",
    "text": "#1b1d22",
    "muted": "#6b6f7b",
    "input": "#ffffff",
    "track": "#e6e8ec",
    "success": "#1f9d63",
    "error": "#d93a3a",
    "warning": "#b7791f",
}


def icon_font_family() -> str:
    """Windows 11 ships Segoe Fluent Icons; Windows 10 has Segoe MDL2 Assets."""
    families = set(QFontDatabase.families())
    for name in ("Segoe Fluent Icons", "Segoe MDL2 Assets"):
        if name in families:
            return name
    return "Segoe UI Symbol"


def is_dark(preference: str) -> bool:
    if preference == "dark":
        return True
    if preference == "light":
        return False
    return QGuiApplication.styleHints().colorScheme() == Qt.ColorScheme.Dark


def current_colors(preference: str) -> dict[str, str]:
    return DARK if is_dark(preference) else LIGHT


_SVG = {
    "check": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16"><path d="M3.5 8.5l3 3 6-7" '
             'fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>',
    "down": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16"><path d="M3.5 6l4.5 4.5 4.5-4.5" '
            'fill="none" stroke="{color}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>',
    "up": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16"><path d="M3.5 10.5l4.5-4.5 4.5 4.5" '
          'fill="none" stroke="{color}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>',
}


def _write_assets(c: dict[str, str]) -> dict[str, str]:
    """Style sheets can only load images from files, so write tiny SVGs to disk."""
    from ytdownloader.core.tools import data_dir

    d = data_dir() / "theme"
    d.mkdir(exist_ok=True)
    paths = {}
    for name, color in (("check", "#ffffff"), ("down", c["muted"]), ("up", c["muted"])):
        p = d / f"{name}-{color.lstrip('#')}.svg"
        if not p.exists():
            p.write_text(_SVG[name].format(color=color), encoding="utf-8")
        paths[name] = p.as_posix()
    return paths


def _stylesheet(c: dict[str, str], icon_font: str) -> str:
    a = _write_assets(c)
    return f"""
* {{
    font-family: "Segoe UI Variable Text", "Segoe UI";
    font-size: 10pt;
    color: {c['text']};
}}
QMainWindow, QDialog {{ background: {c['bg']}; }}
QWidget#Central {{ background: {c['bg']}; }}
QToolTip {{
    background: {c['surface2']}; color: {c['text']};
    border: 1px solid {c['border']}; padding: 4px 6px;
}}

QFrame#Card {{
    background: {c['surface']};
    border: 1px solid {c['border']};
    border-radius: 10px;
}}
QLabel#AppTitle {{ font-size: 15pt; font-weight: 600; }}
QLabel#SectionTitle {{ font-size: 11pt; font-weight: 600; }}
QLabel#MediaTitle {{ font-size: 11.5pt; font-weight: 600; }}
QLabel#Muted, QLabel#Badge {{ color: {c['muted']}; }}
QLabel#Thumb {{ background: {c['surface2']}; border-radius: 6px; }}
QLabel#Success {{ color: {c['success']}; }}
QLabel#Error {{ color: {c['error']}; }}
QLabel#Warning {{ color: {c['warning']}; }}
QLabel#EmptyState {{ color: {c['muted']}; font-size: 10.5pt; }}
QLabel#EmptyIcon {{ color: {c['border']}; font-family: "{icon_font}"; font-size: 34pt; }}

QLineEdit, QComboBox, QSpinBox {{
    background: {c['input']};
    border: 1px solid {c['border']};
    border-radius: 7px;
    padding: 6px 10px;
    selection-background-color: {ACCENT};
}}
QLineEdit#UrlInput {{ font-size: 11pt; padding: 9px 12px; }}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus {{ border: 1px solid {ACCENT}; }}
QLineEdit:disabled, QComboBox:disabled {{ color: {c['muted']}; }}
QComboBox {{ padding-right: 28px; }}
QComboBox::drop-down {{
    subcontrol-origin: padding; subcontrol-position: center right;
    border: none; width: 26px;
}}
QComboBox::down-arrow {{ image: url("{a['down']}"); width: 12px; height: 12px; }}
QSpinBox {{ padding-right: 22px; }}
QSpinBox::up-button, QSpinBox::down-button {{
    subcontrol-origin: border; width: 20px; border: none; background: transparent;
}}
QSpinBox::up-button {{ subcontrol-position: top right; }}
QSpinBox::down-button {{ subcontrol-position: bottom right; }}
QSpinBox::up-arrow {{ image: url("{a['up']}"); width: 10px; height: 10px; }}
QSpinBox::down-arrow {{ image: url("{a['down']}"); width: 10px; height: 10px; }}
QComboBox QAbstractItemView {{
    background: {c['surface']}; border: 1px solid {c['border']};
    selection-background-color: {c['surface2']}; selection-color: {c['text']};
    outline: none; padding: 4px;
}}

QPushButton {{
    background: {c['surface2']};
    border: 1px solid {c['border']};
    border-radius: 7px;
    padding: 7px 14px;
}}
QPushButton:hover {{ border-color: {c['muted']}; }}
QPushButton:pressed {{ background: {c['border']}; }}
QPushButton:disabled {{ color: {c['muted']}; }}
QPushButton#Primary {{
    background: {ACCENT}; border: 1px solid {ACCENT};
    color: white; font-weight: 600; padding: 8px 20px;
}}
QPushButton#Primary:hover {{ background: {ACCENT_HOVER}; border-color: {ACCENT_HOVER}; }}
QPushButton#Primary:pressed {{ background: {ACCENT_PRESSED}; }}
QPushButton#Primary:disabled {{ background: {c['surface2']}; border-color: {c['border']}; color: {c['muted']}; }}

/* Video / Audio segmented toggle */
QPushButton#SegmentLeft {{
    border-top-right-radius: 0; border-bottom-right-radius: 0;
    padding: 7px 16px; background: {c['input']};
}}
QPushButton#SegmentRight {{
    border-top-left-radius: 0; border-bottom-left-radius: 0;
    padding: 7px 16px; background: {c['input']}; margin-left: -1px;
}}
QPushButton#SegmentLeft:checked, QPushButton#SegmentRight:checked {{
    background: {c['surface2']}; border-color: {ACCENT}; color: {ACCENT};
}}

QToolButton#IconButton {{
    font-family: "{icon_font}";
    font-size: 11pt;
    background: transparent;
    border: 1px solid transparent;
    border-radius: 6px;
    padding: 5px;
    min-width: 18px; min-height: 18px;
}}
QToolButton#IconButton:hover {{ background: {c['surface2']}; border-color: {c['border']}; }}
QToolButton#IconButton:pressed {{ background: {c['border']}; }}
QToolButton#IconButton:disabled {{ color: {c['border']}; }}
QLabel#StatusIcon {{ font-family: "{icon_font}"; font-size: 10pt; }}

QProgressBar {{
    background: {c['track']};
    border: none; border-radius: 3px;
    max-height: 6px; min-height: 6px;
    text-align: center; color: transparent;
}}
QProgressBar::chunk {{ background: {ACCENT}; border-radius: 3px; }}
QProgressBar[state="done"]::chunk {{ background: {c['success']}; }}
QProgressBar[state="error"]::chunk {{ background: {c['error']}; }}
QProgressBar[state="muted"]::chunk {{ background: {c['muted']}; }}

QListWidget#Queue {{ background: transparent; border: none; outline: none; }}
QListWidget#Queue::item {{ border: none; padding: 0; margin: 0 0 8px 0; }}
QListWidget#Queue::item:selected, QListWidget#Queue::item:hover {{ background: transparent; }}

QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {c['border']}; border-radius: 3px; min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: {c['muted']}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: none; height: 0; }}

QCheckBox {{ spacing: 8px; }}
QCheckBox::indicator {{
    width: 16px; height: 16px; border-radius: 4px;
    border: 1px solid {c['border']}; background: {c['input']};
}}
QCheckBox::indicator:checked {{ background: {ACCENT}; border-color: {ACCENT}; image: url("{a['check']}"); }}
QCheckBox:disabled {{ color: {c['muted']}; }}

QStatusBar {{ background: {c['surface']}; border-top: 1px solid {c['border']}; }}
QStatusBar QLabel {{ color: {c['muted']}; padding: 0 6px; }}
QGroupBox {{
    border: 1px solid {c['border']}; border-radius: 8px;
    margin-top: 14px; padding: 12px 10px 10px 10px; font-weight: 600;
}}
QGroupBox::title {{ subcontrol-origin: margin; left: 12px; padding: 0 4px; }}
QGroupBox QLabel, QGroupBox QCheckBox {{ font-weight: normal; }}
"""


def apply_theme(app: QApplication, preference: str) -> dict[str, str]:
    c = current_colors(preference)
    app.setStyle("Fusion")
    pal = QPalette()
    for role, key in (
        (QPalette.ColorRole.Window, "bg"),
        (QPalette.ColorRole.Base, "input"),
        (QPalette.ColorRole.AlternateBase, "surface2"),
        (QPalette.ColorRole.Button, "surface2"),
        (QPalette.ColorRole.Text, "text"),
        (QPalette.ColorRole.WindowText, "text"),
        (QPalette.ColorRole.ButtonText, "text"),
        (QPalette.ColorRole.ToolTipBase, "surface2"),
        (QPalette.ColorRole.ToolTipText, "text"),
        (QPalette.ColorRole.PlaceholderText, "muted"),
    ):
        pal.setColor(role, QColor(c[key]))
    pal.setColor(QPalette.ColorRole.Highlight, QColor(ACCENT))
    pal.setColor(QPalette.ColorRole.HighlightedText, QColor("white"))
    app.setPalette(pal)
    app.setFont(QFont("Segoe UI", 10))
    app.setStyleSheet(_stylesheet(c, icon_font_family()))
    return c


# Segoe Fluent Icons / MDL2 glyph code points
class Glyph:
    SETTINGS = ""
    PASTE = ""
    DOWNLOAD = ""
    CANCEL = ""
    RETRY = ""
    FOLDER = ""
    PLAY = ""
    CLEAR = ""
    REMOVE = ""
    CHECK = ""
    ERROR = ""
    WARNING = ""
    VIDEO = ""
    AUDIO = ""
    LINK = ""
    LIST = ""
