"""Nodos del árbol sintáctico abstracto (AST)."""

from dataclasses import dataclass, field, fields


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
class Indice(Nodo):
    """Acceso a un elemento de un arreglo (base 1): `numeros[i]`."""
    nombre: str
    indice: Nodo
    columna: int = 0


@dataclass
class Llamada(Nodo):
    nombre: str
    argumentos: list
    columna: int = 0


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
class Logica(Nodo):
    """Condiciones unidas con `Y` u `O`."""
    op: str
    izq: Nodo
    der: Nodo


@dataclass
class NoLogico(Nodo):
    operando: Nodo


# -- Instrucciones --------------------------------------------------------
@dataclass
class Leer(Nodo):
    destino: Variable | Indice


@dataclass
class Escribir(Nodo):
    elementos: list


@dataclass
class Asignacion(Nodo):
    destino: Variable | Indice
    expr: Nodo


@dataclass
class Si(Nodo):
    condicion: Nodo
    entonces: list
    sino: list | None = None


@dataclass
class Para(Nodo):
    variable: Variable
    inicio: Nodo
    fin: Nodo
    cuerpo: list


@dataclass
class Mientras(Nodo):
    condicion: Nodo
    cuerpo: list


@dataclass
class Dimension(Nodo):
    nombre: str
    tamano: Nodo
    columna: int = 0


@dataclass
class Retornar(Nodo):
    variable: Variable


@dataclass
class Funcion(Nodo):
    """`Funcion retorno = nombre(parametros)`; su cuerpo termina con `Retornar`."""
    nombre: str
    retorno: Variable
    parametros: list
    cuerpo: list
    columna: int = 0


@dataclass
class Programa(Nodo):
    instrucciones: list = field(default_factory=list)


def recorrer(nodo):
    """Recorre en profundidad un nodo (o lista de nodos) y todos sus descendientes."""
    if isinstance(nodo, list):
        for elemento in nodo:
            yield from recorrer(elemento)
    elif isinstance(nodo, Nodo):
        yield nodo
        for campo in fields(nodo):
            yield from recorrer(getattr(nodo, campo.name))


def asignadas(instrucciones) -> set:
    """Nombres que reciben un valor dentro de las instrucciones dadas."""
    nombres = set()
    for n in recorrer(instrucciones):
        match n:
            case Leer(destino=d) | Asignacion(destino=d):
                nombres.add(d.nombre)
            case Para(variable=v):
                nombres.add(v.nombre)
            case Dimension(nombre=nombre):
                nombres.add(nombre)
    return nombres


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


def _destino(d) -> str:
    return f"{d.nombre}[ ]" if isinstance(d, Indice) else d.nombre


def _etiqueta(n) -> str:
    match n:
        case _Grupo():
            return n.nombre
        case Programa():
            return "Programa"
        case Leer():
            return f"Leer {_destino(n.destino)}  (línea {n.linea})"
        case Escribir():
            return f"Escribir  (línea {n.linea})"
        case Asignacion():
            return f"Asignación {_destino(n.destino)} =  (línea {n.linea})"
        case Si():
            return f"Si{'-Sino' if n.sino is not None else ''}  (línea {n.linea})"
        case Para():
            return f"Para {n.variable.nombre}  (línea {n.linea})"
        case Mientras():
            return f"Mientras  (línea {n.linea})"
        case Dimension():
            return f"Dimension {n.nombre}  (línea {n.linea})"
        case Funcion():
            params = ", ".join(p.nombre for p in n.parametros)
            return f"Función {n.retorno.nombre} = {n.nombre}({params})  (línea {n.linea})"
        case Retornar():
            return f"Retornar {n.variable.nombre}  (línea {n.linea})"
        case Logica():
            return n.op
        case NoLogico():
            return "NO"
        case Indice():
            return f"{n.nombre}[ ]"
        case Llamada():
            return f"Llamada {n.nombre}( )"
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
            return [n.destino.indice] if isinstance(n.destino, Indice) else []
        case Escribir():
            return n.elementos
        case Asignacion():
            return ([n.destino.indice] if isinstance(n.destino, Indice) else []) + [n.expr]
        case Si():
            hijos = [_Grupo("condición", [n.condicion]), _Grupo("Entonces", n.entonces)]
            if n.sino is not None:
                hijos.append(_Grupo("Sino", n.sino))
            return hijos
        case Comparacion() | Binaria() | Logica():
            return [n.izq, n.der]
        case NoLogico():
            return [n.operando]
        case Para():
            return [_Grupo("desde", [n.inicio]), _Grupo("hasta", [n.fin]), _Grupo("cuerpo", n.cuerpo)]
        case Mientras():
            return [_Grupo("condición", [n.condicion]), _Grupo("cuerpo", n.cuerpo)]
        case Dimension():
            return [_Grupo("tamaño", [n.tamano])]
        case Funcion():
            return n.cuerpo
        case Indice():
            return [n.indice]
        case Llamada():
            return n.argumentos
        case Agrupacion():
            return [n.expr]
        case Negativo():
            return [n.operando]
    return []
