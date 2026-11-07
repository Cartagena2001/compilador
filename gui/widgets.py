"""Widgets con estética retro: ventanas internas, editor de código con
números de línea, resaltado de sintaxis e indicador de fases."""

import re

from PySide6.QtCore import QRect, QSize, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QSyntaxHighlighter, QTextCharFormat, QTextFormat
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPlainTextEdit, QPushButton, QTextEdit, QVBoxLayout, QWidget,
)

from . import theme
from .theme import Fuentes


# ---------------------------------------------------------------------------
class VentanaRetro(QFrame):
    """Marco con barra de título degradada al estilo Windows 95."""

    maximizar = Signal(object)

    def __init__(self, titulo: str, icono: str = "▣", parent=None):
        super().__init__(parent)
        self.setObjectName("Ventana")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(2, 2, 2, 2)
        lay.setSpacing(2)

        self.barra = QFrame(objectName="BarraTitulo")
        bl = QHBoxLayout(self.barra)
        bl.setContentsMargins(3, 2, 3, 2)
        bl.setSpacing(2)
        self.icono = QLabel(icono, objectName="TextoTitulo")
        self.icono.setFont(Fuentes.texto(18))
        self.texto = QLabel(titulo, objectName="TextoTitulo")
        self.texto.setFont(Fuentes.pixel(8))
        bl.addWidget(self.icono)
        bl.addWidget(self.texto, 1)
        self.extra = QHBoxLayout()
        self.extra.setSpacing(4)
        bl.addLayout(self.extra)

        self.btn_max = QPushButton("□", objectName="BotonTitulo")
        self.btn_max.setFont(Fuentes.texto(16))
        self.btn_max.setToolTip("Maximizar / restaurar este panel")
        self.btn_max.clicked.connect(lambda: self.maximizar.emit(self))
        bl.addWidget(self.btn_max)
        lay.addWidget(self.barra)

        self.cuerpo = QVBoxLayout()
        self.cuerpo.setContentsMargins(2, 2, 2, 2)
        self.cuerpo.setSpacing(4)
        lay.addLayout(self.cuerpo, 1)

    def set_titulo(self, titulo):
        self.texto.setText(titulo)

    def agregar(self, widget, stretch=0):
        self.cuerpo.addWidget(widget, stretch)
        return widget


# ---------------------------------------------------------------------------
class _AreaNumeros(QWidget):
    def __init__(self, editor):
        super().__init__(editor)
        self.editor = editor

    def sizeHint(self):
        return QSize(self.editor.ancho_numeros(), 0)

    def paintEvent(self, event):
        self.editor.pintar_numeros(event)


