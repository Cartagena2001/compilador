"""Ventana principal de PseudoCompilador 95."""

import html
from pathlib import Path

from PySide6.QtCore import QDateTime, QPoint, Qt, QTimer, QUrl
from PySide6.QtGui import QAction, QColor, QIcon, QKeySequence, QPainter, QPixmap, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QComboBox, QDialog, QFileDialog, QHBoxLayout, QHeaderView,
    QLabel, QLineEdit, QMainWindow, QMenu, QMessageBox, QPlainTextEdit, QProgressBar, QPushButton,
    QSplitter, QTableWidget, QTableWidgetItem, QTabWidget, QTextBrowser, QTextEdit, QTreeWidget,
    QTreeWidgetItem, QVBoxLayout, QWidget,
)

from pseudocompiler import compilar
from pseudocompiler import ast_nodes
from pseudocompiler.parser import __doc__ as DOC_GRAMATICA

from . import theme
from .runner import EjecutorJS, EjecutorPython, buscar_node
from .theme import Fuentes
from .widgets import EditorCodigo, IndicadorFase, ResaltadorPseudo, ResaltadorSalida, VentanaRetro

DESTINOS = {"Python": ("python", "SALIDA.PY", ".py"), "JavaScript": ("javascript", "SALIDA.JS", ".js")}

EJEMPLOS = [
    ("Programa A - Operaciones aritméticas", "programa_a.txt"),
    ("Programa B - Condicionales anidados", "programa_b.txt"),
    ("Programa C - Factorial y suma (Para)", "programa_c.txt"),
    ("Programa D - Promedio y mayor (arreglos)", "programa_d.txt"),
    ("Programa E - Área y clasificación (funciones)", "programa_e.txt"),
    None,
    ("Errores léxicos", "errores_lexicos.txt"),
    ("Errores sintácticos", "errores_sintacticos.txt"),
    ("Errores semánticos", "errores_semanticos.txt"),
    ("Errores de ciclos, arreglos y funciones", "errores_ciclos_arreglos_funciones.txt"),
]

CODIGO_INICIAL = """// Bienvenido a PseudoCompilador 95
// Escriba o pegue su pseudocódigo y presione F5 para compilar
// o F6 para compilar y ejecutar.
Inicio
    Escribir "Ingrese su nota final:"
    Leer nota
    Si (nota >= 6) Entonces
        Escribir "Aprobado con ", nota
    Sino
        Escribir "Reprobado"
    FinSi
Fin
"""

ICONO_PIXELES = [
    "................",
    ".##############.",
    ".#............#.",
    ".#.CCCCCCCCCC.#.",
    ".#.C>.......C.#.",
    ".#.C.--.....C.#.",
    ".#.C.----...C.#.",
    ".#.C.--.....C.#.",
    ".#.CCCCCCCCCC.#.",
    ".#............#.",
    ".##############.",
    "......####......",
    "....########....",
    "..############..",
    "..#..........#..",
    "..############..",
]


def crear_icono() -> QIcon:
    """Icono pixel-art de una computadora de los 90."""
    colores = {"#": QColor("#000000"), ".": QColor(theme.FACE), "C": QColor(theme.NAVY),
               ">": QColor("#ffff55"), "-": QColor("#55ff55")}
    pix = QPixmap(64, 64)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    for y, fila in enumerate(ICONO_PIXELES):
        for x, c in enumerate(fila):
            # el gris solo se pinta dentro del marco del monitor
            if c == "." and not (1 <= y <= 10 and 1 <= x <= 14):
                continue
            p.fillRect(x * 4, y * 4, 4, 4, colores[c])
    p.end()
    return QIcon(pix)


