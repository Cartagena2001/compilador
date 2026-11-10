import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from pseudocompiler import compilar
from pseudocompiler.__main__ import main as cli

EJEMPLOS = Path(__file__).resolve().parent.parent / "examples"
NODE = shutil.which("node")


def _ejecutar(comando, entradas):
    return subprocess.run(
        comando, input="\n".join(entradas) + "\n", capture_output=True, text=True,
        encoding="utf-8", timeout=10, env={**os.environ, "PYTHONUTF8": "1"},
    )


def _correr_python(codigo, entradas):
    r = _ejecutar([sys.executable, "-c", codigo], entradas)
    assert r.returncode == 0, r.stderr
    return r.stdout


def _correr_js(codigo, entradas):
    r = _ejecutar([NODE, "-e", codigo], entradas)
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


CASOS_C = [(["5"], ["El factorial es: 120", "La suma es: 30"]),
           (["1"], ["El factorial es: 1", "La suma es: 2"]),
           (["0"], ["El factorial es: 1", "La suma es: 0"])]
CASOS_D = [(["3", "4", "8", "6"], ["El promedio es: 6", "El número mayor es: 8"]),
           (["1", "7"], ["El promedio es: 7", "El número mayor es: 7"]),
           (["2", "1.5", "2.5"], ["El promedio es: 2", "El número mayor es: 2.5"])]
CASOS_E = [(["10", "6"], ["El área es: 60", "Clasificación: Grande"]),
           (["5", "4"], ["El área es: 20", "Clasificación: Pequeña"]),
           (["10", "5"], ["El área es: 50", "Clasificación: Pequeña"])]


@pytest.mark.parametrize("programa,entradas,esperado", [
    *(("programa_c.txt", *caso) for caso in CASOS_C),
    *(("programa_d.txt", *caso) for caso in CASOS_D),
    *(("programa_e.txt", *caso) for caso in CASOS_E),
])
def test_programas_c_d_e(programa, entradas, esperado):
    r = compilar((EJEMPLOS / programa).read_text(encoding="utf-8"))
    assert r.exito, [str(e) for e in r.errores]
    assert _correr_python(r.python, entradas).splitlines()[-2:] == esperado
    if NODE:
        assert _correr_js(r.javascript, entradas).splitlines()[-2:] == esperado


def test_programa_d_division_entre_cero_es_error_de_ejecucion():
    r = compilar((EJEMPLOS / "programa_d.txt").read_text(encoding="utf-8"))
    py = _ejecutar([sys.executable, "-c", r.python], ["0"])
    assert py.returncode != 0 and "ZeroDivisionError" in py.stderr
    if NODE:
        js = _ejecutar([NODE, "-e", r.javascript], ["0"])
        assert js.returncode != 0 and "división entre cero" in js.stderr


@pytest.mark.parametrize("entrada", ["h", "3.5.", "1\\", "", "0x10"])
def test_entrada_invalida_es_error_de_ejecucion(entrada):
    r = compilar((EJEMPLOS / "programa_a.txt").read_text(encoding="utf-8"))
    py = _ejecutar([sys.executable, "-c", r.python], [entrada, "1", "1"])
    assert py.returncode != 0 and "ValueError" in py.stderr
    if NODE:
        js = _ejecutar([NODE, "-e", r.javascript], [entrada, "1", "1"])
        assert js.returncode != 0 and "no es un número válido" in js.stderr


@pytest.mark.parametrize("entrada,esperado", [("3.", "El resultado es: 4"), (".5", "El resultado es: 0.5"),
                                              (" -2 ", "El resultado es: -2"), ("1e1", "El resultado es: 0")])
def test_formatos_de_numero_aceptados(entrada, esperado):
    r = compilar("Inicio\nLeer a\nb = a\nSi a > 5 Entonces\nb = a - 10\nFinSi\nSi a == 3 Entonces\nb = a + 1\nFinSi\nEscribir \"El resultado es: \", b\nFin")
    assert _ultima(_correr_python(r.python, [entrada])) == esperado
    if NODE:
        assert _ultima(_correr_js(r.javascript, [entrada])) == esperado


