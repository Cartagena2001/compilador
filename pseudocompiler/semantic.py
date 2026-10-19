"""Fase 3: Análisis semántico.

Verifica el significado del programa sobre el AST:

* Toda variable debe leerse (`Leer`) o asignarse antes de usarse, considerando
  los caminos de los bloques `Si`/`Sino` (una variable asignada solo en una
  rama puede quedar sin valor).
* Detecta divisiones entre cero cuando el divisor es constante (incluye
  propagación de constantes simples).
* Avisa de condiciones siempre verdaderas o falsas y de variables sin uso.
* Detecta identificadores que chocan con palabras reservadas de Python o
  JavaScript y les asigna un nombre seguro en el código generado.

Además construye la tabla de símbolos.
"""

import keyword
from dataclasses import dataclass, field

from . import ast_nodes as ast
from .errors import SEMANTICO, ErrorManager
from .lexer import PALABRAS_RESERVADAS

# Nombres que no pueden usarse tal cual en el código de salida
RESERVADAS_PY = set(keyword.kwlist) | {
    "print", "input", "float", "int", "str", "formatear", "isinstance", "len",
}
RESERVADAS_JS = {
    "break", "case", "catch", "class", "const", "continue", "debugger", "default",
    "delete", "do", "else", "enum", "export", "extends", "false", "finally", "for",
    "function", "if", "import", "in", "instanceof", "new", "null", "return", "super",
    "switch", "this", "throw", "true", "try", "typeof", "var", "void", "while", "with",
    "yield", "let", "static", "implements", "interface", "package", "private",
    "protected", "public", "await", "async", "arguments", "eval",
    # nombres usados por el código generado
    "console", "readline", "require", "main", "rl", "lineas", "leer", "Number",
    "String", "process", "undefined", "NaN", "Infinity",
}
_RESERVADAS_MINUS = {k.lower(): k for k in PALABRAS_RESERVADAS}


@dataclass
class Simbolo:
    nombre: str
    linea_definicion: int
    definido_por: str               # "Leer" o "Asignación"
    categoria: str = "Variable"
    tipo: str = "Real (float / number)"
    ambito: str = "Global"
    asignaciones: int = 0
    en_bloque: bool = False         # primera definición dentro de un Si
    usos: list = field(default_factory=list)
    nombre_py: str = ""
    nombre_js: str = ""

    @property
    def declaracion_js(self) -> str:
        """`const` si se asigna una sola vez fuera de bloques; si no, `let`
        declarado al inicio de main() para que sea visible en todo el programa."""
        return "const" if self.asignaciones == 1 and not self.en_bloque else "let"


class TablaSimbolos:
    def __init__(self):
        self.simbolos: dict[str, Simbolo] = {}

    def __contains__(self, nombre):
        return nombre in self.simbolos

    def __getitem__(self, nombre) -> Simbolo:
        return self.simbolos[nombre]

    def __iter__(self):
        return iter(self.simbolos.values())

    def __len__(self):
        return len(self.simbolos)


DESCONOCIDO = object()


