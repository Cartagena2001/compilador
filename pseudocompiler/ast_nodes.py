"""Nodos del árbol sintáctico abstracto (AST)."""

from dataclasses import dataclass, field


@dataclass
class Nodo:
    linea: int


# -- Expresiones ----------------------------------------------------------
@dataclass
class Numero(Nodo):
    valor: str


@dataclass
class Variable(Nodo):
    nombre: str
    columna: int = 0


@dataclass
class Cadena(Nodo):
    texto: str


@dataclass
class Negativo(Nodo):
    operando: Nodo


@dataclass
class Binaria(Nodo):
    op: str
    izq: Nodo
    der: Nodo


@dataclass
class Agrupacion(Nodo):
    """Expresión entre paréntesis; se conserva para respetar el código original."""
    expr: Nodo


@dataclass
class Comparacion(Nodo):
    op: str
    izq: Nodo
    der: Nodo


@dataclass
class Condicion(Nodo):
    """Una o más comparaciones unidas con el operador lógico Y."""
    comparaciones: list


# -- Instrucciones --------------------------------------------------------
@dataclass
class Leer(Nodo):
    variable: Variable


@dataclass
class Escribir(Nodo):
    elementos: list


@dataclass
class Asignacion(Nodo):
    variable: Variable
    expr: Nodo


@dataclass
class Si(Nodo):
    condicion: Condicion
    entonces: list
    sino: list | None = None


@dataclass
class Programa(Nodo):
    instrucciones: list = field(default_factory=list)


def arbol_texto(nodo, prefijo="", ultimo=True, raiz=True) -> list[str]:
    """Representa el AST como un árbol de texto (para mostrarlo en la interfaz)."""
    lineas = []
    conector = "" if raiz else ("└── " if ultimo else "├── ")
    lineas.append(prefijo + conector + _etiqueta(nodo))
    hijos = _hijos(nodo)
    nuevo_prefijo = prefijo + ("" if raiz else ("    " if ultimo else "│   "))
    for i, hijo in enumerate(hijos):
        lineas.extend(arbol_texto(hijo, nuevo_prefijo, i == len(hijos) - 1, False))
    return lineas


class _Grupo:
    def __init__(self, nombre, hijos):
        self.nombre = nombre
        self.hijos = hijos


def _etiqueta(n) -> str:
    match n:
        case _Grupo():
            return n.nombre
        case Programa():
            return "Programa"
        case Leer():
            return f"Leer {n.variable.nombre}  (línea {n.linea})"
        case Escribir():
            return f"Escribir  (línea {n.linea})"
        case Asignacion():
            return f"Asignación {n.variable.nombre} =  (línea {n.linea})"
        case Si():
            return f"Si{'-Sino' if n.sino is not None else ''}  (línea {n.linea})"
        case Condicion():
            return "Y" if len(n.comparaciones) > 1 else "Condición"
        case Comparacion():
            return f"( {n.op} )"
        case Binaria():
            return f"[ {n.op} ]"
        case Agrupacion():
            return "( )"
        case Negativo():
            return "[ - unario ]"
        case Numero():
            return n.valor
        case Variable():
            return n.nombre
        case Cadena():
            return f'"{n.texto}"'
    return type(n).__name__


def _hijos(n) -> list:
    match n:
        case _Grupo():
            return n.hijos
        case Programa():
            return n.instrucciones
        case Leer():
            return []
        case Escribir():
            return n.elementos
        case Asignacion():
            return [n.expr]
        case Si():
            hijos = [_Grupo("condición", [n.condicion]), _Grupo("Entonces", n.entonces)]
            if n.sino is not None:
                hijos.append(_Grupo("Sino", n.sino))
            return hijos
        case Condicion():
            return n.comparaciones
        case Comparacion() | Binaria():
            return [n.izq, n.der]
        case Agrupacion():
            return [n.expr]
        case Negativo():
            return [n.operando]
    return []
