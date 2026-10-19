"""Fase 4: Síntesis (generación de código).

Recorre el AST y produce el código equivalente en Python y JavaScript,
aplicando las reglas de traducción definidas en la Fase 1:

    Pseudocódigo        JavaScript                     Python
    Inicio / Fin        async function main() {...}    # Inicio / # Fin
    Escribir "t", x     console.log("t" + x);          print("t", formatear(x), sep="")
    Leer x              const x = await leer();        x = float(input())
    x = expr            const x = expr;                x = expr
    Si (c) Entonces     if (c) {                       if c:
    Sino                } else {                       else:
    FinSi               }                              (fin de la indentación)
    Y                   &&                             and
"""

from . import ast_nodes as ast
from .semantic import TablaSimbolos

COLUMNA_COMENTARIO = 48


def _cadena(texto: str) -> str:
    return '"' + texto.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _alinear(lineas, marca):
    salida = []
    for codigo, comentario, _ in lineas:
        if comentario:
            relleno = max(1, COLUMNA_COMENTARIO - len(codigo))
            salida.append(codigo + " " * relleno + f"{marca} {comentario}")
        else:
            salida.append(codigo)
    return "\n".join(salida) + "\n"


def _resumen_si(si: ast.Si) -> str:
    return "Si ... Y ... Entonces" if len(si.condicion.comparaciones) > 1 else "Si ... Entonces"


def _contiene(instrucciones, tipo) -> bool:
    for ins in instrucciones:
        if isinstance(ins, tipo):
            return True
        if isinstance(ins, ast.Si) and (
            _contiene(ins.entonces, tipo) or _contiene(ins.sino or [], tipo)
        ):
            return True
    return False


def _escribe_numeros(instrucciones) -> bool:
    for ins in instrucciones:
        if isinstance(ins, ast.Escribir) and any(not isinstance(e, ast.Cadena) for e in ins.elementos):
            return True
        if isinstance(ins, ast.Si) and (
            _escribe_numeros(ins.entonces) or _escribe_numeros(ins.sino or [])
        ):
            return True
    return False


class _GenBase:
    def __init__(self, tabla: TablaSimbolos):
        self.tabla = tabla
        self.lineas: list[tuple[str, str, int]] = []
        self.nivel = 0
        self.linea_fuente = 0   # línea del pseudocódigo que se está traduciendo

    def emitir(self, codigo="", comentario=""):
        self.lineas.append(
            ((self.SANGRIA * self.nivel + codigo) if codigo else "", comentario, self.linea_fuente)
        )

    @property
    def mapa(self) -> list[int]:
        """mapa[i] = línea del pseudocódigo que originó la línea i+1 del código generado."""
        return [linea for _, _, linea in self.lineas]

    def expr(self, e) -> str:
        match e:
            case ast.Numero(valor=v):
                return v
            case ast.Variable(nombre=n):
                return self.nombre(n)
            case ast.Agrupacion(expr=x):
                return f"({self.expr(x)})"
            case ast.Negativo(operando=x):
                interior = self.expr(x)
                if isinstance(x, (ast.Negativo, ast.Binaria)):
                    interior = f"({interior})"
                return f"-{interior}"
            case ast.Binaria(op=op, izq=i, der=d):
                return f"{self.expr(i)} {op} {self.expr(d)}"
        raise ValueError(f"expresión desconocida: {e!r}")

    def comparacion(self, c: ast.Comparacion) -> str:
        return f"({self.expr(c.izq)} {c.op} {self.expr(c.der)})"


# ---------------------------------------------------------------------------
class GeneradorPython(_GenBase):
    SANGRIA = "    "

    def nombre(self, n):
        return self.tabla[n].nombre_py if n in self.tabla else n

    def generar(self, prog: ast.Programa) -> str:
        self.emitir("# Código generado por PseudoCompilador 95 (Python)")
        if _escribe_numeros(prog.instrucciones):
            self.emitir()
            self.emitir("def formatear(valor):")
            self.emitir("    # Muestra los números enteros sin el .0")
            self.emitir("    if isinstance(valor, float) and valor.is_integer():")
            self.emitir("        return int(valor)")
            self.emitir("    return valor")
        self.emitir()
        self.emitir("# Inicio")
        self.bloque(prog.instrucciones)
        self.emitir("# Fin")
        return _alinear(self.lineas, "#")

    def bloque(self, instrucciones):
        if not instrucciones:
            self.emitir("pass", "bloque vacío")
        for ins in instrucciones:
            self.instruccion(ins)

    def instruccion(self, ins):
        self.linea_fuente = ins.linea
        match ins:
            case ast.Leer(variable=v):
                self.emitir(f"{self.nombre(v.nombre)} = float(input())", f"Leer {v.nombre}")
            case ast.Asignacion(variable=v, expr=e):
                self.emitir(f"{self.nombre(v.nombre)} = {self.expr(e)}", "Asignación")
            case ast.Escribir(elementos=elems):
                partes = [
                    _cadena(el.texto) if isinstance(el, ast.Cadena) else f"formatear({self.expr(el)})"
                    for el in elems
                ]
                sep = ', sep=""' if len(partes) > 1 else ""
                self.emitir(f"print({', '.join(partes)}{sep})", "Escribir")
            case ast.Si():
                cond = " and ".join(self.comparacion(c) for c in ins.condicion.comparaciones)
                self.emitir(f"if {cond}:", _resumen_si(ins))
                self.nivel += 1
                self.bloque(ins.entonces)
                self.nivel -= 1
                if ins.sino is not None:
                    self.emitir("else:", "Sino")
                    self.nivel += 1
                    self.bloque(ins.sino)
                    self.nivel -= 1
                # FinSi no genera código: solo termina la indentación


