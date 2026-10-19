"""Tema visual estilo escritorio de los 90 (Windows 95 / MS-DOS / Turbo C)."""

import sys
from pathlib import Path

from PySide6.QtGui import QFont, QFontDatabase

# Paleta Windows 95
DESKTOP = "#008080"
FACE = "#c0c0c0"
LIGHT = "#ffffff"
MIDLIGHT = "#dfdfdf"
SHADOW = "#808080"
DARK = "#000000"
NAVY = "#000080"
TITLE_END = "#1084d0"
TOOLTIP = "#ffffe1"

# Paleta CGA / Turbo C (panel de código generado)
BORLAND_BG = "#0000aa"
BORLAND_FG = "#ffff55"

# Consola MS-DOS
DOS_BG = "#000000"
DOS_FG = "#c0c0c0"

OK = "#00aa00"
ERROR = "#aa0000"
WARN = "#aa5500"


def recurso(*partes) -> Path:
    """Ruta a un recurso, tanto en desarrollo como dentro del ejecutable."""
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    return base.joinpath(*partes)


class Fuentes:
    ui = "VT323"
    titulo = "Press Start 2P"

    @classmethod
    def cargar(cls):
        for archivo in ("VT323-Regular.ttf", "PressStart2P-Regular.ttf"):
            QFontDatabase.addApplicationFont(str(recurso("assets", "fonts", archivo)))

    @staticmethod
    def crear(familia: str, px: int) -> QFont:
        f = QFont(familia)
        f.setPixelSize(px)
        f.setStyleStrategy(QFont.StyleStrategy.NoAntialias)
        f.setHintingPreference(QFont.HintingPreference.PreferFullHinting)
        return f

    @classmethod
    def texto(cls, px=20):
        return cls.crear(cls.ui, px)

    @classmethod
    def pixel(cls, px=8):
        return cls.crear(cls.titulo, px)


def _bevel(arriba_izq, abajo_der, ancho=2):
    return (
        f"border-style: solid; border-width: {ancho}px;"
        f"border-color: {arriba_izq} {abajo_der} {abajo_der} {arriba_izq};"
    )


RELIEVE = _bevel(LIGHT, DARK)
HUNDIDO = _bevel(SHADOW, LIGHT)

