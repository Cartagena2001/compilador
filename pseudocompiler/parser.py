"""Fase 2: Análisis sintáctico.

Parser descendente recursivo que sigue la gramática EBNF del lenguaje:

    programa     = "Inicio", { funcion | instruccion }, "Fin" ;
    funcion      = "Funcion", ID, "=", ID, "(", [ ID, { ",", ID } ], ")",
                   { instruccion }, "Retornar", ID, "FinFuncion" ;
    instruccion  = leer | escribir | asignacion | si | para | mientras | dimension ;
    leer         = "Leer", destino ;
    escribir     = "Escribir", expresion, { ",", expresion } ;
    dimension    = "Dimension", ID, "[", expresion, "]" ;
    asignacion   = destino, "=", expresion ;
    destino      = ID | ID, "[", expresion, "]" ;
    si           = "Si", condicion, "Entonces", { instruccion },
                   [ "Sino", { instruccion } ], "FinSi" ;
    para         = "Para", ID, "=", expresion, "Hasta", expresion, "Hacer",
                   { instruccion }, "FinPara" ;
    mientras     = "Mientras", condicion, "Hacer", { instruccion }, "FinMientras" ;
    condicion    = conj, { "O", conj } ;
    conj         = neg, { "Y", neg } ;
    neg          = [ "NO" ], comparacion ;
    comparacion  = expresion, OP_REL, expresion | "(", condicion, ")" ;
    expresion    = termino, { ("+" | "-"), termino } ;
    termino      = factor, { ("*" | "/"), factor } ;
    factor       = NUMERO | CADENA | llamada | ID | ID, "[", expresion, "]"
                 | "(", expresion, ")" | "-", factor ;
    llamada      = ID, "(", [ expresion, { ",", expresion } ], ")" ;

Precedencia (de mayor a menor): paréntesis, - unario, * /, + -, relacionales,
NO, Y, O.

Extensión: `-` unario en `factor` y comparaciones con o sin paréntesis
(`Si a > b Entonces` y `Si (a > b) Entonces`). Un "(" al inicio de una
comparación es ambiguo; se resuelve con retroceso (ver `comparacion`).

Ante un error, el parser lo registra con su línea y se re-sincroniza en la
siguiente instrucción (modo pánico) para poder reportar varios errores.
"""

from . import ast_nodes as ast
from .errors import SINTACTICO, ErrorManager
from .lexer import PALABRAS_RESERVADAS, Token

# Palabra que abre un bloque -> palabra que lo cierra
CIERRES = {"Si": "FinSi", "Para": "FinPara", "Mientras": "FinMientras", "Funcion": "FinFuncion"}
# Token de cierre -> palabra que abre su bloque
ABRE = {"SINO": "Si", "FINSI": "Si", "FINPARA": "Para", "FINMIENTRAS": "Mientras", "FINFUNCION": "Funcion"}
INICIO_INSTRUCCION = {
    "LEER", "ESCRIBIR", "SI", "PARA", "MIENTRAS", "DIMENSION", "FUNCION", "RETORNAR", "FIN", "EOF",
} | set(ABRE)
_RESERVADAS_MINUS = {k.lower(): k for k in PALABRAS_RESERVADAS}


class ParseError(Exception):
    pass


def _describir(tok: Token) -> str:
    if tok.tipo == "EOF":
        return "el fin del archivo"
    if tok.tipo == "CADENA":
        return f'la cadena "{tok.lexema}"'
    return f"'{tok.lexema}'"


