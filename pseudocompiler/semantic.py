"""Fase 3: Análisis semántico.

Verifica el significado del programa sobre el AST:

* Toda variable debe leerse (`Leer`) o asignarse antes de usarse, considerando
  los caminos del programa: una variable asignada solo en una rama de un `Si`
  o dentro de un `Para`/`Mientras` puede quedar sin valor. La variable de control
  de un `Para` solo tiene valor dentro del ciclo.
* Los arreglos deben declararse con `Dimension` antes de usarse y usarse siempre
  con índice; el índice debe ser numérico y, si es constante, estar en rango.
* Las funciones deben declararse antes de llamarse y recibir el número correcto
  de argumentos; deben retornar la variable que declaran como retorno. Dentro de
  una función solo son visibles sus parámetros, sus variables locales y las
  funciones (no las variables globales).
* Comprueba los tipos (`Número`, `Texto`): no se mezclan en aritmética ni en
  comparaciones, y una variable conserva su tipo.
* Detecta divisiones entre cero cuando el divisor es constante (incluye
  propagación de constantes simples).
* Avisa de condiciones siempre verdaderas o falsas, de símbolos sin uso y de la
  reasignación de la variable de control de un `Para`.
* Detecta identificadores que chocan con palabras reservadas de Python o
  JavaScript y les asigna un nombre seguro en el código generado.

Además construye la tabla de símbolos, con el ámbito, la categoría y el tipo de
cada identificador.
"""

import keyword
from dataclasses import dataclass, field

from . import ast_nodes as ast
from .errors import SEMANTICO, ErrorManager
from .lexer import PALABRAS_RESERVADAS

# Nombres que no pueden usarse tal cual en el código de salida
RESERVADAS_PY = set(keyword.kwlist) | {
    "print", "input", "float", "int", "str", "formatear", "isinstance", "len",
    "max", "min", "sum", "list", "range",
}
RESERVADAS_JS = {
    "break", "case", "catch", "class", "const", "continue", "debugger", "default",
    "delete", "do", "else", "enum", "export", "extends", "false", "finally", "for",
    "function", "if", "import", "in", "instanceof", "new", "null", "return", "super",
    "switch", "this", "throw", "true", "try", "typeof", "var", "void", "while", "with",
    "yield", "let", "static", "implements", "interface", "package", "private",
    "protected", "public", "await", "async", "arguments", "eval",
    # nombres usados por el código generado
    "console", "readline", "require", "main", "rl", "lineas", "leer", "dividir", "Number",
    "String", "Array", "Math", "Symbol", "Error", "process", "undefined", "NaN", "Infinity",
}
_RESERVADAS_MINUS = {k.lower(): k for k in PALABRAS_RESERVADAS}

GLOBAL = "Global"

# Categorías
VARIABLE = "Variable"
PARAMETRO = "Parámetro"
RETORNO = "Retorno"
FUNCION = "Función"

# Tipos. SIN_TIPO es compatible con todos: su valor solo se conoce al ejecutar
# (por ejemplo, un parámetro que la función recibe sin operar con él).
NUMERO = "Número"
TEXTO = "Texto"
ARREGLO = "Arreglo"
SIN_TIPO = "Sin determinar"


@dataclass
class Simbolo:
    nombre: str
    linea_definicion: int
    definido_por: str               # "Leer", "Asignación", "Dimension", "Para", ...
    categoria: str = VARIABLE
    tipo: str = SIN_TIPO
    ambito: str = GLOBAL
    asignaciones: int = 0
    asignaciones_para: int = 0      # cuántas son como variable de control de un Para
    en_bloque: bool = False         # primera definición dentro de un bloque
    usos: list = field(default_factory=list)
    nombre_py: str = ""
    nombre_js: str = ""
    # Solo arreglos
    tipo_elemento: str = SIN_TIPO
    tamano: float | None = None     # tamaño, si es constante
    # Solo funciones
    parametros: list = field(default_factory=list)
    tipo_retorno: str = SIN_TIPO
    declarada: bool = False         # el análisis de flujo ya pasó por su declaración

    @property
    def solo_control(self) -> bool:
        """Solo recibe valor como variable de control de un `Para`."""
        return (self.categoria == VARIABLE and self.asignaciones_para > 0
                and self.asignaciones == self.asignaciones_para)

    @property
    def declaracion_js(self) -> str:
        """`const` si se asigna una sola vez fuera de bloques; `let` declarado al
        inicio de su ámbito si no; vacío si el símbolo no necesita declaración."""
        if self.categoria in (PARAMETRO, FUNCION) or self.solo_control:
            return ""
        return "const" if self.asignaciones == 1 and not self.en_bloque else "let"