class EditorCodigo(QPlainTextEdit):
    """Editor con números de línea y marcas de error en el margen."""

    def __init__(self, fondo_margen, color_numeros, solo_lectura=False, parent=None):
        super().__init__(parent)
        self.fondo_margen = QColor(fondo_margen)
        self.color_numeros = QColor(color_numeros)
        self.lineas_error: dict[int, str] = {}
        self.lineas_aviso: set[int] = set()
        self.setReadOnly(solo_lectura)
        self.setFont(Fuentes.texto(22))
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.setTabStopDistance(self.fontMetrics().horizontalAdvance(" ") * 4)
        self.area = _AreaNumeros(self)
        self.blockCountChanged.connect(self._actualizar_ancho)
        self.updateRequest.connect(self._actualizar_area)
        self.cursorPositionChanged.connect(self._resaltar)
        self._actualizar_ancho()
        self._resaltar()

    def ancho_numeros(self):
        digitos = max(3, len(str(self.blockCount())))
        return 14 + self.fontMetrics().horizontalAdvance("9") * digitos + 12

    def _actualizar_ancho(self, *_):
        self.setViewportMargins(self.ancho_numeros(), 0, 0, 0)

    def _actualizar_area(self, rect, dy):
        if dy:
            self.area.scroll(0, dy)
        else:
            self.area.update(0, rect.y(), self.area.width(), rect.height())
        if rect.contains(self.viewport().rect()):
            self._actualizar_ancho()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        cr = self.contentsRect()
        self.area.setGeometry(QRect(cr.left(), cr.top(), self.ancho_numeros(), cr.height()))

    def pintar_numeros(self, event):
        p = QPainter(self.area)
        p.fillRect(event.rect(), self.fondo_margen)
        p.setFont(self.font())
        bloque = self.firstVisibleBlock()
        num = bloque.blockNumber()
        top = round(self.blockBoundingGeometry(bloque).translated(self.contentOffset()).top())
        alto = round(self.blockBoundingRect(bloque).height())
        ancho = self.area.width()
        while bloque.isValid() and top <= event.rect().bottom():
            if bloque.isVisible() and top + alto >= event.rect().top():
                linea = num + 1
                if linea in self.lineas_error:
                    p.fillRect(0, top, ancho, alto, QColor(theme.ERROR))
                    p.setPen(QColor("#ffffff"))
                    p.drawText(2, top, 12, alto, Qt.AlignmentFlag.AlignCenter, "!")
                elif linea in self.lineas_aviso:
                    p.fillRect(0, top, ancho, alto, QColor("#ffff55"))
                    p.setPen(QColor(theme.DARK))
                    p.drawText(2, top, 12, alto, Qt.AlignmentFlag.AlignCenter, "?")
                else:
                    p.setPen(self.color_numeros)
                p.drawText(0, top, ancho - 6, alto, Qt.AlignmentFlag.AlignRight, str(linea))
            bloque = bloque.next()
            top += alto
            alto = round(self.blockBoundingRect(bloque).height())
            num += 1
        # línea de relieve que separa el margen del texto
        p.setPen(QColor(theme.SHADOW))
        p.drawLine(ancho - 1, event.rect().top(), ancho - 1, event.rect().bottom())

    def marcar(self, errores: dict[int, str], avisos: set[int]):
        self.lineas_error = errores
        self.lineas_aviso = avisos - set(errores)
        self.area.update()
        self._resaltar()

    def limpiar_marcas(self):
        self.marcar({}, set())

    def _resaltar(self):
        extras = []
        doc = self.document()
        for linea in self.lineas_error:
            bloque = doc.findBlockByNumber(linea - 1)
            if not bloque.isValid():
                continue
            sel = QTextEdit.ExtraSelection()
            sel.format.setBackground(QColor("#ffc8c8"))
            sel.format.setProperty(QTextFormat.Property.FullWidthSelection, True)
            sel.cursor = self.textCursor()
            sel.cursor.setPosition(bloque.position())
            extras.append(sel)
        if not self.isReadOnly():
            sel = QTextEdit.ExtraSelection()
            linea_actual = self.textCursor().blockNumber() + 1
            color = "#ffb0b0" if linea_actual in self.lineas_error else "#ffffd0"
            sel.format.setBackground(QColor(color))
            sel.format.setProperty(QTextFormat.Property.FullWidthSelection, True)
            sel.cursor = self.textCursor()
            sel.cursor.clearSelection()
            extras.append(sel)
        self.setExtraSelections(extras)

    def ir_a_linea(self, linea: int):
        bloque = self.document().findBlockByNumber(max(0, linea - 1))
        cursor = self.textCursor()
        cursor.setPosition(bloque.position())
        self.setTextCursor(cursor)
        self.centerCursor()
        self.setFocus()

    def event(self, ev):
        # Tooltip con el error al pasar el ratón sobre una línea marcada
        if ev.type() == ev.Type.ToolTip:
            cursor = self.cursorForPosition(self.viewport().mapFromGlobal(ev.globalPos()))
            msg = self.lineas_error.get(cursor.blockNumber() + 1)
            if msg:
                from PySide6.QtWidgets import QToolTip
                QToolTip.showText(ev.globalPos(), msg, self)
                return True
        return super().event(ev)


# ---------------------------------------------------------------------------
def _fmt(color, negrita=False):
    f = QTextCharFormat()
    f.setForeground(QColor(color))
    if negrita:
        f.setFontWeight(700)
    return f


class Resaltador(QSyntaxHighlighter):
    def __init__(self, documento, reglas, comentario, color_comentario):
        super().__init__(documento)
        self.reglas = [(re.compile(p), f) for p, f in reglas]
        self.comentario = re.compile(comentario)
        self.fmt_comentario = _fmt(color_comentario)
        self.re_cadena = re.compile(r'"(?:[^"\\\n]|\\.)*"?')

    def highlightBlock(self, texto):
        for patron, fmt in self.reglas:
            for m in patron.finditer(texto):
                self.setFormat(m.start(), m.end() - m.start(), fmt)
        cadenas = []
        for m in self.re_cadena.finditer(texto):
            cadenas.append((m.start(), m.end()))
            self.setFormat(m.start(), m.end() - m.start(), self.fmt_cadena)
        for m in self.comentario.finditer(texto):
            if not any(a <= m.start() < b for a, b in cadenas):
                self.setFormat(m.start(), len(texto) - m.start(), self.fmt_comentario)
                break


