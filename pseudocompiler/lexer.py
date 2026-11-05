"""Fase 1: Análisis léxico.

Recorre el código fuente carácter por carácter y lo divide en tokens:
palabras reservadas, identificadores, números, cadenas, operadores y
símbolos. Los comentarios (`//` hasta el fin de línea) se descartan.
"""

from dataclasses import dataclass

from .errors import LEXICO, ErrorManager

# Palabras reservadas -> tipo de token
PALABRAS_RESERVADAS = {
    "Inicio": "INICIO",
    "Fin": "FIN",
    "Leer": "LEER",
    "Escribir": "ESCRIBIR",
    "Si": "SI",
    "Entonces": "ENTONCES",
    "Sino": "SINO",
    "FinSi": "FINSI",
    "Para": "PARA",
    "Hasta": "HASTA",
    "Hacer": "HACER",
    "FinPara": "FINPARA",
    "Mientras": "MIENTRAS",
    "FinMientras": "FINMIENTRAS",
    "Dimension": "DIMENSION",
    "Funcion": "FUNCION",
    "Retornar": "RETORNAR",
    "FinFuncion": "FINFUNCION",
    "Y": "Y",
    "O": "O",
    "NO": "NO",
}

# Descripción legible de cada tipo de token (para la tabla de tokens)
DESCRIPCION = {
    "INICIO": "Palabra reservada",
    "FIN": "Palabra reservada",
    "LEER": "Palabra reservada",
    "ESCRIBIR": "Palabra reservada",
    "SI": "Palabra reservada",
    "ENTONCES": "Palabra reservada",
    "SINO": "Palabra reservada",
    "FINSI": "Palabra reservada",
    "PARA": "Palabra reservada",
    "HASTA": "Palabra reservada",
    "HACER": "Palabra reservada",
    "FINPARA": "Palabra reservada",
    "MIENTRAS": "Palabra reservada",
    "FINMIENTRAS": "Palabra reservada",
    "DIMENSION": "Palabra reservada",
    "FUNCION": "Palabra reservada",
    "RETORNAR": "Palabra reservada",
    "FINFUNCION": "Palabra reservada",
    "Y": "Operador lógico",
    "O": "Operador lógico",
    "NO": "Operador lógico",
    "ID": "Identificador",
    "NUMERO": "Número (constante)",
    "CADENA": "Cadena de texto",
    "OP_ARIT": "Operador aritmético",
    "OP_REL": "Operador relacional",
    "ASIGNACION": "Operador de asignación",
    "PAR_IZQ": "Paréntesis de apertura",
    "PAR_DER": "Paréntesis de cierre",
    "CORCHETE_IZQ": "Corchete de apertura",
    "CORCHETE_DER": "Corchete de cierre",
    "COMA": "Coma",
    "EOF": "Fin de archivo",
}


@dataclass
class Token:
    tipo: str
    lexema: str
    linea: int
    columna: int

    @property
    def descripcion(self) -> str:
        return DESCRIPCION.get(self.tipo, self.tipo)

    def __repr__(self) -> str:
        return f"Token({self.tipo}, {self.lexema!r}, {self.linea}:{self.columna})"


def _es_letra(c: str) -> bool:
    return ("a" <= c <= "z") or ("A" <= c <= "Z")


def _es_digito(c: str) -> bool:
    return "0" <= c <= "9"


