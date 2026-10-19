import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from pseudocompiler import compilar

EJEMPLOS = Path(__file__).resolve().parent.parent / "examples"
NODE = shutil.which("node")


def _correr_python(codigo, entradas):
    r = subprocess.run(
        [sys.executable, "-c", codigo], input="\n".join(entradas) + "\n",
        capture_output=True, text=True, timeout=10,
    )
    assert r.returncode == 0, r.stderr
    return r.stdout


def _correr_js(codigo, entradas):
    r = subprocess.run(
        [NODE, "-e", codigo], input="\n".join(entradas) + "\n",
        capture_output=True, text=True, timeout=10,
    )
    assert r.returncode == 0, r.stderr
    return r.stdout


def _ultima(salida):
    return salida.strip().splitlines()[-1]


CASOS_A = [(["4", "2", "3"], "El resultado es: 16"),
           (["10", "5", "2"], "El resultado es: 28"),
           (["6", "3", "4"], "El resultado es: 34")]
CASOS_B = [(["8", "80"], "Aprobado"),
           (["7", "60"], "Reprobado por asistencia"),
           (["4", "90"], "Reprobado por nota")]


@pytest.mark.parametrize("entradas,esperado", CASOS_A)
def test_programa_a(entradas, esperado):
    r = compilar((EJEMPLOS / "programa_a.txt").read_text())
    assert r.exito
    assert _ultima(_correr_python(r.python, entradas)) == esperado
    if NODE:
        assert _ultima(_correr_js(r.javascript, entradas)) == esperado


@pytest.mark.parametrize("entradas,esperado", CASOS_B)
def test_programa_b(entradas, esperado):
    r = compilar((EJEMPLOS / "programa_b.txt").read_text())
    assert r.exito
    assert _ultima(_correr_python(r.python, entradas)) == esperado
    if NODE:
        assert _ultima(_correr_js(r.javascript, entradas)) == esperado


def _mensajes(r, fase):
    return [(e.linea, e.mensaje) for e in r.errores if e.fase == fase]


def test_errores_lexicos():
    r = compilar((EJEMPLOS / "errores_lexicos.txt").read_text())
    assert not r.exito
    assert [f.estado for f in r.fases] == ["error", "omitida", "omitida", "omitida"]
    lineas = [l for l, _ in _mensajes(r, "LÉXICO")]
    assert lineas == [3, 4, 5, 5, 6]


def test_errores_sintacticos():
    r = compilar((EJEMPLOS / "errores_sintacticos.txt").read_text())
    assert [f.estado for f in r.fases][:2] == ["ok", "error"]
    errs = _mensajes(r, "SINTÁCTICO")
    assert [l for l, _ in errs] == [4, 7, 8, 9]
    assert "¿Quiso decir 'Escribir'?" in errs[1][1]


def test_errores_semanticos():
    r = compilar((EJEMPLOS / "errores_semanticos.txt").read_text())
    assert [f.estado for f in r.fases][:3] == ["ok", "ok", "error"]
    errs = _mensajes(r, "SEMÁNTICO")
    assert [l for l, _ in errs] == [4, 6, 10]
    assert "división entre cero" in errs[1][1]


@pytest.mark.parametrize("codigo,fragmento", [
    ("Escribir \"x\"\nFin", "debe comenzar con 'Inicio'"),
    ("Inicio\nEscribir \"x\"", "falta 'Fin'"),
    ("Inicio\nFinSi\nFin", "'FinSi' sin un 'Si'"),
    ("Inicio\nLeer a\nSi (a = 1) Entonces\nFinSi\nFin", "use '=='"),
    ("Inicio\nLeer a\nSi (a > 1)\nEscribir a\nFinSi\nFin", "'Entonces'"),
    ("Inicio\nEscribir\nFin", "se esperaba una cadena o una expresión"),
    ("Inicio\nx = \"hola\"\nFin", "no cadenas"),
    ("Inicio\nFin\nLeer a", "después de 'Fin'"),
])
def test_errores_sintacticos_varios(codigo, fragmento):
    r = compilar(codigo)
    assert any(fragmento in e.mensaje for e in r.errores), [str(e) for e in r.errores]


def test_variables_reasignadas_y_en_bloques():
    codigo = """Inicio
    Leer a
    total = a
    Si (a > 5) Entonces
        total = total * 2
        extra = 1
    Sino
        extra = 0
    FinSi
    Escribir total, " / ", extra
    Escribir -a + 1
    Fin"""
    r = compilar(codigo)
    assert r.exito, [str(e) for e in r.errores]
    assert "let total, extra;" in r.javascript
    assert "const a = await leer();" in r.javascript
    for entrada, esperado in [("7", "14 / 1"), ("2", "2 / 0")]:
        assert _correr_python(r.python, [entrada]).splitlines()[0] == esperado
        if NODE:
            assert _correr_js(r.javascript, [entrada]).splitlines()[0] == esperado


def test_renombra_palabras_reservadas_destino():
    r = compilar("Inicio\nLeer class\nprint = class + 1\nEscribir print\nFin")
    assert r.exito
    # 'class' y 'print' chocan con Python/JavaScript y se renombran
    assert "class_ = float(input())" in r.python
    assert "print_ = class_ + 1" in r.python
    assert "const class_ = await leer();" in r.javascript
    assert _correr_python(r.python, ["2"]).strip() == "3"
    if NODE:
        assert _correr_js(r.javascript, ["2"]).strip() == "3"


def test_bloque_vacio_genera_pass():
    r = compilar("Inicio\nLeer a\nSi (a > 1) Entonces\nFinSi\nFin")
    assert r.exito
    assert "pass" in r.python
    _correr_python(r.python, ["3"])
