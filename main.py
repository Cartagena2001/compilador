"""PseudoCompilador 95 - punto de entrada de la aplicación gráfica."""

import sys

from PySide6.QtWidgets import QApplication

from gui.main_window import VentanaPrincipal, crear_icono
from gui.theme import QSS, Fuentes


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("PseudoCompilador 95")
    app.setStyle("Fusion")
    Fuentes.cargar()
    app.setFont(Fuentes.texto(20))
    app.setStyleSheet(QSS)
    app.setWindowIcon(crear_icono())
    ventana = VentanaPrincipal()
    ventana.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