class AnalizadorSemantico:
    def __init__(self, errores: ErrorManager):
        self.errores = errores
        self.tabla = TablaSimbolos()

    def _error(self, msg, linea, col=0):
        self.errores.error(SEMANTICO, msg, linea, col)

    def _aviso(self, msg, linea, col=0):
        self.errores.advertencia(SEMANTICO, msg, linea, col)

    # -- punto de entrada -------------------------------------------------
    def analizar(self, prog: ast.Programa) -> TablaSimbolos:
        self._registrar(prog.instrucciones, profundidad=0)
        self._resolver_nombres()
        self._flujo(prog.instrucciones, set(), {})
        for s in self.tabla:
            if not s.usos:
                accion = "se lee" if s.definido_por == "Leer" else "se asigna"
                self._aviso(f"la variable '{s.nombre}' {accion} pero nunca se usa", s.linea_definicion)
        return self.tabla

    # -- 1) registro de símbolos ------------------------------------------
    def _registrar(self, instrucciones, profundidad):
        for ins in instrucciones:
            match ins:
                case ast.Leer(variable=v) | ast.Asignacion(variable=v):
                    if v.nombre not in self.tabla:
                        self.tabla.simbolos[v.nombre] = Simbolo(
                            v.nombre, ins.linea,
                            "Leer" if isinstance(ins, ast.Leer) else "Asignación",
                            en_bloque=profundidad > 0,
                        )
                        sugerida = _RESERVADAS_MINUS.get(v.nombre.lower())
                        if sugerida:
                            self._aviso(
                                f"la variable '{v.nombre}' se parece a la palabra reservada "
                                f"'{sugerida}'", ins.linea, v.columna,
                            )
                    self.tabla[v.nombre].asignaciones += 1
                case ast.Si():
                    self._registrar(ins.entonces, profundidad + 1)
                    if ins.sino:
                        self._registrar(ins.sino, profundidad + 1)

    def _resolver_nombres(self):
        usados_py = set(self.tabla.simbolos)
        usados_js = set(self.tabla.simbolos)
        for s in self.tabla:
            s.nombre_py = self._renombrar(s, RESERVADAS_PY, "Python", usados_py)
            s.nombre_js = self._renombrar(s, RESERVADAS_JS, "JavaScript", usados_js)

    def _renombrar(self, s, reservadas, lenguaje, usados):
        if s.nombre not in reservadas:
            return s.nombre
        nuevo = s.nombre + "_"
        while nuevo in usados or nuevo in reservadas:
            nuevo += "_"
        usados.add(nuevo)
        self._aviso(
            f"'{s.nombre}' es un nombre reservado en {lenguaje}; en el código generado "
            f"se renombra a '{nuevo}'", s.linea_definicion,
        )
        return nuevo

    # -- 2) análisis de flujo ---------------------------------------------
    def _flujo(self, instrucciones, definidas: set, constantes: dict) -> set:
        """Recorre las instrucciones. `definidas` contiene las variables que con
        seguridad tienen valor; `constantes` los valores conocidos en compilación."""
        for ins in instrucciones:
            match ins:
                case ast.Leer(variable=v):
                    definidas.add(v.nombre)
                    constantes.pop(v.nombre, None)
                case ast.Asignacion(variable=v, expr=e):
                    valor = self._expr(e, definidas, constantes)
                    definidas.add(v.nombre)
                    if valor is DESCONOCIDO:
                        constantes.pop(v.nombre, None)
                    else:
                        constantes[v.nombre] = valor
                case ast.Escribir(elementos=elems):
                    for el in elems:
                        if not isinstance(el, ast.Cadena):
                            self._expr(el, definidas, constantes)
                case ast.Si():
                    self._condicion(ins.condicion, definidas, constantes)
                    c1, c2 = dict(constantes), dict(constantes)
                    d1 = self._flujo(ins.entonces, set(definidas), c1)
                    d2 = self._flujo(ins.sino or [], set(definidas), c2)
                    # tras el Si, solo quedan definidas las que se asignan en ambas ramas
                    definidas |= d1 & d2
                    # solo se conservan las constantes iguales en ambas ramas
                    for k in list(constantes):
                        del constantes[k]
                    for k, val in c1.items():
                        if k in c2 and c2[k] == val:
                            constantes[k] = val
        return definidas

    def _condicion(self, cond: ast.Condicion, definidas, constantes):
        for comp in cond.comparaciones:
            a = self._expr(comp.izq, definidas, constantes)
            b = self._expr(comp.der, definidas, constantes)
            if a is not DESCONOCIDO and b is not DESCONOCIDO:
                resultado = {
                    ">=": a >= b, "<=": a <= b, ">": a > b,
                    "<": a < b, "==": a == b, "!=": a != b,
                }[comp.op]
                self._aviso(
                    f"la comparación ({_fmt(a)} {comp.op} {_fmt(b)}) siempre es "
                    f"{'verdadera' if resultado else 'falsa'}", comp.linea,
                )

    def _expr(self, e, definidas, constantes):
        """Valida una expresión y devuelve su valor si es constante."""
        match e:
            case ast.Numero(valor=v):
                return float(v)
            case ast.Variable(nombre=n):
                self._uso(e, definidas)
                return constantes.get(n, DESCONOCIDO)
            case ast.Agrupacion(expr=x):
                return self._expr(x, definidas, constantes)
            case ast.Negativo(operando=x):
                v = self._expr(x, definidas, constantes)
                return DESCONOCIDO if v is DESCONOCIDO else -v
            case ast.Binaria(op=op, izq=i, der=d):
                a = self._expr(i, definidas, constantes)
                b = self._expr(d, definidas, constantes)
                if op == "/" and b is not DESCONOCIDO and b == 0:
                    self._error("división entre cero: el divisor siempre vale 0", e.linea)
                    return DESCONOCIDO
                if a is DESCONOCIDO or b is DESCONOCIDO:
                    return DESCONOCIDO
                return {"+": a + b, "-": a - b, "*": a * b, "/": a / b if b else 0}[op]
        return DESCONOCIDO

    def _uso(self, v: ast.Variable, definidas):
        if v.nombre not in self.tabla:
            self._error(
                f"la variable '{v.nombre}' no está definida: debe leerse con 'Leer' "
                "o asignarse antes de usarse", v.linea, v.columna,
            )
            return
        s = self.tabla[v.nombre]
        s.usos.append(v.linea)
        if v.nombre in definidas:
            return
        if s.linea_definicion > v.linea or (s.linea_definicion == v.linea and not s.en_bloque):
            self._error(
                f"la variable '{v.nombre}' se usa antes de tener un valor "
                f"(se define en la línea {s.linea_definicion})", v.linea, v.columna,
            )
        else:
            self._error(
                f"la variable '{v.nombre}' podría no tener valor: solo se asigna dentro de "
                f"algunas ramas de un 'Si' (línea {s.linea_definicion})", v.linea, v.columna,
            )


def _fmt(x: float) -> str:
    return str(int(x)) if x == int(x) else str(x)


def analizar(prog: ast.Programa, errores: ErrorManager) -> TablaSimbolos:
    return AnalizadorSemantico(errores).analizar(prog)