QSS = f"""
QMainWindow, QDialog {{ background: {FACE}; }}
QWidget {{ color: {DARK}; }}
QWidget#Escritorio {{ background: {DESKTOP}; }}

/* --- Ventanas internas --- */
QFrame#Ventana {{ background: {FACE}; {RELIEVE} padding: 1px; }}
QFrame#BarraTitulo {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {NAVY}, stop:1 {TITLE_END});
    min-height: 22px; max-height: 22px;
}}
QFrame#BarraTitulo[inactiva="true"] {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {SHADOW}, stop:1 #b5b5b5);
}}
QLabel#TextoTitulo {{ color: {LIGHT}; padding-left: 4px; background: transparent; }}

/* --- Botones --- */
QPushButton, QToolButton {{
    background: {FACE}; {RELIEVE} padding: 3px 10px; min-height: 20px;
}}
QPushButton:hover, QToolButton:hover {{ background: #cacaca; }}
QPushButton:pressed, QToolButton:pressed, QToolButton:checked {{
    {_bevel(DARK, LIGHT)} padding: 4px 9px 2px 11px; background: {FACE};
}}
QPushButton:disabled {{ color: {SHADOW}; }}
QPushButton:focus {{ outline: none; }}
QPushButton#BotonTitulo {{
    min-width: 14px; max-width: 14px; min-height: 12px; max-height: 12px;
    padding: 0px; {_bevel(LIGHT, DARK, 1)} font-weight: bold;
}}
QPushButton#BotonPrincipal {{ padding: 4px 14px; }}

/* --- Campos de texto --- */
QPlainTextEdit, QTextEdit, QTextBrowser, QLineEdit, QTableWidget, QTreeWidget {{
    background: {LIGHT}; {HUNDIDO}
    selection-background-color: {NAVY}; selection-color: {LIGHT};
}}
QPlainTextEdit#Salida {{ background: {BORLAND_BG}; color: {BORLAND_FG}; }}
QTextBrowser#Dos, QTextEdit#Dos, QPlainTextEdit#Dos {{ background: {DOS_BG}; color: {DOS_FG}; }}
QLineEdit#EntradaDos {{ background: {DOS_BG}; color: #ffff55; }}
QLineEdit:disabled#EntradaDos {{ color: {SHADOW}; }}

/* --- Menús --- */
QMenuBar {{ background: {FACE}; border-bottom: 1px solid {SHADOW}; }}
QMenuBar::item {{ padding: 2px 10px; background: transparent; }}
QMenuBar::item:selected {{ background: {NAVY}; color: {LIGHT}; }}
QMenu {{ background: {FACE}; {RELIEVE} padding: 2px; }}
QMenu::item {{ padding: 3px 28px 3px 22px; }}
QMenu::item:selected {{ background: {NAVY}; color: {LIGHT}; }}
QMenu::separator {{ height: 2px; margin: 3px 4px; background: {SHADOW}; border-bottom: 1px solid {LIGHT}; }}

/* --- Barra de herramientas y estado --- */
QToolBar {{ background: {FACE}; border: none; border-bottom: 2px groove {LIGHT}; spacing: 6px; padding: 4px; }}
QToolBar::separator {{ width: 2px; background: {SHADOW}; border-right: 1px solid {LIGHT}; margin: 2px 4px; }}
QStatusBar {{ background: {FACE}; border-top: 1px solid {SHADOW}; }}
QStatusBar::item {{ border: none; }}
QLabel#Celda {{ {HUNDIDO} border-width: 1px; padding: 0px 8px; }}

/* --- Combo --- */
QComboBox {{ background: {LIGHT}; {HUNDIDO} padding: 1px 6px; min-width: 120px; }}
QComboBox::drop-down {{ width: 18px; background: {FACE}; {RELIEVE} }}
QComboBox::down-arrow {{ width: 0; height: 0; border-left: 4px solid transparent;
    border-right: 4px solid transparent; border-top: 5px solid {DARK}; }}
QComboBox QAbstractItemView {{ background: {LIGHT}; border: 1px solid {DARK};
    selection-background-color: {NAVY}; selection-color: {LIGHT}; }}

/* --- Pestañas --- */
QTabWidget::pane {{ background: {FACE}; {RELIEVE} top: -2px; padding: 3px; }}
QTabBar::tab {{
    background: {FACE}; border: 2px solid; border-color: {LIGHT} {DARK} {FACE} {LIGHT};
    border-top-left-radius: 3px; border-top-right-radius: 3px;
    padding: 2px 12px; margin-right: 1px; margin-top: 3px;
}}
QTabBar::tab:selected {{ margin-top: 0px; padding-bottom: 4px; }}

/* --- Tablas y árbol --- */
QHeaderView::section {{ background: {FACE}; {RELIEVE} padding: 1px 6px; }}
QTableWidget {{ gridline-color: {MIDLIGHT}; }}
QTreeWidget::item:selected, QTableWidget::item:selected {{ background: {NAVY}; color: {LIGHT}; }}

/* --- Barra de progreso por bloques --- */
QProgressBar {{ background: {LIGHT}; {HUNDIDO} border-width: 1px; height: 18px; text-align: center; color: transparent; }}
QProgressBar::chunk {{ background: {NAVY}; width: 12px; margin: 2px 1px; }}

/* --- Separadores --- */
QSplitter::handle {{ background: {DESKTOP}; }}

/* --- Barras de desplazamiento --- */
QScrollBar:vertical {{ background: {MIDLIGHT}; width: 16px; margin: 16px 0 16px 0; }}
QScrollBar:horizontal {{ background: {MIDLIGHT}; height: 16px; margin: 0 16px 0 16px; }}
QScrollBar::handle {{ background: {FACE}; {RELIEVE} }}
QScrollBar::handle:vertical {{ min-height: 20px; }}
QScrollBar::handle:horizontal {{ min-width: 20px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ background: {FACE}; {RELIEVE} }}
QScrollBar::add-line:vertical {{ height: 12px; subcontrol-position: bottom; subcontrol-origin: margin; }}
QScrollBar::sub-line:vertical {{ height: 12px; subcontrol-position: top; subcontrol-origin: margin; }}
QScrollBar::add-line:horizontal {{ width: 12px; subcontrol-position: right; subcontrol-origin: margin; }}
QScrollBar::sub-line:horizontal {{ width: 12px; subcontrol-position: left; subcontrol-origin: margin; }}
QScrollBar::up-arrow:vertical {{ width: 0; height: 0; border-left: 4px solid transparent; border-right: 4px solid transparent; border-bottom: 4px solid {DARK}; }}
QScrollBar::down-arrow:vertical {{ width: 0; height: 0; border-left: 4px solid transparent; border-right: 4px solid transparent; border-top: 4px solid {DARK}; }}
QScrollBar::left-arrow:horizontal {{ width: 0; height: 0; border-top: 4px solid transparent; border-bottom: 4px solid transparent; border-right: 4px solid {DARK}; }}
QScrollBar::right-arrow:horizontal {{ width: 0; height: 0; border-top: 4px solid transparent; border-bottom: 4px solid transparent; border-left: 4px solid {DARK}; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}
QAbstractScrollArea::corner {{ background: {FACE}; }}

QToolTip {{ background: {TOOLTIP}; color: {DARK}; border: 1px solid {DARK}; padding: 2px; }}
QMessageBox QLabel {{ padding: 6px; }}
"""
