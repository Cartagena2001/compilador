"""Orquestador del compilador: ejecuta las fases en orden y guarda el
resultado de cada una para mostrar el proceso en la interfaz."""

from dataclasses import dataclass, field

from . import ast_nodes, codegen, lexer, parser, semantic
from .errors import LEXICO, SEMANTICO, SINTACTICO, ErrorManager

FASES = [
    ("lexico", "ANÁLISIS LÉXICO", LEXICO),
    ("sintactico", "ANÁLISIS SINTÁCTICO", SINTACTICO),
    ("semantico", "ANÁLISIS SEMÁNTICO", SEMANTICO),
    ("sintesis", "GENERACIÓN DE CÓDIGO", None),
]


@dataclass
class ResultadoFase:
    clave: str
    titulo: str
    estado: str = "pendiente"       # pendiente | ok | error | omitida
    errores: list = field(default_factory=list)
    advertencias: list = field(default_factory=list)
    resumen: str = ""


@dataclass
class ResultadoCompilacion:
    fases: list
    tokens: list = field(default_factory=list)
    ast: object = None
    arbol: list = field(default_factory=list)
    tabla: object = None
    python: str = ""
    javascript: str = ""
    mapa_py: list = field(default_factory=list)
    mapa_js: list = field(default_factory=list)
    gestor: ErrorManager = None

    @property
    def exito(self) -> bool:
        return not self.gestor.hay_errores

    @property
    def errores(self):
        return self.gestor.errores

    @property
    def advertencias(self):
        return self.gestor.advertencias


def compilar(codigo: str) -> ResultadoCompilacion:
    gestor = ErrorManager()
    fases = {clave: ResultadoFase(clave, titulo) for clave, titulo, _ in FASES}
    res = ResultadoCompilacion(fases=list(fases.values()), gestor=gestor)

    def cerrar(clave, nombre_fase, resumen):
        f = fases[clave]
        f.errores = gestor.errores_de(nombre_fase)
        f.advertencias = gestor.advertencias_de(nombre_fase)
        f.estado = "error" if f.errores else "ok"
        f.resumen = resumen
        return f.estado == "ok"

    def omitir_desde(clave):
        activo = False
        for c, _, _ in FASES:
            activo = activo or c == clave
            if activo:
                fases[c].estado = "omitida"

    # 1. Léxico
    res.tokens = lexer.tokenizar(codigo, gestor)
    n = len(res.tokens) - 1
    if not cerrar("lexico", LEXICO, f"{n} tokens reconocidos"):
        omitir_desde("sintactico")
        return res

    # 2. Sintáctico
    res.ast = parser.analizar(res.tokens, gestor)
    if not cerrar("sintactico", SINTACTICO, f"{len(res.ast.instrucciones)} instrucciones de primer nivel"):
        omitir_desde("semantico")
        return res
    res.arbol = ast_nodes.arbol_texto(res.ast)

    # 3. Semántico
    res.tabla = semantic.analizar(res.ast, gestor)
    if not cerrar("semantico", SEMANTICO, f"{len(res.tabla)} símbolos en la tabla"):
        omitir_desde("sintesis")
        return res

    # 4. Síntesis
    res.python, res.mapa_py = codegen.generar_python(res.ast, res.tabla)
    res.javascript, res.mapa_js = codegen.generar_js(res.ast, res.tabla)
    f = fases["sintesis"]
    f.estado = "ok"
    f.resumen = (
        f"Python: {res.python.count(chr(10))} líneas · "
        f"JavaScript: {res.javascript.count(chr(10))} líneas"
    )
    return res
