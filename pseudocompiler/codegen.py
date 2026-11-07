"""Fase 4: Síntesis (generación de código).

Recorre el AST y produce el código equivalente en Python y JavaScript,
aplicando las reglas de traducción del lenguaje:

    Pseudocódigo          JavaScript                      Python
    Inicio / Fin          async function main() {...}     # Inicio / # Fin
    Escribir "t", x       console.log("t" + x);           print("t", formatear(x), sep="")
    Leer x                const x = await leer();         x = float(input())
    x = expr              const x = expr;                 x = expr
    Si (c) Entonces       if (c) {                        if (c):
    Sino                  } else {                        else:
    FinSi                 }                               (fin de la indentación)
    Y / O / NO            && / || / !                     and / or / not
    Para i=a Hasta b      for (let i=a; i<=b; i++) {      for i in range(a, int(b) + 1):
    Mientras c Hacer      while (c) {                     while c:
    Dimension v[n]        new Array(n + 1).fill(0)        [0.0] * (int(n) + 1)
    Funcion r = f(p)      function f(p) {                 def f(p):
    Retornar r            return r;                       return r

Decisiones que mantienen igual el comportamiento en ambos lenguajes:

* Arreglos base 1: se reserva un elemento más y el índice 0 no se usa, de modo
  que `v[i]` se traduce directamente a `v[i]`.
* Los números se leen como reales, así que los valores que deben ser enteros
  (tamaños, índices y límites de `Para`) se truncan con `int()` / `Math.trunc()`.
* El límite de `Para` se evalúa una sola vez, como hace `range` en Python.
* La división entre cero es un error de ejecución: Python lanza
  `ZeroDivisionError` y en JavaScript lo lanza la función auxiliar `dividir`.
"""

from . import ast_nodes as ast
from .semantic import GLOBAL, TablaSimbolos

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
    match si.condicion:
        case ast.Logica(op=op):
            return f"Si ... {op} ... Entonces"
        case ast.NoLogico():
            return "Si NO ... Entonces"
    return "Si ... Entonces"


def _contiene(instrucciones, tipo) -> bool:
    return any(isinstance(n, tipo) for n in ast.recorrer(instrucciones))


def _escribe_numeros(instrucciones) -> bool:
    return any(
        isinstance(n, ast.Escribir) and any(not isinstance(e, ast.Cadena) for e in n.elementos)
        for n in ast.recorrer(instrucciones)
    )


def _es_entero_literal(e) -> bool:
    return isinstance(e, ast.Numero) and "." not in e.valor


def _divide_por_variable(instrucciones) -> bool:
    return any(
        isinstance(n, ast.Binaria) and n.op == "/" and not isinstance(n.der, ast.Numero)
        for n in ast.recorrer(instrucciones)
    )


def _limite_fijo(fin, cuerpo) -> bool:
    """El límite de un `Para` conserva su valor si nada del cuerpo lo modifica."""
    cambian = ast.asignadas(cuerpo)
    for n in ast.recorrer(fin):
        if isinstance(n, ast.Llamada):
            return False
        if isinstance(n, (ast.Variable, ast.Indice)) and n.nombre in cambian:
            return False
    return True


def _funciones_asincronas(instrucciones) -> set:
    """Funciones que necesitan `await`: leen datos o llaman a otra que lo hace."""
    funciones = [n for n in ast.recorrer(instrucciones) if isinstance(n, ast.Funcion)]
    asincronas = {f.nombre for f in funciones if _contiene(f.cuerpo, ast.Leer)}
    cambio = True
    while cambio:
        cambio = False
        for f in funciones:
            if f.nombre not in asincronas and any(
                isinstance(n, ast.Llamada) and n.nombre in asincronas for n in ast.recorrer(f.cuerpo)
            ):
                asincronas.add(f.nombre)
                cambio = True
    return asincronas