class TablaSimbolos:
    def __init__(self):
        self.simbolos: dict[tuple[str, str], Simbolo] = {}

    def buscar(self, nombre, ambito=GLOBAL) -> Simbolo | None:
        """Busca en el ámbito dado. Las funciones son visibles desde cualquier
        ámbito; las variables globales no son visibles dentro de una función."""
        s = self.simbolos.get((ambito, nombre))
        if s is not None:
            return s
        g = self.simbolos.get((GLOBAL, nombre))
        return g if g is not None and g.categoria == FUNCION else None

    def agregar(self, s: Simbolo):
        self.simbolos[(s.ambito, s.nombre)] = s

    def de_ambito(self, ambito) -> list[Simbolo]:
        return [s for s in self if s.ambito == ambito]

    def __iter__(self):
        return iter(self.simbolos.values())

    def __len__(self):
        return len(self.simbolos)


DESCONOCIDO = object()


class AnalizadorSemantico:
    def __init__(self, errores: ErrorManager):
        self.errores = errores
        self.tabla = TablaSimbolos()
        self.ambito = GLOBAL

    def _error(self, msg, linea, col=0):
        self.errores.error(SEMANTICO, msg, linea, col)

    def _aviso(self, msg, linea, col=0):
        self.errores.advertencia(SEMANTICO, msg, linea, col)

    def _buscar(self, nombre) -> Simbolo | None:
        return self.tabla.buscar(nombre, self.ambito)

    # -- punto de entrada -------------------------------------------------
    def analizar(self, prog: ast.Programa) -> TablaSimbolos:
        self._registrar(prog.instrucciones, profundidad=0)
        self._verificar_choques()
        self._resolver_nombres()
        self._flujo(prog.instrucciones, set(), {})
        self._avisar_sin_uso()
        return self.tabla

    def _avisar_sin_uso(self):
        for s in self.tabla:
            if s.usos or s.solo_control:
                continue
            if s.categoria == FUNCION:
                self._aviso(f"la función '{s.nombre}' se declara pero nunca se llama", s.linea_definicion)
            elif s.categoria == PARAMETRO:
                self._aviso(f"el parámetro '{s.nombre}' de '{s.ambito}' nunca se usa", s.linea_definicion)
            else:
                accion = {"Leer": "se lee", "Dimension": "se declara"}.get(s.definido_por, "se asigna")
                self._aviso(f"la variable '{s.nombre}' {accion} pero nunca se usa", s.linea_definicion)

    # -- 1) registro de símbolos ------------------------------------------
    def _registrar(self, instrucciones, profundidad):
        for ins in instrucciones:
            match ins:
                case ast.Leer(destino=ast.Variable() as v) | ast.Asignacion(destino=ast.Variable() as v):
                    definido_por = "Leer" if isinstance(ins, ast.Leer) else "Asignación"
                    self._definir(v.nombre, ins.linea, v.columna, definido_por, profundidad)
                case ast.Dimension():
                    self._definir(ins.nombre, ins.linea, ins.columna, "Dimension", profundidad)
                case ast.Si():
                    self._registrar(ins.entonces, profundidad + 1)
                    self._registrar(ins.sino or [], profundidad + 1)
                case ast.Para(variable=v):
                    s = self._definir(v.nombre, ins.linea, v.columna, "Para", profundidad)
                    if s is not None:
                        s.asignaciones_para += 1
                    self._registrar(ins.cuerpo, profundidad + 1)
                case ast.Mientras():
                    self._registrar(ins.cuerpo, profundidad + 1)
                case ast.Funcion():
                    self._registrar_funcion(ins)

    def _definir(self, nombre, linea, col, definido_por, profundidad) -> Simbolo | None:
        s = self.tabla.simbolos.get((self.ambito, nombre))
        if s is None:
            s = Simbolo(nombre, linea, definido_por, ambito=self.ambito, en_bloque=profundidad > 0)
            self.tabla.agregar(s)
            sugerida = _RESERVADAS_MINUS.get(nombre.lower())
            if sugerida:
                self._aviso(f"la variable '{nombre}' se parece a la palabra reservada '{sugerida}'", linea, col)
        elif s.categoria == FUNCION:
            self._error(f"'{nombre}' es una función (línea {s.linea_definicion}) y no puede recibir un valor", linea, col)
            return None
        s.asignaciones += 1
        return s

    def _registrar_funcion(self, fn: ast.Funcion):
        previo = self.tabla.simbolos.get((GLOBAL, fn.nombre))
        if previo is not None:
            que = "función" if previo.categoria == FUNCION else "variable"
            self._error(
                f"'{fn.nombre}' ya está declarado como {que} en la línea {previo.linea_definicion}",
                fn.linea, fn.columna,
            )
            return
        self.tabla.agregar(Simbolo(
            fn.nombre, fn.linea, "Funcion", categoria=FUNCION, tipo=FUNCION,
            parametros=[p.nombre for p in fn.parametros],
        ))
        self.ambito = fn.nombre
        for p in fn.parametros:
            if (fn.nombre, p.nombre) in self.tabla.simbolos:
                self._error(f"el parámetro '{p.nombre}' está repetido en '{fn.nombre}'", p.linea, p.columna)
                continue
            self.tabla.agregar(Simbolo(p.nombre, p.linea, "Parámetro", categoria=PARAMETRO, ambito=fn.nombre))
        ret = self.tabla.simbolos.get((fn.nombre, fn.retorno.nombre))
        if ret is not None:
            self._error(
                f"la variable de retorno '{ret.nombre}' no puede ser también parámetro de '{fn.nombre}'",
                fn.retorno.linea, fn.retorno.columna,
            )
        else:
            self.tabla.agregar(Simbolo(
                fn.retorno.nombre, fn.retorno.linea, "Retorno", categoria=RETORNO, ambito=fn.nombre,
            ))
        self._registrar(fn.cuerpo, profundidad=0)
        self.ambito = GLOBAL

    def _verificar_choques(self):
        """Dentro de una función, un símbolo local no puede llamarse como una función."""
        for s in self.tabla:
            if s.ambito == GLOBAL:
                continue
            f = self.tabla.simbolos.get((GLOBAL, s.nombre))
            if f is not None and f.categoria == FUNCION:
                self._error(
                    f"'{s.nombre}' en '{s.ambito}' tiene el mismo nombre que la función "
                    f"de la línea {f.linea_definicion}", s.linea_definicion,
                )

    def _resolver_nombres(self):
        usados = {s.nombre for s in self.tabla}
        self._renombrar("nombre_py", RESERVADAS_PY, "Python", set(usados))
        self._renombrar("nombre_js", RESERVADAS_JS, "JavaScript", set(usados))

    def _renombrar(self, atributo, reservadas, lenguaje, usados):
        nuevos = {}
        for s in self.tabla:
            if s.nombre not in reservadas:
                setattr(s, atributo, s.nombre)
                continue
            if s.nombre not in nuevos:
                nuevo = s.nombre + "_"
                while nuevo in usados or nuevo in reservadas:
                    nuevo += "_"
                usados.add(nuevo)
                nuevos[s.nombre] = nuevo
            setattr(s, atributo, nuevos[s.nombre])
            self._aviso(
                f"'{s.nombre}' es un nombre reservado en {lenguaje}; en el código generado "
                f"se renombra a '{nuevos[s.nombre]}'", s.linea_definicion,
            )

    # -- 2) análisis de flujo ---------------------------------------------
    def _flujo(self, instrucciones, definidas: set, constantes: dict) -> set:
        """Recorre las instrucciones. `definidas` contiene las variables que con
        seguridad tienen valor; `constantes` los valores conocidos en compilación."""
        for ins in instrucciones:
            match ins:
                case ast.Leer(destino=d):
                    self._leer(d, definidas, constantes)
                case ast.Asignacion(destino=d, expr=e):
                    self._asignacion(d, e, definidas, constantes)
                case ast.Escribir(elementos=elems):
                    for el in elems:
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
                case ast.Para():
                    self._para(ins, definidas, constantes)
                case ast.Mientras():
                    # El cuerpo puede repetirse: lo que asigna deja de ser constante
                    # y, como puede no ejecutarse, no garantiza ninguna definición.
                    self._olvidar(ast.asignadas(ins.cuerpo), constantes)
                    self._condicion(ins.condicion, definidas, constantes)
                    self._flujo(ins.cuerpo, set(definidas), dict(constantes))
                case ast.Dimension():
                    self._dimension(ins, definidas, constantes)
                case ast.Funcion():
                    self._funcion(ins)
                case ast.Retornar():
                    self._retornar(ins, definidas)
        return definidas

    @staticmethod
    def _olvidar(nombres, constantes):
        for n in nombres:
            constantes.pop(n, None)

    def _leer(self, d, definidas, constantes):
        if isinstance(d, ast.Indice):
            self._elemento_destino(d, NUMERO, definidas, constantes)
            return
        s = self._buscar(d.nombre)
        if s is None or s.categoria == FUNCION:
            return
        if s.tipo == ARREGLO:
            self._error(f"'{d.nombre}' es un arreglo: use 'Leer {d.nombre}[índice]'", d.linea, d.columna)
            return
        self._fijar_tipo(s, NUMERO, d)
        definidas.add(d.nombre)
        constantes.pop(d.nombre, None)

    def _asignacion(self, d, e, definidas, constantes):
        valor = self._expr(e, definidas, constantes)
        tipo = self._tipo(e)
        if isinstance(d, ast.Indice):
            self._elemento_destino(d, tipo, definidas, constantes)
            return
        s = self._buscar(d.nombre)
        if s is None or s.categoria == FUNCION:
            return
        if s.tipo == ARREGLO:
            self._error(f"'{d.nombre}' es un arreglo: asigne a sus elementos con un índice", d.linea, d.columna)
            return
        self._fijar_tipo(s, tipo, d)
        definidas.add(d.nombre)
        if valor is DESCONOCIDO:
            constantes.pop(d.nombre, None)
        else:
            constantes[d.nombre] = valor

    def _fijar_tipo(self, s: Simbolo, tipo, nodo):
        if tipo == SIN_TIPO:
            return
        if s.tipo == SIN_TIPO:
            s.tipo = tipo
        elif s.tipo != tipo:
            self._error(
                f"la variable '{s.nombre}' es de tipo {s.tipo} y no puede recibir un valor de tipo {tipo}",
                nodo.linea, getattr(nodo, "columna", 0),
            )

    def _para(self, ins: ast.Para, definidas, constantes):
        v = ins.variable
        self._exigir_numero(ins.inicio, "el valor inicial de 'Para'", definidas, constantes)
        self._exigir_numero(ins.fin, "el límite de 'Para'", definidas, constantes)
        s = self._buscar(v.nombre)
        if s is None or s.categoria == FUNCION:
            return
        if s.tipo == ARREGLO:
            self._error(f"el arreglo '{v.nombre}' no puede ser la variable de control de 'Para'", v.linea, v.columna)
            return
        self._fijar_tipo(s, NUMERO, v)
        asignadas_cuerpo = ast.asignadas(ins.cuerpo)
        if v.nombre in asignadas_cuerpo:
            self._aviso(
                f"la variable de control '{v.nombre}' se modifica dentro del 'Para'; "
                "el resultado puede diferir entre Python y JavaScript", v.linea, v.columna,
            )
        self._olvidar(asignadas_cuerpo | {v.nombre}, constantes)
        self._flujo(ins.cuerpo, set(definidas) | {v.nombre}, dict(constantes))
        definidas.discard(v.nombre)

    def _dimension(self, ins: ast.Dimension, definidas, constantes):
        tamano = self._exigir_numero(ins.tamano, f"el tamaño del arreglo '{ins.nombre}'", definidas, constantes)
        s = self._buscar(ins.nombre)
        if s is None or s.categoria == FUNCION:
            return
        if ins.nombre in definidas:
            que = "ya está declarado" if s.tipo == ARREGLO else f"ya tiene un valor de tipo {s.tipo}"
            self._error(f"'{ins.nombre}' {que}: no puede usarse en 'Dimension'", ins.linea, ins.columna)
            return
        if s.tipo not in (SIN_TIPO, ARREGLO):
            self._error(f"'{ins.nombre}' es de tipo {s.tipo}: no puede usarse en 'Dimension'", ins.linea, ins.columna)
            return
        s.tipo = ARREGLO
        if tamano is not DESCONOCIDO:
            if tamano < 1:
                self._error(f"el tamaño del arreglo '{ins.nombre}' debe ser al menos 1", ins.linea, ins.columna)
            s.tamano = tamano
        definidas.add(ins.nombre)

    def _funcion(self, fn: ast.Funcion):
        f = self.tabla.simbolos.get((GLOBAL, fn.nombre))
        if f is None or f.linea_definicion != fn.linea:
            return  # declaración duplicada, ya reportada
        f.declarada = True  # visible en su propio cuerpo: se admite la recursión
        self.ambito = fn.nombre
        self._flujo(fn.cuerpo, {p.nombre for p in fn.parametros}, {})
        f.tipo_retorno = self.tabla.simbolos[(fn.nombre, fn.retorno.nombre)].tipo
        self.ambito = GLOBAL

    def _retornar(self, ins: ast.Retornar, definidas):
        v = ins.variable
        self._expr(v, definidas, {})
        retorno = next((s for s in self.tabla.de_ambito(self.ambito) if s.categoria == RETORNO), None)
        if retorno is not None and v.nombre != retorno.nombre:
            self._error(
                f"la función '{self.ambito}' declara '{retorno.nombre}' como variable de retorno, "
                f"pero retorna '{v.nombre}'", v.linea, v.columna,
            )

    # -- condiciones ------------------------------------------------------
    def _condicion(self, cond, definidas, constantes):
        match cond:
            case ast.Logica(izq=i, der=d):
                self._condicion(i, definidas, constantes)
                self._condicion(d, definidas, constantes)
            case ast.NoLogico(operando=x) | ast.Agrupacion(expr=x):
                self._condicion(x, definidas, constantes)
            case ast.Comparacion():
                self._comparacion(cond, definidas, constantes)

    def _comparacion(self, comp: ast.Comparacion, definidas, constantes):
        a = self._expr(comp.izq, definidas, constantes)
        b = self._expr(comp.der, definidas, constantes)
        ta, tb = self._tipo(comp.izq), self._tipo(comp.der)
        if SIN_TIPO not in (ta, tb) and ta != tb:
            self._error(f"no se puede comparar un valor de tipo {ta} con uno de tipo {tb}", comp.linea)
            return
        self._inferir(comp.izq, tb)
        self._inferir(comp.der, ta)
        if a is not DESCONOCIDO and b is not DESCONOCIDO:
            resultado = {
                ">=": a >= b, "<=": a <= b, ">": a > b,
                "<": a < b, "==": a == b, "!=": a != b,
            }[comp.op]
            self._aviso(
                f"la comparación ({_fmt(a)} {comp.op} {_fmt(b)}) siempre es "
                f"{'verdadera' if resultado else 'falsa'}", comp.linea,
            )

    # -- expresiones ------------------------------------------------------
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
                v = self._exigir_numero(x, "el operando de '-'", definidas, constantes)
                return DESCONOCIDO if v is DESCONOCIDO else -v
            case ast.Binaria(op=op, izq=i, der=d):
                a = self._exigir_numero(i, f"el operando de '{op}'", definidas, constantes)
                b = self._exigir_numero(d, f"el operando de '{op}'", definidas, constantes)
                if op == "/" and b is not DESCONOCIDO and b == 0:
                    self._error("división entre cero: el divisor siempre vale 0", e.linea)
                    return DESCONOCIDO
                if a is DESCONOCIDO or b is DESCONOCIDO:
                    return DESCONOCIDO
                return {"+": a + b, "-": a - b, "*": a * b, "/": a / b if b else 0}[op]
            case ast.Indice():
                self._arreglo(e, definidas, constantes)
            case ast.Llamada():
                self._llamada(e, definidas, constantes)
        return DESCONOCIDO

    def _exigir_numero(self, e, que, definidas, constantes):
        """Valida una expresión que debe ser numérica y devuelve su valor si es
        constante."""
        valor = self._expr(e, definidas, constantes)
        tipo = self._tipo(e)
        if tipo == TEXTO:
            self._error(f"{que} debe ser un número, no un texto", e.linea, getattr(e, "columna", 0))
        else:
            self._inferir(e, NUMERO)
        return valor

    def _inferir(self, e, tipo):
        """Una variable aún sin tipo adopta el tipo con el que se opera."""
        if isinstance(e, ast.Variable):
            s = self._buscar(e.nombre)
            if s is not None and s.tipo == SIN_TIPO:
                s.tipo = tipo

    def _tipo(self, e) -> str:
        match e:
            case ast.Numero() | ast.Negativo() | ast.Binaria():
                return NUMERO
            case ast.Cadena():
                return TEXTO
            case ast.Agrupacion(expr=x):
                return self._tipo(x)
            case ast.Variable(nombre=n):
                s = self._buscar(n)
                return s.tipo if s is not None and s.tipo in (NUMERO, TEXTO) else SIN_TIPO
            case ast.Indice(nombre=n):
                s = self._buscar(n)
                return s.tipo_elemento if s is not None else SIN_TIPO
            case ast.Llamada(nombre=n):
                s = self._buscar(n)
                return s.tipo_retorno if s is not None else SIN_TIPO
        return SIN_TIPO

    def _uso(self, v: ast.Variable, definidas):
        s = self._buscar(v.nombre)
        if s is None:
            if self.ambito != GLOBAL and self.tabla.simbolos.get((GLOBAL, v.nombre)) is not None:
                self._error(
                    f"la variable global '{v.nombre}' no es visible dentro de la función "
                    f"'{self.ambito}': pásela como parámetro", v.linea, v.columna,
                )
                return
            self._error(
                f"la variable '{v.nombre}' no está definida: debe leerse con 'Leer' "
                "o asignarse antes de usarse", v.linea, v.columna,
            )
            return
        if s.categoria == FUNCION:
            self._error(f"'{v.nombre}' es una función: debe llamarse con paréntesis", v.linea, v.columna)
            return
        s.usos.append(v.linea)
        if s.tipo == ARREGLO and v.nombre in definidas:
            self._error(f"el arreglo '{v.nombre}' debe usarse con un índice: {v.nombre}[i]", v.linea, v.columna)
            return
        self._verificar_definida(s, v, definidas)

    def _verificar_definida(self, s: Simbolo, nodo, definidas):
        if s.nombre in definidas:
            return
        columna = nodo.columna
        if s.linea_definicion > nodo.linea or (s.linea_definicion == nodo.linea and not s.en_bloque):
            self._error(
                f"la variable '{s.nombre}' se usa antes de tener un valor "
                f"(se define en la línea {s.linea_definicion})", nodo.linea, columna,
            )
        elif s.asignaciones_para:
            self._error(
                f"la variable '{s.nombre}' no tiene valor aquí: una variable de control de 'Para' "
                f"solo tiene valor dentro del ciclo (línea {s.linea_definicion})", nodo.linea, columna,
            )
        else:
            self._error(
                f"la variable '{s.nombre}' podría no tener valor: solo se asigna dentro de un "
                f"bloque que podría no ejecutarse (línea {s.linea_definicion})", nodo.linea, columna,
            )

    # -- arreglos ---------------------------------------------------------
    def _arreglo(self, e: ast.Indice, definidas, constantes) -> Simbolo | None:
        """Valida el acceso `e` y devuelve el símbolo del arreglo, si es válido."""
        indice = self._exigir_numero(e.indice, f"el índice de '{e.nombre}'", definidas, constantes)
        s = self._buscar(e.nombre)
        if s is None:
            self._error(
                f"el arreglo '{e.nombre}' no está declarado: use 'Dimension {e.nombre}[tamaño]' antes de usarlo",
                e.linea, e.columna,
            )
            return None
        s.usos.append(e.linea)
        if s.tipo != ARREGLO and s.definido_por != "Dimension":
            que = "una función" if s.categoria == FUNCION else f"de tipo {s.tipo}"
            self._error(f"'{e.nombre}' no es un arreglo ({que}): no se le puede aplicar un índice", e.linea, e.columna)
            return None
        if e.nombre not in definidas:
            if s.linea_definicion >= e.linea:
                self._error(
                    f"el arreglo '{e.nombre}' se usa antes de su 'Dimension' (línea {s.linea_definicion})",
                    e.linea, e.columna,
                )
            else:
                self._verificar_definida(s, e, definidas)
            return None
        if indice is not DESCONOCIDO:
            if indice < 1:
                self._error(f"el índice {_fmt(indice)} de '{e.nombre}' no es válido: los arreglos comienzan en 1", e.linea, e.columna)
            elif s.tamano is not None and indice > s.tamano:
                self._error(
                    f"el índice {_fmt(indice)} está fuera del arreglo '{e.nombre}' de tamaño {_fmt(s.tamano)}",
                    e.linea, e.columna,
                )
        return s

    def _elemento_destino(self, d: ast.Indice, tipo, definidas, constantes):
        s = self._arreglo(d, definidas, constantes)
        if s is None or tipo == SIN_TIPO:
            return
        if s.tipo_elemento == SIN_TIPO:
            s.tipo_elemento = tipo
        elif s.tipo_elemento != tipo:
            self._error(
                f"el arreglo '{d.nombre}' guarda valores de tipo {s.tipo_elemento} "
                f"y no puede recibir un valor de tipo {tipo}", d.linea, d.columna,
            )

    # -- funciones --------------------------------------------------------
    def _llamada(self, e: ast.Llamada, definidas, constantes):
        for arg in e.argumentos:
            self._expr(arg, definidas, constantes)
        f = self._buscar(e.nombre)
        if f is None:
            self._error(f"la función '{e.nombre}' no está declarada", e.linea, e.columna)
            return
        if f.categoria != FUNCION:
            self._error(f"'{e.nombre}' no es una función: no se puede llamar", e.linea, e.columna)
            return
        f.usos.append(e.linea)
        if not f.declarada:
            self._error(
                f"la función '{e.nombre}' se llama antes de declararse (línea {f.linea_definicion})",
                e.linea, e.columna,
            )
            return
        if len(e.argumentos) != len(f.parametros):
            self._error(
                f"la función '{e.nombre}' espera {len(f.parametros)} argumento(s), "
                f"pero recibe {len(e.argumentos)}", e.linea, e.columna,
            )
            return
        for i, (arg, nombre) in enumerate(zip(e.argumentos, f.parametros), 1):
            p = self.tabla.simbolos[(e.nombre, nombre)]
            tipo = self._tipo(arg)
            if SIN_TIPO in (tipo, p.tipo):
                p.tipo = tipo if p.tipo == SIN_TIPO else p.tipo
            elif tipo != p.tipo:
                self._error(
                    f"el argumento {i} de '{e.nombre}' debe ser de tipo {p.tipo}, no {tipo}",
                    e.linea, e.columna,
                )


def _fmt(x: float) -> str:
    return str(int(x)) if x == int(x) else str(x)


def analizar(prog: ast.Programa, errores: ErrorManager) -> TablaSimbolos:
    return AnalizadorSemantico(errores).analizar(prog)
