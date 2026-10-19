"""Fase 2: Análisis sintáctico.

Parser descendente recursivo que sigue la gramática EBNF de la Fase 1:

    programa     = "Inicio", { instruccion }, "Fin" ;
    instruccion  = lectura | escritura | asignacion | condicional ;
    lectura      = "Leer", identificador ;
    escritura    = "Escribir", elemento_salida, { ",", elemento_salida } ;
    elemento_salida = cadena | expresion ;
    asignacion   = identificador, "=", expresion ;
    condicional  = "Si", condicion, "Entonces", { instruccion },
                   [ "Sino", { instruccion } ], "FinSi" ;
    condicion    = comparacion, { "Y", comparacion } ;
    comparacion  = "(", expresion, operador_relacional, expresion, ")" ;
    expresion    = termino, { ("+" | "-"), termino } ;
    termino      = factor, { ("*" | "/"), factor } ;
    factor       = identificador | numero | "(", expresion, ")" ;

Extensión: se admite el menos unario en `factor` (ej. `x = -5`).

Ante un error, el parser lo registra con su línea y se re-sincroniza en la
siguiente instrucción (modo pánico) para poder reportar varios errores.
"""

from . import ast_nodes as ast
from .errors import SINTACTICO, ErrorManager
from .lexer import PALABRAS_RESERVADAS, Token

INICIO_INSTRUCCION = {"LEER", "ESCRIBIR", "SI", "SINO", "FINSI", "FIN", "EOF"}
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
        """Lanza un error. Si lo esperado faltaba al final de una línea,
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
        raise ParseError(mensaje)

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
                or (tok.tipo == "ID" and self._ver().tipo == "ASIGNACION")
            ):
                return
            if tok.tipo in ("FINSI", "SINO", "FIN"):
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
                    self.errores.error(
                        SINTACTICO,
                        f"el bloque 'Si' abierto en la línea {abierto_en.linea} no se cerró con 'FinSi'",
                        abierto_en.linea, abierto_en.columna,
                    )
                    raise ParseError("Si sin cerrar")
                return instrucciones
            if abierto_en is None and self._es("SINO", "FINSI"):
                tok = self._avanzar()
                self.errores.error(
                    SINTACTICO,
                    f"'{tok.lexema}' sin un 'Si' correspondiente",
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

    def instruccion(self):
        tok = self.actual
        if tok.tipo == "LEER":
            return self.lectura()
        if tok.tipo == "ESCRIBIR":
            return self.escritura()
        if tok.tipo == "SI":
            return self.condicional()
        if tok.tipo == "ID":
            if self._ver().tipo == "ASIGNACION":
                return self.asignacion()
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

    def lectura(self):
        kw = self._avanzar()
        if self.actual.tipo != "ID":
            self._fallar(
                f"'Leer' debe ir seguido de un identificador, pero se encontró {_describir(self.actual)}"
            )
        tok = self._avanzar()
        return ast.Leer(kw.linea, ast.Variable(tok.linea, tok.lexema, tok.columna))

    def escritura(self):
        kw = self._avanzar()
        elementos = [self.elemento_salida("'Escribir'")]
        while self._es("COMA"):
            self._avanzar()
            elementos.append(self.elemento_salida("','"))
        return ast.Escribir(kw.linea, elementos)

    def elemento_salida(self, despues_de: str):
        if self._es("CADENA"):
            tok = self._avanzar()
            return ast.Cadena(tok.linea, tok.lexema)
        if self._es("ID", "NUMERO", "PAR_IZQ") or (self._es("OP_ARIT") and self.actual.lexema == "-"):
            return self.expresion()
        self._fallar(
            f"se esperaba una cadena o una expresión después de {despues_de}, "
            f"pero se encontró {_describir(self.actual)}"
        )

    def asignacion(self):
        tok = self._avanzar()
        self._avanzar()  # '='
        if self._es("CADENA"):
            self._fallar("solo se pueden asignar expresiones numéricas, no cadenas de texto")
        expr = self.expresion()
        return ast.Asignacion(tok.linea, ast.Variable(tok.linea, tok.lexema, tok.columna), expr)

    def condicional(self):
        kw = self._avanzar()
        try:
            cond = self.condicion()
            if not self._es("ENTONCES"):
                self._fallar(f"se esperaba 'Entonces' después de la condición, pero se encontró {_describir(self.actual)}")
            self._avanzar()
        except ParseError:
            # Recuperación local: se salta el resto del encabezado del Si
            # para seguir analizando su bloque sin errores en cascada.
            cond = None
            while not self._es("EOF") and self.actual.linea == kw.linea:
                if self._avanzar().tipo == "ENTONCES":
                    break
        entonces = self._bloque(cierre=("SINO", "FINSI"), abierto_en=kw)
        sino = None
        if self._es("SINO"):
            self._avanzar()
            sino = self._bloque(cierre=("FINSI",), abierto_en=kw)
            if self._es("SINO"):
                tok = self.actual
                self._fallar(f"el 'Si' de la línea {kw.linea} ya tiene un 'Sino'", tok)
        self._esperar("FINSI", "'FinSi'")
        return ast.Si(kw.linea, cond, entonces, sino)

    def condicion(self):
        linea = self.actual.linea
        comps = [self.comparacion()]
        while self._es("Y"):
            self._avanzar()
            comps.append(self.comparacion())
        if self._es("ID") and self.actual.lexema.lower() in ("o", "and", "or"):
            self._fallar(f"operador lógico '{self.actual.lexema}' no soportado; use 'Y'")
        return ast.Condicion(linea, comps)

    def comparacion(self):
        if not self._es("PAR_IZQ"):
            self._fallar(
                "cada comparación debe ir entre paréntesis, ej. (nota >= 6); "
                f"se encontró {_describir(self.actual)}"
            )
        abre = self._avanzar()
        izq = self.expresion()
        if self._es("ASIGNACION"):
            self._fallar("para comparar use '==' en lugar de '='")
        if not self._es("OP_REL"):
            self._fallar(
                "se esperaba un operador relacional (>=, <=, >, <, ==, !=), "
                f"pero se encontró {_describir(self.actual)}"
            )
        op = self._avanzar().lexema
        der = self.expresion()
        if not self._es("PAR_DER"):
            self._fallar(
                f"falta ')' para cerrar la comparación abierta en la columna {abre.columna}; "
                f"se encontró {_describir(self.actual)}"
            )
        self._avanzar()
        return ast.Comparacion(abre.linea, op, izq, der)

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
            return ast.Variable(tok.linea, tok.lexema, tok.columna)
        if tok.tipo == "NUMERO":
            self._avanzar()
            return ast.Numero(tok.linea, tok.lexema)
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
        if tok.tipo == "CADENA":
            self._fallar("no se puede usar una cadena de texto dentro de una operación aritmética")
        self._fallar(
            f"se esperaba un número, una variable o '(', pero se encontró {_describir(tok)}"
        )


def analizar(tokens: list[Token], errores: ErrorManager) -> ast.Programa:
    return Parser(tokens, errores).programa()