class Parser:
    def __init__(self, tokens: list[Token], errores: ErrorManager):
        self.tokens = tokens
        self.errores = errores
        self.pos = 0
        self.abiertos: list[str] = []   # bloques abiertos, del más externo al más interno

    # -- utilidades -------------------------------------------------------
    @property
    def actual(self) -> Token:
        return self.tokens[self.pos]

    @property
    def anterior(self) -> Token | None:
        return self.tokens[self.pos - 1] if self.pos > 0 else None

    def _ver(self, k=1) -> Token:
        return self.tokens[min(self.pos + k, len(self.tokens) - 1)]

    def _avanzar(self) -> Token:
        tok = self.actual
        if tok.tipo != "EOF":
            self.pos += 1
        return tok

    def _es(self, *tipos) -> bool:
        return self.actual.tipo in tipos

    def _fallar(self, mensaje: str, tok: Token | None = None):
        self._registrar_falta(mensaje, tok)
        raise ParseError(mensaje)

    def _registrar_falta(self, mensaje: str, tok: Token | None = None):
        """Registra un error. Si lo esperado faltaba al final de una línea,
        se reporta en esa línea y no en la siguiente."""
        falta_algo = tok is None
        tok = tok or self.actual
        prev = self.anterior
        if falta_algo and prev is not None and tok.linea > prev.linea:
            linea, col = prev.linea, prev.columna + len(prev.lexema)
            mensaje += " (al final de la línea)"
        else:
            linea, col = tok.linea, tok.columna
        self.errores.error(SINTACTICO, mensaje, linea, col)

    def _esperar(self, tipo: str, que: str) -> Token:
        if self.actual.tipo == tipo:
            return self._avanzar()
        self._fallar(f"se esperaba {que}, pero se encontró {_describir(self.actual)}")

    def _sincronizar(self, linea_error: int):
        """Modo pánico: descarta tokens hasta el inicio de otra instrucción."""
        while not self._es("EOF"):
            tok = self.actual
            if tok.linea > linea_error and (
                tok.tipo in INICIO_INSTRUCCION
                or (tok.tipo == "ID" and self._ver().tipo in ("ASIGNACION", "CORCHETE_IZQ"))
            ):
                return
            if tok.tipo == "FIN" or tok.tipo in ABRE:
                return
            self._avanzar()

    # -- reglas -----------------------------------------------------------
    def programa(self) -> ast.Programa:
        prog = ast.Programa(linea=self.actual.linea)
        if self._es("INICIO"):
            self._avanzar()
        else:
            self.errores.error(
                SINTACTICO,
                f"el programa debe comenzar con 'Inicio', pero se encontró {_describir(self.actual)}",
                self.actual.linea, self.actual.columna,
            )

        prog.instrucciones = self._bloque(cierre=("FIN",), abierto_en=None)

        if self._es("FIN"):
            self._avanzar()
            if not self._es("EOF"):
                tok = self.actual
                self.errores.error(
                    SINTACTICO,
                    f"no puede haber instrucciones después de 'Fin' (se encontró {_describir(tok)})",
                    tok.linea, tok.columna,
                )
        else:
            ultimo = self.anterior or self.actual
            self.errores.error(
                SINTACTICO, "falta 'Fin' al final del programa", ultimo.linea, 0
            )
        return prog

    def _bloque(self, cierre: tuple, abierto_en: Token | None) -> list:
        instrucciones = []
        while True:
            if self._es(*cierre):
                return instrucciones
            if self._es("EOF") or (abierto_en is not None and self._es("FIN")):
                if abierto_en is not None:
                    self._sin_cerrar(abierto_en)
                return instrucciones
            if self.actual.tipo in ABRE:
                # Un cierre de un bloque externo significa que este quedó sin cerrar
                if ABRE[self.actual.tipo] in self.abiertos:
                    self._sin_cerrar(abierto_en)
                tok = self._avanzar()
                self.errores.error(
                    SINTACTICO,
                    f"'{tok.lexema}' sin un '{ABRE[tok.tipo]}' correspondiente",
                    tok.linea, tok.columna,
                )
                continue
            if abierto_en is None and self._es("INICIO"):
                tok = self._avanzar()
                self.errores.error(SINTACTICO, "'Inicio' repetido", tok.linea, tok.columna)
                continue

            inicio = self.pos
            try:
                instr = self.instruccion()
                if instr is not None:
                    instrucciones.append(instr)
            except ParseError:
                linea = self.tokens[inicio].linea
                if self.pos == inicio:
                    self._avanzar()
                self._sincronizar(linea)

    def _sin_cerrar(self, abierto_en: Token):
        self.errores.error(
            SINTACTICO,
            f"el bloque '{abierto_en.lexema}' abierto en la línea {abierto_en.linea} "
            f"no se cerró con '{CIERRES[abierto_en.lexema]}'",
            abierto_en.linea, abierto_en.columna,
        )
        raise ParseError(f"{abierto_en.lexema} sin cerrar")

    def _cuerpo(self, cierre: tuple, abierto_en: Token) -> list:
        """Analiza las instrucciones de un bloque, que debe cerrarse con `cierre`."""
        self.abiertos.append(abierto_en.lexema)
        try:
            return self._bloque(cierre, abierto_en)
        finally:
            self.abiertos.pop()

    def _encabezado(self, regla, kw: Token):
        """Analiza el encabezado de un bloque. Si falla, salta el resto de esa
        línea para seguir analizando el bloque sin errores en cascada."""
        try:
            return regla()
        except ParseError:
            while not self._es("EOF") and self.actual.linea == kw.linea:
                if self._avanzar().tipo in ("ENTONCES", "HACER"):
                    break
            return None

    def instruccion(self):
        tok = self.actual
        if tok.tipo == "LEER":
            return self.lectura()
        if tok.tipo == "ESCRIBIR":
            return self.escritura()
        if tok.tipo == "SI":
            return self.condicional()
        if tok.tipo == "PARA":
            return self.para()
        if tok.tipo == "MIENTRAS":
            return self.mientras()
        if tok.tipo == "DIMENSION":
            return self.dimension()
        if tok.tipo == "FUNCION":
            return self.funcion()
        if tok.tipo == "RETORNAR":
            if "Funcion" in self.abiertos:
                self._fallar("'Retornar' debe ser la última instrucción de la función, fuera de otros bloques", tok)
            self._fallar("'Retornar' fuera de una función", tok)
        if tok.tipo == "HASTA":
            self._fallar("'Hasta' sin un 'Para' que lo preceda", tok)
        if tok.tipo == "HACER":
            self._fallar("'Hacer' sin un 'Para' o 'Mientras' que lo preceda", tok)
        if tok.tipo == "ID":
            if self._ver().tipo in ("ASIGNACION", "CORCHETE_IZQ"):
                return self.asignacion()
            if self._ver().tipo == "PAR_IZQ" and tok.lexema.lower() not in _RESERVADAS_MINUS:
                self._fallar(
                    f"la llamada a '{tok.lexema}' debe usarse dentro de una expresión, "
                    f"ej. x = {tok.lexema}(...)", tok,
                )
            sugerencia = _RESERVADAS_MINUS.get(tok.lexema.lower())
            if sugerencia:
                self._fallar(
                    f"'{tok.lexema}' no es una instrucción válida. ¿Quiso decir '{sugerencia}'? "
                    "(las palabras reservadas distinguen mayúsculas y minúsculas)", tok,
                )
            self._avanzar()
            if self._es("OP_REL") and self.actual.lexema == "==":
                self._fallar("para asignar un valor use '=' en lugar de '=='")
            self._fallar(
                f"se esperaba '=' después de '{tok.lexema}' para una asignación, "
                f"pero se encontró {_describir(self.actual)}"
            )
        if tok.tipo == "ENTONCES":
            self._fallar("'Entonces' sin un 'Si' que lo preceda", tok)
        self._fallar(f"instrucción no válida: {_describir(tok)}", tok)

    def destino(self):
        tok = self._avanzar()
        if self._es("CORCHETE_IZQ"):
            return self._indice(tok)
        return ast.Variable(tok.linea, tok.lexema, tok.columna)

    def _indice(self, tok: Token) -> ast.Indice:
        abre = self._avanzar()  # '['
        indice = self.expresion()
        if not self._es("CORCHETE_DER"):
            self._fallar(
                f"falta ']' para cerrar el corchete abierto en la columna {abre.columna}; "
                f"se encontró {_describir(self.actual)}"
            )
        self._avanzar()
        return ast.Indice(tok.linea, tok.lexema, indice, tok.columna)

    def lectura(self):
        kw = self._avanzar()
        if self.actual.tipo != "ID":
            self._fallar(
                f"'Leer' debe ir seguido de un identificador, pero se encontró {_describir(self.actual)}"
            )
        return ast.Leer(kw.linea, self.destino())

    def escritura(self):
        kw = self._avanzar()
        elementos = [self.elemento_salida("'Escribir'")]
        while self._es("COMA"):
            self._avanzar()
            elementos.append(self.elemento_salida("','"))
        return ast.Escribir(kw.linea, elementos)

    def elemento_salida(self, despues_de: str):
        if self._es("CADENA", "ID", "NUMERO", "PAR_IZQ") or (self._es("OP_ARIT") and self.actual.lexema == "-"):
            return self.expresion()
        self._fallar(
            f"se esperaba una cadena o una expresión después de {despues_de}, "
            f"pero se encontró {_describir(self.actual)}"
        )

    def asignacion(self):
        destino = self.destino()
        if self._es("OP_REL") and self.actual.lexema == "==":
            self._fallar("para asignar un valor use '=' en lugar de '=='")
        if not self._es("ASIGNACION"):
            self._fallar(f"se esperaba '=' en la asignación, pero se encontró {_describir(self.actual)}")
        self._avanzar()
        return ast.Asignacion(destino.linea, destino, self.expresion())

    def dimension(self):
        kw = self._avanzar()
        if not self._es("ID"):
            self._fallar(
                f"'Dimension' debe ir seguido del nombre del arreglo, pero se encontró {_describir(self.actual)}"
            )
        tok = self._avanzar()
        if not self._es("CORCHETE_IZQ"):
            self._fallar(
                f"se esperaba '[' con el tamaño del arreglo '{tok.lexema}', "
                f"pero se encontró {_describir(self.actual)}"
            )
        indice = self._indice(tok)
        return ast.Dimension(kw.linea, tok.lexema, indice.indice, tok.columna)

    def condicional(self):
        kw = self._avanzar()
        cond = self._encabezado(self._encabezado_si, kw)
        entonces = self._cuerpo(("SINO", "FINSI"), kw)
        sino = None
        if self._es("SINO"):
            self._avanzar()
            sino = self._cuerpo(("FINSI",), kw)
            if self._es("SINO"):
                tok = self.actual
                self._fallar(f"el 'Si' de la línea {kw.linea} ya tiene un 'Sino'", tok)
        self._esperar("FINSI", "'FinSi'")
        return ast.Si(kw.linea, cond, entonces, sino)

    def _encabezado_si(self):
        cond = self.condicion()
        if not self._es("ENTONCES"):
            self._fallar(f"se esperaba 'Entonces' después de la condición, pero se encontró {_describir(self.actual)}")
        self._avanzar()
        return cond

    def para(self):
        kw = self._avanzar()
        encabezado = self._encabezado(self._encabezado_para, kw)
        cuerpo = self._cuerpo(("FINPARA",), kw)
        self._esperar("FINPARA", "'FinPara'")
        variable, inicio, fin = encabezado or (None, None, None)
        return ast.Para(kw.linea, variable, inicio, fin, cuerpo)

    def _encabezado_para(self):
        if not self._es("ID"):
            self._fallar(
                f"'Para' debe ir seguido de la variable de control, pero se encontró {_describir(self.actual)}"
            )
        tok = self._avanzar()
        self._esperar("ASIGNACION", f"'=' después de la variable de control '{tok.lexema}'")
        inicio = self.expresion()
        self._esperar("HASTA", "'Hasta' después del valor inicial del 'Para'")
        fin = self.expresion()
        self._esperar("HACER", "'Hacer' después del límite del 'Para'")
        return ast.Variable(tok.linea, tok.lexema, tok.columna), inicio, fin

    def mientras(self):
        kw = self._avanzar()
        cond = self._encabezado(self._encabezado_mientras, kw)
        cuerpo = self._cuerpo(("FINMIENTRAS",), kw)
        self._esperar("FINMIENTRAS", "'FinMientras'")
        return ast.Mientras(kw.linea, cond, cuerpo)

    def _encabezado_mientras(self):
        cond = self.condicion()
        self._esperar("HACER", "'Hacer' después de la condición del 'Mientras'")
        return cond

    def funcion(self):
        kw = self._avanzar()
        if self.abiertos:
            self.errores.error(
                SINTACTICO,
                "las funciones solo pueden declararse en el nivel principal del programa",
                kw.linea, kw.columna,
            )
        retorno, nombre, parametros = self._encabezado(self._encabezado_funcion, kw) or (None, None, [])
        cuerpo = self._cuerpo(("RETORNAR", "FINFUNCION"), kw)
        if self._es("FINFUNCION"):
            tok = self._avanzar()
            self.errores.error(
                SINTACTICO,
                f"la función de la línea {kw.linea} debe terminar con 'Retornar' antes de 'FinFuncion'",
                tok.linea, tok.columna,
            )
        else:
            cuerpo.append(self._retornar(kw))
        return ast.Funcion(kw.linea, nombre.lexema if nombre else None, retorno, parametros, cuerpo,
                           nombre.columna if nombre else 0)

    def _retornar(self, kw: Token) -> ast.Retornar:
        tok = self._avanzar()
        var = None
        if self._es("ID"):
            var = self._avanzar()
        else:
            self._registrar_falta(
                f"'Retornar' debe ir seguido de una variable, pero se encontró {_describir(self.actual)}"
            )
        if not self._es("FINFUNCION"):
            sobrante = self.actual
            self.errores.error(
                SINTACTICO,
                f"se esperaba 'FinFuncion' después de 'Retornar', pero se encontró {_describir(sobrante)}",
                sobrante.linea, sobrante.columna,
            )
            while not self._es("FINFUNCION", "FIN", "EOF"):
                self._avanzar()
            if not self._es("FINFUNCION"):
                self._sin_cerrar(kw)
        self._avanzar()
        return ast.Retornar(tok.linea, ast.Variable(var.linea, var.lexema, var.columna) if var else None)

    def _encabezado_funcion(self):
        if not self._es("ID"):
            self._fallar(
                f"'Funcion' debe ir seguido de la variable de retorno, pero se encontró {_describir(self.actual)}"
            )
        ret = self._avanzar()
        self._esperar("ASIGNACION", f"'=' después de la variable de retorno '{ret.lexema}'")
        if not self._es("ID"):
            self._fallar(f"se esperaba el nombre de la función, pero se encontró {_describir(self.actual)}")
        nombre = self._avanzar()
        self._esperar("PAR_IZQ", f"'(' después del nombre de la función '{nombre.lexema}'")
        parametros = []
        if not self._es("PAR_DER"):
            while True:
                if not self._es("ID"):
                    self._fallar(f"se esperaba el nombre de un parámetro, pero se encontró {_describir(self.actual)}")
                tok = self._avanzar()
                parametros.append(ast.Variable(tok.linea, tok.lexema, tok.columna))
                if not self._es("COMA"):
                    break
                self._avanzar()
        self._esperar("PAR_DER", "')' para cerrar los parámetros")
        return ast.Variable(ret.linea, ret.lexema, ret.columna), nombre, parametros

    def condicion(self):
        nodo = self._conj()
        while self._es("O"):
            op = self._avanzar()
            nodo = ast.Logica(op.linea, op.lexema, nodo, self._conj())
        if self._es("ID") and self.actual.lexema.lower() in ("o", "y", "and", "or"):
            self._fallar(f"operador lógico '{self.actual.lexema}' no válido; use 'Y' u 'O'")
        return nodo

    def _conj(self):
        nodo = self._neg()
        while self._es("Y"):
            op = self._avanzar()
            nodo = ast.Logica(op.linea, op.lexema, nodo, self._neg())
        return nodo

    def _neg(self):
        if self._es("NO"):
            op = self._avanzar()
            return ast.NoLogico(op.linea, self.comparacion())
        return self.comparacion()

    def comparacion(self):
        if self._es("PAR_IZQ"):
            # "(" puede abrir una expresión, `(a + b) > c`, o una condición,
            # `(a > b)`. Se intenta lo primero y, si no resulta, se retrocede.
            comp = self._comparacion_con_expresion()
            return comp if comp is not None else self._condicion_agrupada()
        izq = self.expresion()
        return self._resto_comparacion(izq)

    def _comparacion_con_expresion(self):
        pos, n_errores = self.pos, len(self.errores.errores)
        try:
            izq = self.expresion()
            if self._es("OP_REL"):
                return self._resto_comparacion(izq)
        except ParseError:
            pass
        self.pos = pos
        del self.errores.errores[n_errores:]
        return None

    def _condicion_agrupada(self):
        abre = self._avanzar()
        interior = self.condicion()
        if not self._es("PAR_DER"):
            self._fallar(
                f"falta ')' para cerrar la comparación abierta en la columna {abre.columna}; "
                f"se encontró {_describir(self.actual)}"
            )
        self._avanzar()
        # Toda comparación se genera ya entre paréntesis
        return interior if isinstance(interior, ast.Comparacion) else ast.Agrupacion(abre.linea, interior)

    def _resto_comparacion(self, izq):
        if self._es("ASIGNACION"):
            self._fallar("para comparar use '==' en lugar de '='")
        if not self._es("OP_REL"):
            self._fallar(
                "se esperaba un operador relacional (>=, <=, >, <, ==, !=), "
                f"pero se encontró {_describir(self.actual)}"
            )
        op = self._avanzar()
        return ast.Comparacion(op.linea, op.lexema, izq, self.expresion())

    def expresion(self):
        nodo = self.termino()
        while self._es("OP_ARIT") and self.actual.lexema in "+-":
            op = self._avanzar()
            nodo = ast.Binaria(op.linea, op.lexema, nodo, self.termino())
        return nodo

    def termino(self):
        nodo = self.factor()
        while self._es("OP_ARIT") and self.actual.lexema in "*/":
            op = self._avanzar()
            nodo = ast.Binaria(op.linea, op.lexema, nodo, self.factor())
        return nodo

    def factor(self):
        tok = self.actual
        if tok.tipo == "ID":
            self._avanzar()
            if self._es("CORCHETE_IZQ"):
                return self._indice(tok)
            if self._es("PAR_IZQ"):
                return self._llamada(tok)
            return ast.Variable(tok.linea, tok.lexema, tok.columna)
        if tok.tipo == "NUMERO":
            self._avanzar()
            return ast.Numero(tok.linea, tok.lexema)
        if tok.tipo == "CADENA":
            self._avanzar()
            return ast.Cadena(tok.linea, tok.lexema)
        if tok.tipo == "PAR_IZQ":
            self._avanzar()
            expr = self.expresion()
            if not self._es("PAR_DER"):
                self._fallar(
                    f"falta ')' para cerrar el paréntesis abierto en la línea {tok.linea}, "
                    f"columna {tok.columna}; se encontró {_describir(self.actual)}"
                )
            self._avanzar()
            return ast.Agrupacion(tok.linea, expr)
        if tok.tipo == "OP_ARIT" and tok.lexema == "-":
            self._avanzar()
            return ast.Negativo(tok.linea, self.factor())
        self._fallar(
            f"se esperaba un número, una cadena, una variable o '(', pero se encontró {_describir(tok)}"
        )

    def _llamada(self, tok: Token) -> ast.Llamada:
        abre = self._avanzar()  # '('
        argumentos = []
        if not self._es("PAR_DER"):
            argumentos.append(self.expresion())
            while self._es("COMA"):
                self._avanzar()
                argumentos.append(self.expresion())
        if not self._es("PAR_DER"):
            self._fallar(
                f"falta ')' para cerrar la llamada a '{tok.lexema}' abierta en la columna {abre.columna}; "
                f"se encontró {_describir(self.actual)}"
            )
        self._avanzar()
        return ast.Llamada(tok.linea, tok.lexema, argumentos, tok.columna)


def analizar(tokens: list[Token], errores: ErrorManager) -> ast.Programa:
    return Parser(tokens, errores).programa()