class _GenBase:
    def __init__(self, tabla: TablaSimbolos):
        self.tabla = tabla
        self.lineas: list[tuple[str, str, int]] = []
        self.nivel = 0
        self.linea_fuente = 0   # línea del pseudocódigo que se está traduciendo
        self.ambito = GLOBAL

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
            case ast.Cadena(texto=t):
                return _cadena(t)
            case ast.Variable(nombre=n):
                return self.nombre(n)
            case ast.Indice(nombre=n, indice=i):
                return f"{self.nombre(n)}[{self.indice(i)}]"
            case ast.Llamada():
                return self.llamada(e)
            case ast.Agrupacion(expr=x):
                return f"({self.expr(x)})"
            case ast.Negativo(operando=x):
                interior = self.expr(x)
                if isinstance(x, (ast.Negativo, ast.Binaria)):
                    interior = f"({interior})"
                return f"-{interior}"
            case ast.Binaria():
                return self.binaria(e)
        raise ValueError(f"expresión desconocida: {e!r}")

    def binaria(self, e: ast.Binaria) -> str:
        return f"{self.expr(e.izq)} {e.op} {self.expr(e.der)}"

    def llamada(self, e: ast.Llamada) -> str:
        args = ", ".join(self.expr(a) for a in e.argumentos)
        return f"{self.nombre(e.nombre)}({args})"

    def entero(self, e) -> str:
        """Expresión truncada a entero, salvo que ya lo sea."""
        return self.expr(e) if _es_entero_literal(e) else self.ENTERO.format(self.expr(e))

    def indice(self, e) -> str:
        if isinstance(e, ast.Variable) and self.tabla.buscar(e.nombre, self.ambito).solo_control:
            return self.expr(e)  # la variable de control de un Para ya es entera
        return self.entero(e)

    def _cuerpo(self, instrucciones):
        self.nivel += 1
        self.bloque(instrucciones)
        self.nivel -= 1

    def destino(self, d) -> str:
        return self.expr(d)

    def parametros(self, fn: ast.Funcion) -> str:
        return ", ".join(self.nombre(p.nombre) for p in fn.parametros)

    def condicion(self, c) -> str:
        match c:
            case ast.Comparacion(op=op, izq=i, der=d):
                return f"({self.expr(i)} {op} {self.expr(d)})"
            case ast.Agrupacion(expr=x):
                return f"({self.condicion(x)})"
            case ast.Logica(op=op, izq=i, der=d):
                return f"{self.condicion(i)} {self.OP_LOGICOS[op]} {self.condicion(d)}"
            case ast.NoLogico(operando=x):
                return f"{self.OP_LOGICOS['NO']}{self.condicion(x)}"
        raise ValueError(f"condición desconocida: {c!r}")


# ---------------------------------------------------------------------------
class GeneradorPython(_GenBase):
    SANGRIA = "    "
    OP_LOGICOS = {"Y": "and", "O": "or", "NO": "not "}
    ENTERO = "int({})"

    def nombre(self, n):
        s = self.tabla.buscar(n, self.ambito)
        return s.nombre_py if s is not None else n

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
            case ast.Leer(destino=d):
                self.emitir(f"{self.destino(d)} = float(input())", f"Leer {d.nombre}")
            case ast.Asignacion(destino=d, expr=e):
                self.emitir(f"{self.destino(d)} = {self.expr(e)}", "Asignación")
            case ast.Escribir(elementos=elems):
                partes = [
                    _cadena(el.texto) if isinstance(el, ast.Cadena) else f"formatear({self.expr(el)})"
                    for el in elems
                ]
                sep = ', sep=""' if len(partes) > 1 else ""
                self.emitir(f"print({', '.join(partes)}{sep})", "Escribir")
            case ast.Si():
                self.emitir(f"if {self.condicion(ins.condicion)}:", _resumen_si(ins))
                self._cuerpo(ins.entonces)
                if ins.sino is not None:
                    self.emitir("else:", "Sino")
                    self._cuerpo(ins.sino)
                # FinSi no genera código: solo termina la indentación
            case ast.Para(variable=v, inicio=a, fin=b, cuerpo=cuerpo):
                rango = f"range({self.entero(a)}, {self.entero(b)} + 1)"
                self.emitir(f"for {self.nombre(v.nombre)} in {rango}:", "Para")
                self._cuerpo(cuerpo)
            case ast.Mientras(condicion=c, cuerpo=cuerpo):
                self.emitir(f"while {self.condicion(c)}:", "Mientras")
                self._cuerpo(cuerpo)
            case ast.Dimension(nombre=n, tamano=t):
                self.emitir(f"{self.nombre(n)} = [0.0] * ({self.entero(t)} + 1)", f"Dimension {n} (base 1)")
            case ast.Funcion():
                self.ambito = ins.nombre
                self.emitir(f"def {self.nombre(ins.nombre)}({self.parametros(ins)}):", "Funcion")
                self._cuerpo(ins.cuerpo)
                self.ambito = GLOBAL
            case ast.Retornar(variable=v):
                self.emitir(f"return {self.nombre(v.nombre)}", "Retornar")