class VentanaPrincipal(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PseudoCompilador 95 - Pseudocódigo a Python y JavaScript")
        self.setWindowIcon(crear_icono())
        self.resize(1440, 920)

        self.archivo: Path | None = None
        self.resultado = None
        self.codigo_compilado = None
        self._pasos = []
        self._ejecutar_al_terminar = False
        self.ejecutor = None
        self.animar = True

        self._crear_acciones()
        self._crear_menu()
        self._crear_barra_herramientas()
        self._crear_centro()
        self._crear_barra_estado()

        self.editor.setPlainText(CODIGO_INICIAL)
        self._mostrar_salida()
        self._dos_bienvenida()

    # ------------------------------------------------------------------ UI
    def _crear_acciones(self):
        def accion(texto, atajo=None, slot=None):
            a = QAction(texto, self)
            if atajo:
                a.setShortcut(QKeySequence(atajo))
            if slot:
                a.triggered.connect(slot)
            self.addAction(a)
            return a

        self.a_nuevo = accion("&Nuevo", "Ctrl+N", self.nuevo)
        self.a_abrir = accion("&Abrir...", "Ctrl+O", self.abrir)
        self.a_guardar = accion("&Guardar", "Ctrl+S", self.guardar)
        self.a_guardar_como = accion("Guardar &como...", "Ctrl+Shift+S", self.guardar_como)
        self.a_guardar_salida = accion("Guardar código &generado...", "Ctrl+E", self.guardar_salida)
        self.a_salir = accion("&Salir", "Alt+F4", self.close)
        self.a_compilar = accion("&Compilar", "F5", self.compilar)
        self.a_ejecutar = accion("&Ejecutar", "F6", self.ejecutar)
        self.a_detener = accion("&Detener", "Shift+F6", self.detener)
        self.a_animar = accion("&Animar el proceso de compilación")
        self.a_animar.setCheckable(True)
        self.a_animar.setChecked(True)
        self.a_animar.toggled.connect(lambda v: setattr(self, "animar", v))
        self.a_gramatica = accion("&Gramática del lenguaje", "F1", self.mostrar_gramatica)
        self.a_acerca = accion("&Acerca de...", None, self.acerca_de)

    def _menu_ejemplos(self, padre):
        menu = QMenu("E&jemplos", padre)
        for item in EJEMPLOS:
            if item is None:
                menu.addSeparator()
                continue
            nombre, archivo = item
            menu.addAction(nombre, lambda a=archivo: self.cargar_ejemplo(a))
        return menu

    def _crear_menu(self):
        mb = self.menuBar()
        mb.setFont(Fuentes.texto(20))
        m = mb.addMenu("&Archivo")
        for a in (self.a_nuevo, self.a_abrir, self.a_guardar, self.a_guardar_como):
            m.addAction(a)
        m.addSeparator()
        m.addAction(self.a_guardar_salida)
        m.addSeparator()
        m.addAction(self.a_salir)
        m = mb.addMenu("&Compilar")
        m.addAction(self.a_compilar)
        m.addAction(self.a_ejecutar)
        m.addAction(self.a_detener)
        m.addSeparator()
        m.addAction(self.a_animar)
        self.menu_ejemplos = self._menu_ejemplos(self)
        mb.addMenu(self.menu_ejemplos)
        m = mb.addMenu("A&yuda")
        m.addAction(self.a_gramatica)
        m.addAction(self.a_acerca)
        for menu in mb.findChildren(QMenu):
            menu.setFont(Fuentes.texto(20))

    def _boton(self, texto, slot, tip="", principal=False):
        b = QPushButton(texto)
        b.setFont(Fuentes.pixel(8) if principal else Fuentes.texto(20))
        if principal:
            b.setObjectName("BotonPrincipal")
        b.setToolTip(tip)
        b.clicked.connect(slot)
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        return b

    def _crear_barra_herramientas(self):
        tb = self.addToolBar("Herramientas")
        tb.setMovable(False)
        self.b_compilar = self._boton("> COMPILAR", self.compilar, "Compilar el pseudocódigo (F5)", True)
        self.b_ejecutar = self._boton(">> EJECUTAR", self.ejecutar, "Compilar y ejecutar (F6)", True)
        self.b_detener = self._boton("[] DETENER", self.detener, "Detener la ejecución (Shift+F6)", True)
        self.b_detener.setEnabled(False)
        for b in (self.b_compilar, self.b_ejecutar, self.b_detener):
            tb.addWidget(b)
        tb.addSeparator()
        lbl = QLabel(" Compilar a: ")
        lbl.setFont(Fuentes.texto(20))
        tb.addWidget(lbl)
        self.combo = QComboBox()
        self.combo.setFont(Fuentes.texto(20))
        self.combo.addItems(list(DESTINOS))
        self.combo.currentTextChanged.connect(self._mostrar_salida)
        tb.addWidget(self.combo)
        tb.addSeparator()
        tb.addWidget(self._boton("Nuevo", self.nuevo, "Nuevo archivo (Ctrl+N)"))
        tb.addWidget(self._boton("Abrir...", self.abrir, "Abrir pseudocódigo (Ctrl+O)"))
        tb.addWidget(self._boton("Guardar", self.guardar, "Guardar pseudocódigo (Ctrl+S)"))
        tb.addWidget(self._boton("Exportar", self.guardar_salida, "Guardar el código generado (Ctrl+E)"))
        b = self._boton("Ejemplos", lambda: None, "Cargar un programa de ejemplo")
        b.clicked.disconnect()
        b.clicked.connect(lambda: self.menu_ejemplos.exec(b.mapToGlobal(b.rect().bottomLeft())))
        tb.addWidget(b)

    def _crear_centro(self):
        escritorio = QWidget(objectName="Escritorio")
        lay = QVBoxLayout(escritorio)
        lay.setContentsMargins(10, 10, 10, 10)

        # -- Editor --------------------------------------------------------
        self.v_editor = VentanaRetro("PSEUDO.TXT - Editor de pseudocódigo", "≡")
        self.editor = EditorCodigo(theme.FACE, theme.SHADOW)
        self.editor.setPlaceholderText("Escriba o pegue aquí su pseudocódigo...")
        ResaltadorPseudo(self.editor.document())
        self.editor.cursorPositionChanged.connect(self._actualizar_cursor)
        self.editor.textChanged.connect(self._texto_cambiado)
        self.v_editor.agregar(self.editor, 1)

        # -- Salida --------------------------------------------------------
        self.v_salida = VentanaRetro("SALIDA.PY - Código generado", "▤")
        self.salida = EditorCodigo(theme.NAVY, "#aaaaaa", solo_lectura=True)
        self.salida.setObjectName("Salida")
        self.resaltador_salida = ResaltadorSalida(self.salida.document())
        self.v_salida.agregar(self.salida, 1)
        b_copiar = QPushButton("Copiar", objectName="BotonTitulo")
        b_copiar.setStyleSheet("QPushButton#BotonTitulo { min-width: 52px; max-width: 52px; }")
        b_copiar.setFont(Fuentes.texto(16))
        b_copiar.setToolTip("Copiar el código generado al portapapeles")
        b_copiar.clicked.connect(self._copiar_salida)
        self.v_salida.extra.addWidget(b_copiar)

        # -- Consola -------------------------------------------------------
        self.v_consola = VentanaRetro("MS-DOS - Consola de ejecución", "▶")
        self.consola = QTextEdit(objectName="Dos")
        self.consola.setReadOnly(True)
        self.consola.setFont(Fuentes.texto(22))
        self.v_consola.agregar(self.consola, 1)
        fila = QHBoxLayout()
        fila.setSpacing(4)
        prompt = QLabel("Entrada >")
        prompt.setFont(Fuentes.texto(20))
        self.entrada = QLineEdit(objectName="EntradaDos")
        self.entrada.setFont(Fuentes.texto(22))
        self.entrada.setPlaceholderText("Escriba un valor y presione Enter")
        self.entrada.returnPressed.connect(self._enviar_entrada)
        self.entrada.setEnabled(False)
        b_enviar = self._boton("Enviar", self._enviar_entrada)
        b_limpiar = self._boton("Limpiar", self.consola.clear)
        fila.addWidget(prompt)
        fila.addWidget(self.entrada, 1)
        fila.addWidget(b_enviar)
        fila.addWidget(b_limpiar)
        self.v_consola.cuerpo.addLayout(fila)

        # -- Proceso de compilación -----------------------------------------
        self.v_proceso = VentanaRetro("COMPILAR.EXE - Proceso de compilación", "⚙")
        fases = QHBoxLayout()
        fases.setSpacing(6)
        self.indicadores = {}
        for i, (clave, nombre) in enumerate(
            [("lexico", "LÉXICO"), ("sintactico", "SINTÁCTICO"), ("semantico", "SEMÁNTICO"), ("sintesis", "SÍNTESIS")], 1
        ):
            ind = IndicadorFase(i, nombre)
            self.indicadores[clave] = ind
            fases.addWidget(ind, 1)
            if i < 4:
                flecha = QLabel(">")
                flecha.setFont(Fuentes.pixel(8))
                fases.addWidget(flecha)
        self.v_proceso.cuerpo.addLayout(fases)
        self.progreso = QProgressBar()
        self.progreso.setRange(0, 100)
        self.progreso.setValue(0)
        self.progreso.setFixedHeight(18)
        self.v_proceso.agregar(self.progreso)

        self.tabs = QTabWidget()
        self.tabs.setFont(Fuentes.texto(20))
        self.log = QTextBrowser(objectName="Dos")
        self.log.setFont(Fuentes.texto(21))
        self.log.setOpenLinks(False)
        self.log.anchorClicked.connect(self._click_log)
        self.tabla_errores = self._tabla(["Tipo", "Fase", "Línea", "Col.", "Descripción"])
        self.tabla_errores.cellDoubleClicked.connect(self._click_error)
        self.tabla_tokens = self._tabla(["N.°", "Lexema", "Tipo de token", "Línea", "Columna"])
        self.tabla_tokens.cellDoubleClicked.connect(
            lambda r, _c: self.editor.ir_a_linea(int(self.tabla_tokens.item(r, 3).text()))
        )
        self.arbol = QTreeWidget()
        self.arbol.setHeaderHidden(True)
        self.arbol.setFont(Fuentes.texto(20))
        self.tabla_simbolos = self._tabla(
            ["Identificador", "Categoría", "Tipo", "Ámbito", "Línea donde se define", "Definido por",
             "Usado en líneas", "Nombre en Python", "Nombre en JS"]
        )
        self.tabs.addTab(self.log, "Proceso")
        self.tabs.addTab(self.tabla_errores, "Errores (0)")
        self.tabs.addTab(self.tabla_tokens, "Tokens (léxico)")
        self.tabs.addTab(self.arbol, "Árbol sintáctico (AST)")
        self.tabs.addTab(self.tabla_simbolos, "Tabla de símbolos")
        self.v_proceso.agregar(self.tabs, 1)

        # -- Distribución --------------------------------------------------
        derecha = QSplitter(Qt.Orientation.Vertical)
        derecha.addWidget(self.v_salida)
        derecha.addWidget(self.v_consola)
        derecha.setSizes([360, 240])
        arriba = QSplitter(Qt.Orientation.Horizontal)
        arriba.addWidget(self.v_editor)
        arriba.addWidget(derecha)
        arriba.setSizes([700, 700])
        principal = QSplitter(Qt.Orientation.Vertical)
        principal.addWidget(arriba)
        principal.addWidget(self.v_proceso)
        principal.setSizes([560, 320])
        for s in (derecha, arriba, principal):
            s.setHandleWidth(8)
            s.setChildrenCollapsible(False)
        lay.addWidget(principal)
        self.setCentralWidget(escritorio)

        self.ventanas = [self.v_editor, self.v_salida, self.v_consola, self.v_proceso]
        self._maximizada = None
        for v in self.ventanas:
            v.maximizar.connect(self._toggle_maximizar)
            v.barra.mousePressEvent = lambda _e, v=v: self._activar(v)
        self._activar(self.v_editor)

    def _tabla(self, columnas):
        t = QTableWidget(0, len(columnas))
        t.setHorizontalHeaderLabels(columnas)
        t.setFont(Fuentes.texto(20))
        t.horizontalHeader().setFont(Fuentes.texto(20))
        t.horizontalHeader().setStretchLastSection(True)
        t.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        t.verticalHeader().setVisible(False)
        t.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        t.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        t.setAlternatingRowColors(False)
        t.verticalHeader().setDefaultSectionSize(24)
        return t

    def _crear_barra_estado(self):
        sb = self.statusBar()
        sb.setFont(Fuentes.texto(20))
        self.b_inicio = QPushButton("Inicio")
        self.b_inicio.setFont(Fuentes.pixel(8))
        self.b_inicio.setToolTip("Menú de inicio")
        menu = QMenu(self)
        menu.setFont(Fuentes.texto(20))
        menu.addMenu(self._menu_ejemplos(menu))
        menu.addAction(self.a_gramatica)
        menu.addAction(self.a_acerca)
        menu.addSeparator()
        menu.addAction(self.a_salir)
        self.b_inicio.clicked.connect(
            lambda: menu.exec(self.b_inicio.mapToGlobal(QPoint(0, -menu.sizeHint().height())))
        )
        sb.addWidget(self.b_inicio)
        self.lbl_estado = QLabel("Listo")
        self.lbl_estado.setFont(Fuentes.texto(20))
        sb.addWidget(self.lbl_estado, 1)
        self.lbl_cursor = QLabel(objectName="Celda")
        self.lbl_errores = QLabel(objectName="Celda")
        self.lbl_reloj = QLabel(objectName="Celda")
        for l in (self.lbl_cursor, self.lbl_errores, self.lbl_reloj):
            l.setFont(Fuentes.texto(20))
            sb.addPermanentWidget(l)
        self.lbl_errores.setText("Sin compilar")
        self._actualizar_cursor()
        self._reloj()
        self._timer_reloj = QTimer(self, timeout=self._reloj, interval=10_000)
        self._timer_reloj.start()

    def _reloj(self):
        self.lbl_reloj.setText(QDateTime.currentDateTime().toString("hh:mm"))

    # ------------------------------------------------------------- ventanas
    def _activar(self, ventana):
        for v in self.ventanas:
            v.barra.setProperty("inactiva", v is not ventana)
            v.barra.style().unpolish(v.barra)
            v.barra.style().polish(v.barra)

    def _toggle_maximizar(self, ventana):
        if self._maximizada is ventana:
            for v in self.ventanas:
                v.show()
            self._maximizada = None
        else:
            for v in self.ventanas:
                v.setVisible(v is ventana)
            self._maximizada = ventana
        self._activar(ventana)
        # El separador derecho se oculta si ambas ventanas lo están
        derecha = self.v_salida.parentWidget()
        derecha.setVisible(self.v_salida.isVisibleTo(derecha) or self.v_consola.isVisibleTo(derecha))
        arriba = self.v_editor.parentWidget()
        arriba.setVisible(self.v_editor.isVisibleTo(arriba) or derecha.isVisibleTo(arriba))

    def _actualizar_cursor(self):
        c = self.editor.textCursor()
        self.lbl_cursor.setText(f"Ln {c.blockNumber() + 1}, Col {c.positionInBlock() + 1}")

    def _texto_cambiado(self):
        if self.editor.lineas_error or self.editor.lineas_aviso:
            self.editor.limpiar_marcas()
        nombre = self.archivo.name.upper() if self.archivo else "PSEUDO.TXT"
        modificado = self.editor.document().isModified()
        self.v_editor.set_titulo(f"{nombre}{'*' if modificado else ''} - Editor de pseudocódigo")

    # ------------------------------------------------------------ compilar
    def _destino(self):
        return DESTINOS[self.combo.currentText()]

    def compilar(self, ejecutar_despues=False):
        if self._pasos:
            return
        codigo = self.editor.toPlainText()
        self.resultado = compilar(codigo)
        self.codigo_compilado = codigo
        self._ejecutar_al_terminar = ejecutar_despues
        self.editor.limpiar_marcas()
        self.log.clear()
        self.progreso.setValue(0)
        for ind in self.indicadores.values():
            ind.set_estado("pendiente")
        self.tabs.setCurrentWidget(self.log)
        self.b_compilar.setEnabled(False)
        self.b_ejecutar.setEnabled(False)
        self.lbl_estado.setText("Compilando...")

        lenguaje = self.combo.currentText().upper()
        nombre = self.archivo.name if self.archivo else "PSEUDO.TXT"
        self._dos(f"C:\\PSEUDO> COMPILAR.EXE {html.escape(nombre.upper())} /DESTINO:{lenguaje}", "#ffffff")
        self._dos("PseudoCompilador 95  versión 1.0  -  Autómatas y Compiladores", "#aaaaaa")
        self._dos("=" * 64, "#555555")

        self._pasos = []
        self._bloque_fase = {}
        total = len(self.resultado.fases)
        for i, fase in enumerate(self.resultado.fases):
            self._pasos.append(lambda f=fase, i=i: self._paso_inicio(f, i))
            self._pasos.append(lambda f=fase, i=i, t=total: self._paso_fin(f, i, t))
        self._pasos.append(self._finalizar)
        self._siguiente_paso()

    def _siguiente_paso(self):
        if not self._pasos:
            return
        paso = self._pasos.pop(0)
        paso()
        if self._pasos:
            QTimer.singleShot(260 if self.animar else 0, self._siguiente_paso)

    DESCRIPCION_FASE = {
        "lexico": "Reconociendo tokens: palabras reservadas, identificadores, números, cadenas y operadores...",
        "sintactico": "Verificando la gramática (EBNF) y el anidamiento de los bloques Si, Para, Mientras y Funcion...",
        "semantico": "Comprobando variables, tipos, arreglos, funciones, condiciones y posibles divisiones entre cero...",
        "sintesis": "Recorriendo el AST y traduciendo a Python y JavaScript...",
    }

    def _paso_inicio(self, fase, i):
        self._dos("")
        self._bloque_fase[fase.clave] = self.log.document().blockCount()
        self._dos(f"[FASE {i + 1}] {fase.titulo}", "#ffffff", negrita=True)
        if fase.estado == "omitida":
            return
        self.indicadores[fase.clave].set_estado("proceso")
        self._dos("  " + self.DESCRIPCION_FASE[fase.clave], "#aaaaaa")

    def _paso_fin(self, fase, i, total):
        self.progreso.setValue(int((i + 1) * 100 / total))
        self.indicadores[fase.clave].set_estado(fase.estado)
        if fase.estado == "omitida":
            self._dos("  OMITIDA: corrija los errores de la fase anterior para continuar.", "#777777")
            return
        if fase.estado == "ok":
            self._dos(f"  [OK] {fase.resumen}", "#55ff55")
        else:
            n = len(fase.errores)
            self._dos(f"  [ERROR] {n} error{'es' if n != 1 else ''} {fase.titulo.split()[-1].lower()}{'s' if n != 1 else ''}:", "#ff5555", negrita=True)
            for e in fase.errores:
                self._dos_error(e, "#ff5555")
        for a in fase.advertencias:
            self._dos_error(a, "#ffff55", "[!] ")

    def _dos_error(self, e, color, marca="  > "):
        enlace = f'<a href="linea:{e.linea}" style="color:{color}; text-decoration: underline;">Línea {e.linea}' \
                 f'{f", columna {e.columna}" if e.columna else ""}</a>'
        self.log.append(
            f'<span style="color:{color}; white-space:pre;">    {html.escape(marca)}</span>{enlace}'
            f'<span style="color:{color};">: {html.escape(e.mensaje)}</span>'
        )

    def _finalizar(self):
        r = self.resultado
        self._dos("")
        if r.exito:
            avisos = len(r.advertencias)
            extra = f" con {avisos} advertencia{'s' if avisos != 1 else ''}" if avisos else ""
            self._dos(f"*** COMPILACIÓN EXITOSA{extra.upper()} ***", "#55ff55", negrita=True)
            self.lbl_estado.setText("Compilación exitosa")
        else:
            fallida = next(f for f in r.fases if f.estado == "error")
            n = len(r.errores)
            self._dos(
                f"*** COMPILACIÓN FALLIDA: {n} error{'es' if n != 1 else ''} en {fallida.titulo} ***",
                "#ff5555", negrita=True,
            )
            # mostrar el detalle de la fase que falló
            QTimer.singleShot(0, lambda c=fallida.clave: self._scroll_log(self._bloque_fase[c]))
            primero = r.errores[0]
            self.lbl_estado.setText(f"Error {primero.fase.lower()} en línea {primero.linea}: {primero.mensaje}")
        self.lbl_errores.setText(f"Errores: {len(r.errores)}  Avisos: {len(r.advertencias)}")

        self.editor.marcar(
            {e.linea: str(e) for e in reversed(r.errores)},
            {a.linea for a in r.advertencias},
        )
        self._llenar_errores()
        self._llenar_tokens()
        self._llenar_arbol()
        self._llenar_simbolos()
        self._mostrar_salida()
        self.b_compilar.setEnabled(True)
        self.b_ejecutar.setEnabled(True)
        if self._ejecutar_al_terminar:
            self._ejecutar_al_terminar = False
            QTimer.singleShot(0, self._iniciar_ejecucion)

    def _scroll_log(self, numero_bloque):
        doc = self.log.document()
        bloque = doc.findBlockByNumber(numero_bloque)
        y = doc.documentLayout().blockBoundingRect(bloque).top()
        self.log.verticalScrollBar().setValue(int(y))

    def _dos(self, texto, color="#c0c0c0", negrita=False):
        peso = "font-weight:bold;" if negrita else ""
        self.log.append(f'<span style="color:{color}; white-space:pre; {peso}">{html.escape(texto)}</span>')

    def _dos_bienvenida(self):
        self._dos("PseudoCompilador 95 [Versión 1.0]", "#ffffff")
        self._dos("(C) Autómatas y Compiladores - UDB Virtual", "#aaaaaa")
        self._dos("")
        self._dos("Presione F5 para compilar o F6 para compilar y ejecutar.", "#c0c0c0")
        self._dos("Cada fase (léxica, sintáctica, semántica y síntesis) se mostrará aquí.", "#c0c0c0")
        self._consola("Consola lista. El programa se ejecutará aquí (F6).\n", "info")

    # --------------------------------------------------- llenado de paneles
    def _llenar_errores(self):
        r = self.resultado
        filas = [("Error", e) for e in r.errores] + [("Aviso", a) for a in r.advertencias]
        t = self.tabla_errores
        t.setRowCount(len(filas))
        for i, (tipo, e) in enumerate(filas):
            valores = [tipo, e.fase, str(e.linea), str(e.columna or ""), e.mensaje]
            for j, v in enumerate(valores):
                item = QTableWidgetItem(v)
                if tipo == "Error":
                    item.setForeground(QColor(theme.ERROR))
                t.setItem(i, j, item)
        self.tabs.setTabText(1, f"Errores ({len(r.errores)})")

    def _llenar_tokens(self):
        tokens = [t for t in self.resultado.tokens if t.tipo != "EOF"]
        t = self.tabla_tokens
        t.setRowCount(len(tokens))
        for i, tok in enumerate(tokens):
            lexema = f'"{tok.lexema}"' if tok.tipo == "CADENA" else tok.lexema
            for j, v in enumerate([str(i + 1), lexema, tok.descripcion, str(tok.linea), str(tok.columna)]):
                t.setItem(i, j, QTableWidgetItem(v))

    def _llenar_arbol(self):
        self.arbol.clear()
        r = self.resultado
        if r.ast is None or not r.fases[1].estado == "ok":
            QTreeWidgetItem(self.arbol, ["(El árbol se construye cuando el análisis sintáctico no tiene errores)"])
            return

        def agregar(padre, nodo):
            item = QTreeWidgetItem(padre, [ast_nodes._etiqueta(nodo)])
            for h in ast_nodes._hijos(nodo):
                agregar(item, h)
            return item

        agregar(self.arbol, r.ast)
        self.arbol.expandAll()

    def _llenar_simbolos(self):
        t = self.tabla_simbolos
        tabla = self.resultado.tabla
        simbolos = list(tabla) if tabla else []
        t.setRowCount(len(simbolos))
        for i, s in enumerate(simbolos):
            usos = ", ".join(str(u) for u in sorted(set(s.usos))) or "-"
            valores = [s.nombre, s.categoria, s.tipo, s.ambito, str(s.linea_definicion),
                       f"{s.definido_por} ({s.asignaciones}x)", usos, s.nombre_py, s.nombre_js]
            for j, v in enumerate(valores):
                t.setItem(i, j, QTableWidgetItem(v))

    def _mostrar_salida(self, *_):
        lenguaje, archivo, _ext = self._destino()
        self.v_salida.set_titulo(f"{archivo} - Código generado ({self.combo.currentText()})")
        self.resaltador_salida.set_lenguaje(lenguaje)
        com = "#" if lenguaje == "python" else "//"
        r = self.resultado
        if r is None:
            texto = f"{com} Aquí aparecerá el código {self.combo.currentText()} generado.\n{com} Presione F5 para compilar."
        elif not r.exito:
            texto = (f"{com} No se generó código: la compilación terminó con errores.\n"
                     f"{com} Revise el panel 'Proceso de compilación'.")
        else:
            texto = r.python if lenguaje == "python" else r.javascript
        self.salida.setPlainText(texto)

    # ------------------------------------------------------------ ejecutar
    def ejecutar(self):
        if self.ejecutor and self.ejecutor.ejecutando():
            return
        if self.resultado is None or self.codigo_compilado != self.editor.toPlainText():
            self.compilar(ejecutar_despues=True)
        else:
            self._iniciar_ejecucion()

    def _iniciar_ejecucion(self):
        r = self.resultado
        if not r.exito:
            self._consola("\nNo se puede ejecutar: el programa tiene errores de compilación.\n", "err")
            return
        lenguaje = self._destino()[0]
        if self.ejecutor:
            self.ejecutor.deleteLater()
        if lenguaje == "python":
            self.ejecutor = EjecutorPython(self)
            codigo, mapa, cmd = r.python, r.mapa_py, "python salida.py"
        else:
            self.ejecutor = EjecutorJS(self)
            codigo, mapa, cmd = r.javascript, r.mapa_js, "node salida.js"
        self.ejecutor.salida.connect(self._consola)
        self.ejecutor.terminado.connect(self._ejecucion_terminada)
        self._consola(f"\nC:\\PSEUDO> {cmd}\n", "cmd")
        self.entrada.setEnabled(True)
        self.b_detener.setEnabled(True)
        self.b_ejecutar.setEnabled(False)
        self.lbl_estado.setText("Ejecutando...")
        self.ejecutor.iniciar(codigo, mapa)
        self.entrada.setFocus()

    def _ejecucion_terminada(self, codigo):
        self.entrada.setEnabled(False)
        self.b_detener.setEnabled(False)
        self.b_ejecutar.setEnabled(True)
        estado = "terminó correctamente" if codigo == 0 else f"terminó con código {codigo}"
        self._consola(f"\n[Programa {estado}]\n", "info")
        self.lbl_estado.setText(f"Ejecución: el programa {estado}")

    def detener(self):
        if self.ejecutor:
            self.ejecutor.detener()

    def _enviar_entrada(self):
        if not (self.ejecutor and self.ejecutor.ejecutando()):
            return
        texto = self.entrada.text()
        self.entrada.clear()
        self._consola(texto + "\n", "in")
        self.ejecutor.enviar(texto)

    COLORES_CONSOLA = {"out": "#c0c0c0", "err": "#ff5555", "info": "#55ffff", "in": "#ffff55", "cmd": "#ffffff"}

    def _consola(self, texto, tipo="out"):
        cursor = self.consola.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(self.COLORES_CONSOLA.get(tipo, "#c0c0c0")))
        fmt.setFont(Fuentes.texto(22))
        cursor.insertText(texto, fmt)
        self.consola.setTextCursor(cursor)
        self.consola.ensureCursorVisible()

    # ------------------------------------------------------------- enlaces
    def _click_log(self, url: QUrl):
        texto = url.toString()
        if texto.startswith("linea:"):
            self.editor.ir_a_linea(int(texto.split(":")[1]))

    def _click_error(self, fila, _col):
        self.editor.ir_a_linea(int(self.tabla_errores.item(fila, 2).text()))

    def _copiar_salida(self):
        QApplication.clipboard().setText(self.salida.toPlainText())
        self.lbl_estado.setText("Código generado copiado al portapapeles")

    # ------------------------------------------------------------ archivos
    def _confirmar_descartar(self) -> bool:
        if not self.editor.document().isModified():
            return True
        r = QMessageBox.question(
            self, "PseudoCompilador 95", "El archivo tiene cambios sin guardar.\n¿Desea guardarlos?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel,
        )
        if r == QMessageBox.StandardButton.Cancel:
            return False
        if r == QMessageBox.StandardButton.Yes:
            return self.guardar()
        return True

    def _cargar_texto(self, texto, archivo):
        self.archivo = archivo
        self.editor.setPlainText(texto)
        self.editor.document().setModified(False)
        self.resultado = None
        self.codigo_compilado = None
        self._texto_cambiado()
        self._mostrar_salida()
        for ind in self.indicadores.values():
            ind.set_estado("pendiente")
        self.progreso.setValue(0)
        self.lbl_errores.setText("Sin compilar")

    def nuevo(self):
        if self._confirmar_descartar():
            self._cargar_texto("Inicio\n    \nFin\n", None)
            self.editor.ir_a_linea(2)

    def abrir(self):
        if not self._confirmar_descartar():
            return
        ruta, _ = QFileDialog.getOpenFileName(
            self, "Abrir pseudocódigo", "", "Pseudocódigo (*.txt *.psc *.pseudo);;Todos (*)"
        )
        if ruta:
            p = Path(ruta)
            self._cargar_texto(p.read_text(encoding="utf-8", errors="replace"), p)
            self.lbl_estado.setText(f"Abierto: {p.name}")

    def cargar_ejemplo(self, archivo):
        if not self._confirmar_descartar():
            return
        p = theme.recurso("examples", archivo)
        self._cargar_texto(p.read_text(encoding="utf-8"), None)
        self.v_editor.set_titulo(f"{archivo.upper()} - Editor de pseudocódigo (ejemplo)")
        self.lbl_estado.setText(f"Ejemplo cargado: {archivo}. Presione F5 para compilar.")

    def guardar(self) -> bool:
        if self.archivo is None:
            return self.guardar_como()
        self.archivo.write_text(self.editor.toPlainText(), encoding="utf-8")
        self.editor.document().setModified(False)
        self._texto_cambiado()
        self.lbl_estado.setText(f"Guardado: {self.archivo.name}")
        return True

    def guardar_como(self) -> bool:
        ruta, _ = QFileDialog.getSaveFileName(self, "Guardar pseudocódigo", "programa.txt", "Pseudocódigo (*.txt)")
        if not ruta:
            return False
        self.archivo = Path(ruta)
        return self.guardar()

    def guardar_salida(self):
        r = self.resultado
        if r is None or not r.exito or self.codigo_compilado != self.editor.toPlainText():
            QMessageBox.information(self, "Exportar", "Primero compile el programa sin errores (F5).")
            return
        lenguaje, archivo, ext = self._destino()
        ruta, _ = QFileDialog.getSaveFileName(self, "Guardar código generado", archivo.lower(), f"*{ext}")
        if ruta:
            Path(ruta).write_text(r.python if lenguaje == "python" else r.javascript, encoding="utf-8")
            self.lbl_estado.setText(f"Código guardado en {Path(ruta).name}")

    # --------------------------------------------------------------- ayuda
    def mostrar_gramatica(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("Gramática del pseudocódigo (EBNF)")
        dlg.resize(820, 640)
        lay = QVBoxLayout(dlg)
        v = VentanaRetro("GRAMATICA.TXT - Referencia del lenguaje", "?")
        v.btn_max.hide()
        txt = QPlainTextEdit(objectName="Dos")
        txt.setReadOnly(True)
        txt.setFont(Fuentes.texto(21))
        inicio = DOC_GRAMATICA.index("programa ")
        fin = DOC_GRAMATICA.index("Extensión")
        txt.setPlainText(
            "PALABRAS RESERVADAS\n  Inicio Fin Leer Escribir Si Entonces Sino FinSi\n"
            "  Para Hasta Hacer FinPara Mientras FinMientras Dimension\n"
            "  Funcion Retornar FinFuncion Y O NO\n\n"
            "OPERADORES\n  Aritméticos: + - * /     Relacionales: >= <= > < == !=\n"
            "  Asignación: =             Lógicos: Y O NO\n\n"
            "REGLAS DE PRODUCCIÓN (EBNF)\n" + DOC_GRAMATICA[inicio:fin].rstrip() + "\n\n"
            "NOTAS\n"
            "  * Las comparaciones van con o sin paréntesis: Si (a > 5) Y b < 3 Entonces\n"
            "  * Los arreglos comienzan en 1: Dimension v[n] crea de v[1] a v[n].\n"
            "  * Las funciones se declaran antes de llamarse y solo ven sus parámetros\n"
            "    y variables locales. Terminan con Retornar <variable de retorno>.\n"
            "  * Las palabras reservadas distinguen mayúsculas y minúsculas.\n"
            "  * Los identificadores usan letras sin tilde, dígitos y '_'.\n"
            "  * Comentarios: // hasta el final de la línea.\n"
            "  * Se admite el menos unario: x = -5\n"
        )
        v.agregar(txt, 1)
        lay.addWidget(v)
        b = self._boton("Aceptar", dlg.accept)
        lay.addWidget(b, 0, Qt.AlignmentFlag.AlignRight)
        dlg.exec()

    def acerca_de(self):
        node = buscar_node()
        QMessageBox.about(
            self, "Acerca de PseudoCompilador 95",
            "<b>PseudoCompilador 95</b> versión 1.0<br><br>"
            "Compilador de pseudocódigo en español a <b>Python</b> y <b>JavaScript</b>.<br>"
            "Fases: análisis léxico, sintáctico, semántico y generación de código.<br><br>"
            "Autómatas y Compiladores (AYC941) - Universidad Don Bosco Virtual<br><br>"
            f"Node.js: {html.escape(node) if node else 'no encontrado (solo se ejecutará Python)'}<br>"
            "Fuentes: VT323 y Press Start 2P (SIL Open Font License).",
        )

    def closeEvent(self, event):
        if not self._confirmar_descartar():
            event.ignore()
            return
        if self.ejecutor:
            self.ejecutor.detener()
        event.accept()