def test_programa_d_renombra_max_solo_en_python():
    r = compilar((EJEMPLOS / "programa_d.txt").read_text(encoding="utf-8"))
    assert "max_ = 0" in r.python
    assert "max = 0;" in r.javascript
    assert any("'max' es un nombre reservado en Python" in a.mensaje for a in r.advertencias)


def test_tabla_de_simbolos_del_programa_e():
    r = compilar((EJEMPLOS / "programa_e.txt").read_text(encoding="utf-8"))
    filas = {(s.ambito, s.nombre): (s.categoria, s.tipo) for s in r.tabla}
    assert filas[("Global", "CalcularArea")] == ("Función", "Función")
    assert filas[("CalcularArea", "area")] == ("Retorno", "Número")
    assert filas[("ClasificarArea", "area")] == ("Parámetro", "Número")
    assert filas[("ClasificarArea", "clasificacion")] == ("Retorno", "Texto")
    assert filas[("Global", "resultado")] == ("Variable", "Texto")
    assert ("CalcularArea", "base") in filas and ("Global", "base") in filas


def test_arbol_incluye_los_nodos_nuevos():
    r = compilar((EJEMPLOS / "programa_d.txt").read_text(encoding="utf-8"))
    arbol = "\n".join(r.arbol)
    for texto in ("Dimension numeros", "Para i", "Leer numeros[ ]", "numeros[ ]"):
        assert texto in arbol


@pytest.mark.parametrize("condicion,entradas,esperado", [
    ("a > 1 Y b > 1", ["2", "2"], "si"),
    ("a > 1 Y b > 1", ["2", "0"], "no"),
    ("a > 1 O b > 1", ["0", "2"], "si"),
    ("NO a > 1", ["0", "0"], "si"),
    ("(a > 1 O b > 1) Y a == 0", ["0", "2"], "si"),
    ("a > 1 O b > 1 Y a == 0", ["2", "0"], "si"),      # Y tiene más precedencia que O
    ("(a > 1 O b > 1) Y a == 0", ["2", "0"], "no"),
    ("(a + b) * 2 > 3", ["1", "1"], "si"),
    ("(a) > (b)", ["2", "1"], "si"),
])
def test_condiciones(condicion, entradas, esperado):
    r = compilar(
        f'Inicio\nLeer a\nLeer b\nSi {condicion} Entonces\nEscribir "si"\n'
        'Sino\nEscribir "no"\nFinSi\nFin'
    )
    assert r.exito, [str(e) for e in r.errores]
    assert _ultima(_correr_python(r.python, entradas)) == esperado
    if NODE:
        assert _ultima(_correr_js(r.javascript, entradas)) == esperado


