"""Compilador por línea de comandos.

Termina con código 0 si compiló, 1 si el programa tiene errores y 2 si no se
pudo leer la entrada.
"""

import argparse
import sys
from pathlib import Path

from .compiler import compilar


def _leer_fuente(ruta: Path) -> str:
    datos = ruta.read_bytes()
    try:
        return datos.decode("utf-8-sig")
    except UnicodeDecodeError:  # archivos guardados como "ANSI" en Windows
        return datos.decode("cp1252", "replace")


def _reporte(resultado) -> str:
    lineas = [str(e) for e in resultado.errores] or ["Sin errores"]
    lineas += [str(a) for a in resultado.advertencias]
    return "\n".join(lineas) + "\n"


def main(argv=None) -> int:
    args = argparse.ArgumentParser(
        prog="python -m pseudocompiler", description="Traduce pseudocódigo a Python y JavaScript.",
    )
    args.add_argument("entrada", type=Path, help="archivo .txt con el pseudocódigo")
    args.add_argument("-o", "--salida", type=Path, help="carpeta de salida (por defecto, la de la entrada)")
    opciones = args.parse_args(argv)

    try:
        fuente = _leer_fuente(opciones.entrada)
    except OSError as e:
        print(f"No se pudo leer '{opciones.entrada}': {e.strerror}", file=sys.stderr)
        return 2

    carpeta = opciones.salida or opciones.entrada.parent
    carpeta.mkdir(parents=True, exist_ok=True)
    nombre = opciones.entrada.stem
    archivo_errores = carpeta / f"{nombre}_errores.txt"
    archivo_python = carpeta / f"{nombre}_python.txt"
    archivo_js = carpeta / f"{nombre}_javascript.txt"

    resultado = compilar(fuente)
    archivo_errores.write_text(_reporte(resultado), encoding="utf-8")
    print(f"Reporte de errores: {archivo_errores}")

    if not resultado.exito:
        # No se conserva código traducido de una compilación anterior
        archivo_python.unlink(missing_ok=True)
        archivo_js.unlink(missing_ok=True)
        print(f"{len(resultado.errores)} error(es): no se generó código.")
        return 1

    archivo_python.write_text(resultado.python, encoding="utf-8")
    archivo_js.write_text(resultado.javascript, encoding="utf-8")
    print(f"Código Python: {archivo_python}")
    print(f"Código JavaScript: {archivo_js}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