class ResaltadorPseudo(Resaltador):
    def __init__(self, documento):
        palabras = (
            r"\b(Inicio|Fin|Leer|Escribir|Si|Entonces|Sino|FinSi|Para|Hasta|Hacer|FinPara"
            r"|Mientras|FinMientras|Dimension|Funcion|Retornar|FinFuncion)\b"
        )
        reglas = [
            (palabras, _fmt(theme.NAVY, True)),
            (r"\b(Y|O|NO)\b", _fmt("#800080", True)),
            (r"\b\d+(\.\d+)?\b", _fmt("#008080")),
            (r"(>=|<=|==|!=|[<>=+\-*/])", _fmt("#800000")),
        ]
        super().__init__(documento, reglas, r"//", theme.SHADOW)
        self.fmt_cadena = _fmt("#a00000")


class ResaltadorSalida(Resaltador):
    """Colores CGA sobre fondo azul, al estilo de los IDE Borland."""

    PY = r"\b(def|if|else|elif|return|and|or|not|pass|import|True|False|None)\b"
    JS = r"\b(const|let|var|async|function|await|if|else|return|require|new)\b"
    BUILTINS_PY = r"\b(print|input|float|int|isinstance|formatear)\b"
    BUILTINS_JS = r"\b(console|log|Number|String|Symbol|process|readline|main|leer)\b"

    def __init__(self, documento, lenguaje="python"):
        self.lenguaje = lenguaje
        super().__init__(documento, self._reglas(), self._comentario(), "#aaaaaa")
        self.fmt_cadena = _fmt("#55ffff")

    def _reglas(self):
        py = self.lenguaje == "python"
        return [
            (self.PY if py else self.JS, _fmt("#ffffff", True)),
            (self.BUILTINS_PY if py else self.BUILTINS_JS, _fmt("#55ff55")),
            (r"\b\d+(\.\d+)?\b", _fmt("#ff55ff")),
            (r"(&&|>=|<=|==|!=|=>|[<>=+\-*/{}()])", _fmt("#ffffff")),
        ]

    def _comentario(self):
        return r"#" if self.lenguaje == "python" else r"//"

    def set_lenguaje(self, lenguaje):
        self.lenguaje = lenguaje
        self.reglas = [(re.compile(p), f) for p, f in self._reglas()]
        self.comentario = re.compile(self._comentario())
        self.rehighlight()


# ---------------------------------------------------------------------------
class IndicadorFase(QFrame):
    """Caja con un "LED" que muestra el estado de una fase del compilador."""

    COLORES = {
        "pendiente": ("#808080", "#404040"),
        "proceso": ("#ffff00", "#808000"),
        "ok": ("#00ff00", "#008000"),
        "error": ("#ff0000", "#800000"),
        "omitida": ("#404040", "#202020"),
    }
    TEXTO = {"pendiente": "EN ESPERA", "proceso": "ANALIZANDO", "ok": "OK",
             "error": "ERROR", "omitida": "OMITIDA"}

    def __init__(self, numero, nombre, parent=None):
        super().__init__(parent)
        self.setStyleSheet(
            f"IndicadorFase {{ background: {theme.FACE}; border: 2px solid;"
            f" border-color: {theme.SHADOW} {theme.LIGHT} {theme.LIGHT} {theme.SHADOW}; }}"
        )
        lay = QHBoxLayout(self)
        lay.setContentsMargins(6, 3, 8, 3)
        lay.setSpacing(8)
        self.led = QLabel()
        self.led.setFixedSize(14, 14)
        lay.addWidget(self.led)
        col = QVBoxLayout()
        col.setSpacing(0)
        t = QLabel(f"{numero}. {nombre}")
        t.setFont(Fuentes.texto(20))
        t.setStyleSheet("font-weight: bold;")
        self.estado = QLabel()
        self.estado.setFont(Fuentes.texto(18))
        col.addWidget(t)
        col.addWidget(self.estado)
        lay.addLayout(col, 1)
        self.set_estado("pendiente")

    def set_estado(self, estado):
        claro, oscuro = self.COLORES[estado]
        self.led.setStyleSheet(
            f"background: {claro}; border: 2px solid; border-color: {oscuro} {theme.LIGHT} {theme.LIGHT} {oscuro};"
        )
        self.estado.setText(self.TEXTO[estado])
        color = {"error": theme.ERROR, "ok": "#006000"}.get(estado, theme.DARK)
        self.estado.setStyleSheet(f"color: {color};")