# ---------------------------------------------------------------------------
class GeneradorJS(_GenBase):
    SANGRIA = "  "

    def nombre(self, n):
        return self.tabla[n].nombre_js if n in self.tabla else n

    def generar(self, prog: ast.Programa) -> str:
        usa_leer = _contiene(prog.instrucciones, ast.Leer)
        self.emitir("// Código generado por PseudoCompilador 95 (JavaScript / Node.js)")
        if usa_leer:
            self.emitir('const readline = require("readline");')
        self.emitir()
        self.emitir("async function main() {", "Inicio")
        self.nivel = 1
        if usa_leer:
            self.emitir("const rl = readline.createInterface({ input: process.stdin });")
            self.emitir("const lineas = rl[Symbol.asyncIterator]();")
            self.emitir("const leer = async () => Number((await lineas.next()).value);", "Leer: línea -> número")
        variables_let = [s.nombre_js for s in self.tabla if s.declaracion_js == "let"]
        if variables_let:
            self.emitir(f"let {', '.join(variables_let)};", "variables que cambian o se asignan en bloques")
        if usa_leer or variables_let:
            self.emitir()
        self.bloque(prog.instrucciones)
        if usa_leer:
            self.emitir()
            self.emitir("rl.close();")
        self.nivel = 0
        self.emitir("}", "Fin")
        self.emitir()
        self.emitir("main();")
        return _alinear(self.lineas, "//")

    def bloque(self, instrucciones):
        for ins in instrucciones:
            self.instruccion(ins)

    def _destino(self, nombre):
        s = self.tabla[nombre]
        prefijo = "const " if s.declaracion_js == "const" else ""
        return prefijo + s.nombre_js

    def instruccion(self, ins):
        self.linea_fuente = ins.linea
        match ins:
            case ast.Leer(variable=v):
                self.emitir(f"{self._destino(v.nombre)} = await leer();", f"Leer {v.nombre}")
            case ast.Asignacion(variable=v, expr=e):
                self.emitir(f"{self._destino(v.nombre)} = {self.expr(e)};", "Asignación")
            case ast.Escribir(elementos=elems):
                partes = []
                for el in elems:
                    if isinstance(el, ast.Cadena):
                        partes.append(_cadena(el.texto))
                    else:
                        texto = self.expr(el)
                        if isinstance(el, ast.Binaria) and len(elems) > 1:
                            texto = f"({texto})"
                        partes.append(texto)
                # Si el primer elemento no es texto, se fuerza la concatenación de cadenas
                if len(elems) > 1 and not isinstance(elems[0], ast.Cadena):
                    partes[0] = f"String({partes[0]})"
                self.emitir(f"console.log({' + '.join(partes)});", "Escribir")
            case ast.Si():
                comps = [self.comparacion(c) for c in ins.condicion.comparaciones]
                cond = comps[0] if len(comps) == 1 else "(" + " && ".join(comps) + ")"
                self.emitir(f"if {cond} {{", _resumen_si(ins))
                self.nivel += 1
                self.bloque(ins.entonces)
                self.nivel -= 1
                if ins.sino is not None:
                    self.emitir("} else {", "Sino")
                    self.nivel += 1
                    self.bloque(ins.sino)
                    self.nivel -= 1
                self.emitir("}", "FinSi")


def generar_python(prog, tabla) -> tuple[str, list[int]]:
    gen = GeneradorPython(tabla)
    return gen.generar(prog), gen.mapa


def generar_js(prog, tabla) -> tuple[str, list[int]]:
    gen = GeneradorJS(tabla)
    return gen.generar(prog), gen.mapa