@pytest.mark.parametrize("codigo,entradas,esperado", [
    # Mientras
    ('Inicio\nLeer n\ni = 0\nMientras i < n Hacer\ni = i + 1\nEscribir i\nFinMientras\nFin', ["2"], "1\n2\n"),
    # El límite de Para se evalúa una sola vez
    ('Inicio\nLeer n\nPara i = 1 Hasta n Hacer\nn = n - 1\nEscribir i\nFinPara\nFin', ["2"], "1\n2\n"),
    # Índice y tamaño reales se truncan
    ('Inicio\nLeer n\nDimension v[n]\nv[n] = 9\nEscribir v[n]\nFin', ["2.5"], "9\n"),
    # La variable de control puede reutilizarse tras asignarla
    ('Inicio\nPara i = 1 Hasta 1 Hacer\nEscribir i\nFinPara\ni = 5\nPara i = i Hasta 5 Hacer\nEscribir i\nFinPara\nFin', [], "1\n5\n"),
    # Recursión
    ('Inicio\nFuncion r = F(n)\nSi n > 1 Entonces\nr = n * F(n - 1)\nSino\nr = 1\nFinSi\nRetornar r\nFinFuncion\nEscribir F(4)\nFin', [], "24\n"),
    # Una función que lee datos (y otra que la llama) debe esperar la entrada en JS
    ('Inicio\nFuncion r = P(a)\nLeer r\nRetornar r\nFinFuncion\nFuncion s = D(a)\ns = P(a) * 2\nRetornar s\nFinFuncion\nEscribir D(0)\nFin', ["4"], "8\n"),
    # Parámetro reasignado y nombres reservados
    ('Inicio\nFuncion class = print(len)\nlen = len + 1\nclass = len\nRetornar class\nFinFuncion\nEscribir print(1)\nFin', [], "2\n"),
])
def test_ejecucion_equivalente(codigo, entradas, esperado):
    r = compilar(codigo)
    assert r.exito, [str(e) for e in r.errores]
    assert _correr_python(r.python, entradas) == esperado
    if NODE:
        assert _correr_js(r.javascript, entradas) == esperado


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
    ("Inicio\nFin\nLeer a", "después de 'Fin'"),
    ("Inicio\nPara i = 1 Hasta 3\nFinPara\nFin", "'Hacer'"),
    ("Inicio\nPara i = 1 Hacer\nFinPara\nFin", "'Hasta'"),
    ("Inicio\nPara i = 1 Hasta 3 Hacer\nFin", "no se cerró con 'FinPara'"),
    ("Inicio\nFinPara\nFin", "'FinPara' sin un 'Para'"),
    ("Inicio\nMientras a > 1\nFinMientras\nFin", "'Hacer'"),
    ("Inicio\nFinMientras\nFin", "'FinMientras' sin un 'Mientras'"),
    ("Inicio\nPara i = 1 Hasta 2 Hacer\nSi i > 1 Entonces\nFinPara\nFin", "no se cerró con 'FinSi'"),
    ("Inicio\nRetornar x\nFin", "'Retornar' fuera de una función"),
    ("Inicio\nFuncion r = F(a)\nr = a\nFinFuncion\nFin", "debe terminar con 'Retornar'"),
    ("Inicio\nFuncion r = F(a)\nr = a\nRetornar r\nFin", "no se cerró con 'FinFuncion'"),
    ("Inicio\nFuncion r = F(a)\nSi a > 1 Entonces\nRetornar r\nFinSi\nRetornar r\nFinFuncion\nFin", "última instrucción"),
    ("Inicio\nFuncion r = F(a)\nRetornar r\nEscribir 1\nFinFuncion\nFin", "'FinFuncion' después de 'Retornar'"),
    ("Inicio\nSi 1 > 0 Entonces\nFuncion r = F()\nRetornar r\nFinFuncion\nFinSi\nFin", "nivel principal"),
    ("Inicio\nF(1)\nFin", "dentro de una expresión"),
    ("Inicio\nDimension x\nFin", "'['"),
    ("Inicio\nx[1 = 2\nFin", "falta ']'"),
    ("Inicio\nEscribir F(1\nFin", "falta ')'"),
    ("Inicio\nSi a Entonces\nFinSi\nFin", "operador relacional"),
    ("Inicio\nSi a > 1 or a < 0 Entonces\nFinSi\nFin", "use 'Y' u 'O'"),
    ("Inicio\npara i = 1 Hasta 2 Hacer\nFinPara\nFin", "¿Quiso decir 'Para'?"),
])
def test_errores_sintacticos_varios(codigo, fragmento):
    r = compilar(codigo)
    assert any(fragmento in e.mensaje for e in r.errores), [str(e) for e in r.errores]


def test_un_error_no_genera_errores_en_cascada():
    r = compilar("Inicio\nFuncion r = F(a)\nRetornar\nFinFuncion\nPara i = 1 Hasta\nEscribir i\nFinPara\nFin")
    assert [e.linea for e in r.errores] == [3, 5]


