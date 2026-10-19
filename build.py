"""Genera el ejecutable de PseudoCompilador 95 con PyInstaller.

Uso:  python build.py
El ejecutable queda en dist/ (PseudoCompilador95.exe en Windows,
PseudoCompilador95 en Linux, PseudoCompilador95.app en macOS).
PyInstaller no compila de forma cruzada: para obtener el .exe de Windows
hay que ejecutar este script en Windows.
"""

import os
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent


def generar_icono() -> Path:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from gui.main_window import crear_icono

    _app = QApplication.instance() or QApplication([])
    png = RAIZ / "assets" / "icono.png"
    crear_icono().pixmap(256, 256).save(str(png))
    try:  # .ico para Windows (requiere Pillow)
        from PIL import Image

        ico = RAIZ / "assets" / "icono.ico"
        Image.open(png).save(ico, sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (256, 256)])
        return ico
    except ImportError:
        return png


def main():
    import PyInstaller.__main__

    icono = generar_icono()
    sep = os.pathsep
    PyInstaller.__main__.run([
        str(RAIZ / "main.py"),
        "--name", "PseudoCompilador95",
        "--onefile",
        "--windowed",
        "--noconfirm",
        "--clean",
        "--icon", str(icono),
        "--add-data", f"{RAIZ / 'assets' / 'fonts'}{sep}assets/fonts",
        "--add-data", f"{RAIZ / 'examples'}{sep}examples",
        "--exclude-module", "tkinter",
        "--exclude-module", "pytest",
    ])
    print("\nListo. Ejecutable en:", RAIZ / "dist")


if __name__ == "__main__":
    sys.path.insert(0, str(RAIZ))
    main()