# ---------------------------------------------------------------------------
class GeneradorJS(_GenBase):
    SANGRIA = "  "
    OP_LOGICOS = {"Y": "&&", "O": "||", "NO": "!"}
    ENTERO = "Math.trunc({})"

    def __init__(self, tabla):
        super().__init__(tabla)
        self.asincronas = set()
        self.limites = 0        # contador de límites de Para guardados

    def binaria(self, e: ast.Binaria) -> str:
        if e.op == "/" and not isinstance(e.der, ast.Numero):
            return f"dividir({self.expr(e.izq)}, {self.expr(e.der)})"
        return super().binaria(e)

    def llamada(self, e: ast.Llamada) -> str:
        texto = super().llamada(e)
        return f"(await {texto})" if e.nombre in self.asincronas else texto

    def nombre(self, n):
        s = self.tabla.buscar(n, self.ambito)
        return s.nombre_js if s is not None else n

    def generar(self, prog: ast.Programa) -> str:
        usa_leer = _contiene(prog.instrucciones, ast.Leer)
        self.asincronas = _funciones_asincronas(prog.instrucciones)
        self.emitir("// Código generado por PseudoCompilador 95 (JavaScript / Node.js)")
        if usa_leer:
            self.emitir('const readline = require("readline");')
        if _divide_por_variable(prog.instrucciones):
            self.emitir()
            self.emitir("function dividir(a, b) {")
            self.emitir('  if (b === 0) throw new Error("división entre cero");')
            self.emitir("  return a / b;")
            self.emitir("}")
        self.emitir()
        self.emitir("async function main() {", "Inicio")
        self.nivel = 1
        if usa_leer:
            self.emitir("const rl = readline.createInterface({ input: process.stdin });")
            self.emitir("const lineas = rl[Symbol.asyncIterator]();")
            self.emitir("const leer = async () => Number((await lineas.next()).value);", "Leer: línea -> número")
        variables_let = self._variables_let()
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

    def _variables_let(self) -> list[str]:
        return [s.nombre_js for s in self.tabla.de_ambito(self.ambito) if s.declaracion_js == "let"]

    def destino(self, d) -> str:
        if isinstance(d, ast.Indice):
            return self.expr(d)
        return self._declarar(d.nombre)

    def _declarar(self, nombre) -> str:
        s = self.tabla.buscar(nombre, self.ambito)
        prefijo = "const " if s.declaracion_js == "const" else ""
        return prefijo + s.nombre_js

    def _condicion_js(self, c) -> str:
        """JavaScript exige paréntesis alrededor de toda la condición."""
        texto = self.condicion(c)
        return texto if isinstance(c, (ast.Comparacion, ast.Agrupacion)) else f"({texto})"

    def instruccion(self, ins):
        self.linea_fuente = ins.linea
        match ins:
            case ast.Leer(destino=d):
                self.emitir(f"{self.destino(d)} = await leer();", f"Leer {d.nombre}")
            case ast.Asignacion(destino=d, expr=e):
                self.emitir(f"{self.destino(d)} = {self.expr(e)};", "Asignación")
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
                self.emitir(f"if {self._condicion_js(ins.condicion)} {{", _resumen_si(ins))
                self._cuerpo(ins.entonces)
                if ins.sino is not None:
                    self.emitir("} else {", "Sino")
                    self._cuerpo(ins.sino)
                self.emitir("}", "FinSi")
            case ast.Para():
                self._para(ins)
            case ast.Mientras(condicion=c, cuerpo=cuerpo):
                self.emitir(f"while {self._condicion_js(c)} {{", "Mientras")
                self._cuerpo(cuerpo)
                self.emitir("}", "FinMientras")
            case ast.Dimension(nombre=n, tamano=t):
                self.emitir(
                    f"{self._declarar(n)} = new Array({self.entero(t)} + 1).fill(0);",
                    f"Dimension {n} (base 1)",
                )
            case ast.Funcion():
                self._funcion(ins)
            case ast.Retornar(variable=v):
                self.emitir(f"return {self.nombre(v.nombre)};", "Retornar")

    def _para(self, ins: ast.Para):
        s = self.tabla.buscar(ins.variable.nombre, self.ambito)
        limite = self.entero(ins.fin)
        if not _limite_fijo(ins.fin, ins.cuerpo):
            self.limites += 1
            guardado = f"_limite{self.limites}"  # el '_' inicial no es válido en el pseudocódigo
            self.emitir(f"const {guardado} = {limite};", "límite del Para (se evalúa una vez)")
            limite = guardado
        i = s.nombre_js
        declara = "let " if s.solo_control else ""
        self.emitir(f"for ({declara}{i} = {self.entero(ins.inicio)}; {i} <= {limite}; {i}++) {{", "Para")
        self._cuerpo(ins.cuerpo)
        self.emitir("}", "FinPara")

    def _funcion(self, fn: ast.Funcion):
        self.ambito = fn.nombre
        asincrona = "async " if fn.nombre in self.asincronas else ""
        self.emitir(f"{asincrona}function {self.nombre(fn.nombre)}({self.parametros(fn)}) {{", "Funcion")
        self.nivel += 1
        variables_let = self._variables_let()
        if variables_let:
            self.emitir(f"let {', '.join(variables_let)};")
        self.bloque(fn.cuerpo)
        self.nivel -= 1
        self.emitir("}", "FinFuncion")
        self.ambito = GLOBAL


def generar_python(prog, tabla) -> tuple[str, list[int]]:
    gen = GeneradorPython(tabla)
    return gen.generar(prog), gen.mapa


def generar_js(prog, tabla) -> tuple[str, list[int]]:
    gen = GeneradorJS(tabla)
    return gen.generar(prog), gen.mapa