def test_errores_de_ciclos_arreglos_y_funciones():
    r = compilar((EJEMPLOS / "errores_ciclos_arreglos_funciones.txt").read_text(encoding="utf-8"))
    assert [f.estado for f in r.fases] == ["ok", "ok", "error", "omitida"]
    assert [l for l, _ in _mensajes(r, "SEMÁNTICO")] == [8, 9, 10, 12, 13, 15, 19, 20]


@pytest.mark.parametrize("codigo,fragmento", [
    # Flujo: un ciclo puede no ejecutarse
    ("Inicio\nPara i = 1 Hasta 3 Hacer\nx = i\nFinPara\nEscribir x\nFin", "podría no tener valor"),
    ("Inicio\nb = 1\nMientras b > 2 Hacer\nx = 1\nFinMientras\nEscribir x\nFin", "podría no tener valor"),
    ("Inicio\nPara i = 1 Hasta 3 Hacer\nFinPara\nEscribir i\nFin", "solo tiene valor dentro del ciclo"),
    # Arreglos
    ("Inicio\nx[1] = 1\nFin", "no está declarado"),
    ("Inicio\nnum[1] = 2\nDimension num[3]\nFin", "antes de su 'Dimension'"),
    ("Inicio\nx = 1\nEscribir x[1]\nFin", "no es un arreglo"),
    ("Inicio\nDimension a[2]\nEscribir a\nFin", "debe usarse con un índice"),
    ("Inicio\nDimension a[2]\na = 1\nFin", "es un arreglo"),
    ("Inicio\nDimension a[2]\nLeer a\nFin", "es un arreglo"),
    ("Inicio\nDimension a[2]\nEscribir a[0]\nFin", "comienzan en 1"),
    ("Inicio\nDimension a[2]\nEscribir a[3]\nFin", "fuera del arreglo"),
    ("Inicio\nDimension a[0]\nFin", "al menos 1"),
    ("Inicio\nDimension a[2]\nDimension a[3]\nFin", "ya está declarado"),
    ("Inicio\nDimension a[2]\nEscribir a[\"x\"]\nFin", "debe ser un número"),
    # Funciones
    ("Inicio\nx = F(1)\nFin", "no está declarada"),
    ("Inicio\nx = F(1)\nFuncion r = F(a)\nr = a\nRetornar r\nFinFuncion\nFin", "antes de declararse"),
    ("Inicio\nFuncion r = F(a)\nr = a\nRetornar r\nFinFuncion\nx = F(1, 2)\nFin", "espera 1 argumento(s)"),
    ("Inicio\nx = 1\ny = x(1)\nFin", "no es una función"),
    ("Inicio\nFuncion r = F(a)\nr = a\nRetornar r\nFinFuncion\nx = F\nFin", "debe llamarse con paréntesis"),
    ("Inicio\nFuncion r = F(a)\nr = a\nRetornar a\nFinFuncion\nFin", "pero retorna 'a'"),
    ("Inicio\nFuncion r = F(a)\nRetornar r\nFinFuncion\nFin", "podría no tener valor"),
    ("Inicio\ng = 1\nFuncion r = F(a)\nr = g\nRetornar r\nFinFuncion\nFin", "no es visible"),
    ("Inicio\nFuncion r = F(a, a)\nr = a\nRetornar r\nFinFuncion\nFin", "repetido"),
    ("Inicio\nFuncion r = F(a)\nr = a\nRetornar r\nFinFuncion\nFuncion s = F(b)\ns = b\nRetornar s\nFinFuncion\nFin", "ya está declarado"),
    ("Inicio\nFuncion r = F(a)\nr = a\nRetornar r\nFinFuncion\nF = 1\nFin", "es una función"),
    # Tipos
    ("Inicio\nx = \"a\"\nz = x + 1\nFin", "debe ser un número"),
    ("Inicio\nz = \"a\" * 2\nFin", "debe ser un número"),
    ("Inicio\nz = -\"a\"\nFin", "debe ser un número"),
    ("Inicio\nx = \"a\"\nSi x > 1 Entonces\nFinSi\nFin", "no se puede comparar"),
    ("Inicio\nx = \"a\"\nx = 1\nFin", "no puede recibir"),
    ("Inicio\nx = \"a\"\nLeer x\nFin", "no puede recibir"),
    ("Inicio\nFuncion r = F(a)\nr = a * 2\nRetornar r\nFinFuncion\nx = F(\"t\")\nFin", "debe ser de tipo Número"),
    ("Inicio\nFuncion r = F(a)\nr = \"t\"\nRetornar r\nFinFuncion\nx = F(1) + 1\nFin", "debe ser un número"),
    ("Inicio\nPara i = \"a\" Hasta 3 Hacer\nFinPara\nFin", "debe ser un número"),
])
def test_errores_semanticos_varios(codigo, fragmento):
    r = compilar(codigo)
    assert r.fases[1].estado == "ok", [str(e) for e in r.errores]
    assert any(fragmento in e.mensaje for e in r.errores), [str(e) for e in r.errores]


