"""Ejecución del código generado dentro de la propia interfaz.

* Python se ejecuta en un hilo aparte con `print` e `input` redirigidos a la
  consola de la aplicación (no requiere Python instalado: funciona también
  dentro del ejecutable).
* JavaScript se ejecuta con Node.js (si está instalado) mediante QProcess.
"""

import os
import queue
import re
import shutil
import tempfile
import threading
import traceback
from pathlib import Path

from PySide6.QtCore import QObject, QProcess, Signal

_DETENER = object()


class _Detenido(Exception):
    pass


def _linea_pseudo(mapa, linea_generada):
    if 1 <= linea_generada <= len(mapa):
        return mapa[linea_generada - 1]
    return 0


def _traducir_excepcion(e: BaseException) -> str:
    if isinstance(e, ZeroDivisionError):
        return "división entre cero"
    if isinstance(e, ValueError) and "could not convert string to float" in str(e):
        valor = str(e).split(":", 1)[-1].strip()
        return f"la entrada {valor} no es un número válido"
    if isinstance(e, OverflowError):
        return "el resultado es demasiado grande"
    return f"{type(e).__name__}: {e}"


class Ejecutor(QObject):
    salida = Signal(str, str)        # texto, tipo: out | err | info
    terminado = Signal(int)          # código de salida
    esperando_entrada = Signal()

    def ejecutando(self) -> bool:
        raise NotImplementedError

    def enviar(self, texto: str):
        raise NotImplementedError

    def detener(self):
        raise NotImplementedError


class EjecutorPython(Ejecutor):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._hilo = None
        self._cola = queue.Queue()

    def ejecutando(self):
        return self._hilo is not None and self._hilo.is_alive()

    def iniciar(self, codigo: str, mapa: list[int]):
        self._cola = queue.Queue()
        self._hilo = threading.Thread(target=self._correr, args=(codigo, mapa), daemon=True)
        self._hilo.start()

    def _print(self, *args, sep=" ", end="\n", file=None, flush=False):
        self.salida.emit(sep.join(str(a) for a in args) + end, "out")

    def _input(self, prompt=""):
        if prompt:
            self.salida.emit(str(prompt), "out")
        self.esperando_entrada.emit()
        valor = self._cola.get()
        if valor is _DETENER:
            raise _Detenido()
        return valor

    def _correr(self, codigo, mapa):
        entorno = {"__name__": "__main__", "print": self._print, "input": self._input}
        codigo_salida = 0
        try:
            exec(compile(codigo, "salida.py", "exec"), entorno)
        except _Detenido:
            self.salida.emit("\n*** Ejecución detenida por el usuario ***\n", "info")
            codigo_salida = -1
        except Exception as e:  # error en tiempo de ejecución del programa
            linea = 0
            for frame in traceback.extract_tb(e.__traceback__):
                if frame.filename == "salida.py":
                    linea = frame.lineno
            lp = _linea_pseudo(mapa, linea)
            donde = f" (línea {linea} de salida.py" + (f", línea {lp} del pseudocódigo)" if lp else ")")
            self.salida.emit(f"\nError en tiempo de ejecución{donde}: {_traducir_excepcion(e)}\n", "err")
            codigo_salida = 1
        self.terminado.emit(codigo_salida)

    def enviar(self, texto):
        self._cola.put(texto)

    def detener(self):
        if self.ejecutando():
            self._cola.put(_DETENER)


def buscar_node() -> str | None:
    encontrado = shutil.which("node") or shutil.which("nodejs")
    if encontrado:
        return encontrado
    candidatos = [
        r"C:\Program Files\nodejs\node.exe",
        r"C:\Program Files (x86)\nodejs\node.exe",
        "/usr/local/bin/node", "/opt/homebrew/bin/node", "/usr/bin/node",
        str(Path.home() / ".asdf/shims/node"),
    ]
    return next((c for c in candidatos if os.path.exists(c)), None)


class EjecutorJS(Ejecutor):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.proceso = None
        self._dir = tempfile.mkdtemp(prefix="pseudocompilador_")
        self._mapa = []

    def ejecutando(self):
        return self.proceso is not None and self.proceso.state() != QProcess.ProcessState.NotRunning

    def iniciar(self, codigo: str, mapa: list[int]) -> bool:
        node = buscar_node()
        if not node:
            self.salida.emit(
                "No se encontró Node.js. Instálalo desde https://nodejs.org para ejecutar\n"
                "el código JavaScript (el código Python sí puede ejecutarse sin instalar nada).\n",
                "err",
            )
            self.terminado.emit(1)
            return False
        self._mapa = mapa
        archivo = os.path.join(self._dir, "salida.js")
        with open(archivo, "w", encoding="utf-8") as f:
            f.write(codigo)
        self.proceso = QProcess(self)
        self.proceso.readyReadStandardOutput.connect(self._leer_stdout)
        self.proceso.readyReadStandardError.connect(self._leer_stderr)
        self.proceso.finished.connect(self._fin)
        self.proceso.errorOccurred.connect(self._fallo)
        self._stderr = ""
        self.proceso.start(node, [archivo])
        return True

    def _leer_stdout(self):
        datos = bytes(self.proceso.readAllStandardOutput()).decode("utf-8", "replace")
        self.salida.emit(datos, "out")

    def _leer_stderr(self):
        self._stderr += bytes(self.proceso.readAllStandardError()).decode("utf-8", "replace")

    def _fin(self, codigo, _estado):
        if self._stderr.strip():
            lineas = [int(n) for n in re.findall(r"salida\.js:(\d+)", self._stderr)]
            error = next(
                (l.strip() for l in self._stderr.splitlines() if re.match(r"\s*\w*Error\b", l)),
                self._stderr.strip().splitlines()[-1],
            )
            error = re.sub(r"^Error:\s*", "", error)  
            donde = ""
            if lineas:
                lg = next((l for l in lineas if _linea_pseudo(self._mapa, l)), lineas[0])
                lp = _linea_pseudo(self._mapa, lg)
                donde = f" (línea {lg} de salida.js" + (f", línea {lp} del pseudocódigo)" if lp else ")")
            self.salida.emit(f"\nError en tiempo de ejecución{donde}: {error}\n", "err")
        self.terminado.emit(codigo)

    def _fallo(self, error):
        if error == QProcess.ProcessError.FailedToStart:
            self.salida.emit("No se pudo iniciar Node.js.\n", "err")
            self.terminado.emit(1)

    def enviar(self, texto):
        if self.ejecutando():
            self.proceso.write((texto + "\n").encode("utf-8"))

    def detener(self):
        if self.ejecutando():
            self.proceso.kill()
            self.salida.emit("\n*** Ejecución detenida por el usuario ***\n", "info")