class Lexer:
    def __init__(self, codigo: str, errores: ErrorManager):
        self.codigo = codigo.replace("\r\n", "\n").replace("\t", "    ")
        self.errores = errores
        self.pos = 0
        self.linea = 1
        self.col = 1
        self.tokens: list[Token] = []

    # -- utilidades -------------------------------------------------------
    def _actual(self) -> str:
        return self.codigo[self.pos] if self.pos < len(self.codigo) else ""

    def _siguiente(self, k: int = 1) -> str:
        p = self.pos + k
        return self.codigo[p] if p < len(self.codigo) else ""

    def _avanzar(self) -> str:
        c = self._actual()
        self.pos += 1
        if c == "\n":
            self.linea += 1
            self.col = 1
        else:
            self.col += 1
        return c

    def _agregar(self, tipo, lexema, linea, col):
        self.tokens.append(Token(tipo, lexema, linea, col))

    def _error(self, mensaje, linea, col):
        self.errores.error(LEXICO, mensaje, linea, col)

    # -- análisis ---------------------------------------------------------
    def analizar(self) -> list[Token]:
        while self.pos < len(self.codigo):
            c = self._actual()
            linea, col = self.linea, self.col

            if c in " \n":
                self._avanzar()
            elif c == "/" and self._siguiente() == "/":
                while self._actual() not in ("", "\n"):
                    self._avanzar()
            elif _es_letra(c) or c == "_":
                self._identificador(linea, col)
            elif _es_digito(c):
                self._numero(linea, col)
            elif c == '"':
                self._cadena(linea, col)
            elif c in "<>=!":
                self._operador_relacional(linea, col)
            elif c in "+-*/":
                self._agregar("OP_ARIT", self._avanzar(), linea, col)
            elif c == "(":
                self._agregar("PAR_IZQ", self._avanzar(), linea, col)
            elif c == ")":
                self._agregar("PAR_DER", self._avanzar(), linea, col)
            elif c == "[":
                self._agregar("CORCHETE_IZQ", self._avanzar(), linea, col)
            elif c == "]":
                self._agregar("CORCHETE_DER", self._avanzar(), linea, col)
            elif c == ",":
                self._agregar("COMA", self._avanzar(), linea, col)
            elif c in "“”":
                self._avanzar()
                self._error(
                    f"comilla tipográfica '{c}' no válida; use comillas dobles rectas (\")",
                    linea, col,
                )
            else:
                self._avanzar()
                self._error(f"carácter no reconocido '{c}'", linea, col)

        self._agregar("EOF", "", self.linea, self.col)
        return self.tokens

    def _identificador(self, linea, col):
        inicio = self.pos
        invalido = None
        while True:
            c = self._actual()
            if _es_letra(c) or _es_digito(c) or c == "_":
                self._avanzar()
            elif c.isalpha():  # letras con tilde, ñ, etc.
                invalido = invalido or (c, self.col)
                self._avanzar()
            else:
                break
        lexema = self.codigo[inicio:self.pos]

        if lexema.startswith("_"):
            self._error(
                f"identificador '{lexema}' inválido: debe comenzar con una letra",
                linea, col,
            )
            return
        if invalido:
            self._error(
                f"carácter '{invalido[0]}' no permitido en el identificador '{lexema}' "
                "(solo letras sin tilde, dígitos y '_')",
                linea, invalido[1],
            )
            return
        tipo = PALABRAS_RESERVADAS.get(lexema, "ID")
        self._agregar(tipo, lexema, linea, col)

    def _numero(self, linea, col):
        inicio = self.pos
        while _es_digito(self._actual()):
            self._avanzar()
        if self._actual() == ".":
            if not _es_digito(self._siguiente()):
                self._avanzar()
                lexema = self.codigo[inicio:self.pos]
                self._error(
                    f"número mal formado '{lexema}': se esperaba un dígito después del punto",
                    linea, col,
                )
                return
            self._avanzar()
            while _es_digito(self._actual()):
                self._avanzar()
            if self._actual() == "." and _es_digito(self._siguiente()):
                while self._actual() == "." or _es_digito(self._actual()):
                    self._avanzar()
                lexema = self.codigo[inicio:self.pos]
                self._error(f"número mal formado '{lexema}': tiene más de un punto decimal", linea, col)
                return
        # Un número pegado a letras (ej. 2abc) no es un identificador válido
        if _es_letra(self._actual()) or self._actual() == "_":
            while _es_letra(self._actual()) or _es_digito(self._actual()) or self._actual() == "_":
                self._avanzar()
            lexema = self.codigo[inicio:self.pos]
            self._error(
                f"'{lexema}' no es válido: un identificador no puede comenzar con un dígito",
                linea, col,
            )
            return
        self._agregar("NUMERO", self.codigo[inicio:self.pos], linea, col)

    def _cadena(self, linea, col):
        self._avanzar()  # comilla de apertura
        inicio = self.pos
        while self._actual() not in ('"', "\n", ""):
            self._avanzar()
        if self._actual() != '"':
            self._error("cadena de texto sin cerrar: falta la comilla doble final (\")", linea, col)
            return
        texto = self.codigo[inicio:self.pos]
        self._avanzar()  # comilla de cierre
        self._agregar("CADENA", texto, linea, col)

    def _operador_relacional(self, linea, col):
        c = self._avanzar()
        if self._actual() == "=":
            self._avanzar()
            self._agregar("OP_REL", c + "=", linea, col)
        elif c in "<>":
            self._agregar("OP_REL", c, linea, col)
        elif c == "=":
            self._agregar("ASIGNACION", "=", linea, col)
        else:  # '!' solo
            self._error("operador '!' incompleto: ¿quiso escribir '!='?", linea, col)


def tokenizar(codigo: str, errores: ErrorManager) -> list[Token]:
    return Lexer(codigo, errores).analizar()