def test_constantes_no_se_propagan_dentro_de_ciclos():
    r = compilar(
        "Inicio\ni = 0\nMientras i < 3 Hacer\ni = i + 1\nFinMientras\n"
        "x = 0\nPara j = 1 Hasta 2 Hacer\nx = x + 1\nFinPara\nEscribir 1 / x, i\nFin"
    )
    assert r.exito, [str(e) for e in r.errores]
    assert not any("siempre es" in a.mensaje for a in r.advertencias)


def test_aviso_variable_de_control_reasignada():
    r = compilar("Inicio\nPara i = 1 Hasta 3 Hacer\ni = i + 1\nFinPara\nFin")
    assert r.exito
    assert any("variable de control 'i'" in a.mensaje for a in r.advertencias)


def test_cli_genera_codigo_y_reporte(tmp_path, capsys):
    assert cli([str(EJEMPLOS / "programa_d.txt"), "-o", str(tmp_path)]) == 0
    reporte = (tmp_path / "programa_d_errores.txt").read_text(encoding="utf-8")
    assert reporte.startswith("Sin errores\n") and "se renombra a 'max_'" in reporte
    python = (tmp_path / "programa_d_python.txt").read_text(encoding="utf-8")
    assert _correr_python(python, ["1", "7"]).splitlines()[-1] == "El número mayor es: 7"
    javascript = (tmp_path / "programa_d_javascript.txt").read_text(encoding="utf-8")
    if NODE:
        assert _correr_js(javascript, ["1", "7"]).splitlines()[-1] == "El número mayor es: 7"


def test_cli_con_errores_no_genera_codigo(tmp_path, capsys):
    entrada = tmp_path / "malo.txt"
    entrada.write_text("Inicio\nFinPara\nFin", encoding="utf-8")
    (tmp_path / "malo_python.txt").write_text("codigo anterior", encoding="utf-8")
    assert cli([str(entrada)]) == 1
    reporte = (tmp_path / "malo_errores.txt").read_text(encoding="utf-8")
    assert "Error sintáctico en línea 2, columna 1" in reporte
    assert not (tmp_path / "malo_python.txt").exists()
    assert not (tmp_path / "malo_javascript.txt").exists()


def test_cli_admite_archivos_con_bom_y_ansi(tmp_path, capsys):
    bom = tmp_path / "bom.txt"
    bom.write_bytes('Inicio\nEscribir "ñ"\nFin'.encode("utf-8-sig"))
    ansi = tmp_path / "ansi.txt"
    ansi.write_bytes('Inicio\nEscribir "ñ"\nFin'.encode("cp1252"))
    assert cli([str(bom)]) == 0
    assert cli([str(ansi)]) == 0
    assert 'print("ñ")' in (tmp_path / "ansi_python.txt").read_text(encoding="utf-8")


def test_cli_entrada_inexistente(tmp_path, capsys):
    assert cli([str(tmp_path / "no_existe.txt")]) == 2
    assert "No se pudo leer" in capsys.readouterr().err


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
