"""Gestor de errores del compilador.

Cada fase (léxica, sintáctica, semántica) registra aquí sus errores y
advertencias, siempre con la línea y columna donde se detectaron.
"""

from dataclasses import dataclass, field

LEXICO = "LÉXICO"
SINTACTICO = "SINTÁCTICO"
SEMANTICO = "SEMÁNTICO"


@dataclass
class CompilerError:
    fase: str
    mensaje: str
    linea: int
    columna: int = 0
    es_advertencia: bool = False

    def __str__(self) -> str:
        fase = self.fase.lower()
        tipo = "Error"
        if self.es_advertencia:
            tipo, fase = "Advertencia", fase[:-1] + "a"
        return f"{tipo} {fase} en {self.posicion}: {self.mensaje}"

    @property
    def posicion(self) -> str:
        pos = f"línea {self.linea}"
        if self.columna:
            pos += f", columna {self.columna}"
        return pos


@dataclass
class ErrorManager:
    errores: list = field(default_factory=list)
    advertencias: list = field(default_factory=list)

    def error(self, fase, mensaje, linea, columna=0):
        self.errores.append(CompilerError(fase, mensaje, linea, columna))

    def advertencia(self, fase, mensaje, linea, columna=0):
        self.advertencias.append(CompilerError(fase, mensaje, linea, columna, True))

    def errores_de(self, fase):
        return [e for e in self.errores if e.fase == fase]

    def advertencias_de(self, fase):
        return [e for e in self.advertencias if e.fase == fase]

    @property
    def hay_errores(self) -> bool:
        return bool(self.errores)
