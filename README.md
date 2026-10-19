# PseudoCompilador 95

Compilador de pseudocódigo en español a **Python** y **JavaScript**, con interfaz
gráfica estilo escritorio de los 90. Proyecto de Autómatas y Compiladores (AYC941).

![fases](https://img.shields.io/badge/fases-léxico%20·%20sintáctico%20·%20semántico%20·%20síntesis-008080)

## Uso

| Acción | Atajo |
|---|---|
| Compilar | `F5` |
| Compilar y ejecutar | `F6` |
| Detener ejecución | `Shift+F6` |
| Gramática del lenguaje | `F1` |

- **Izquierda:** editor de pseudocódigo (con números de línea y marcas de error).
- **Derecha:** código generado (elija *Python* o *JavaScript* en "Compilar a") y la
  consola donde se ejecuta el programa. Los valores para `Leer` se escriben en
  la caja *Entrada* y se envían con Enter.
- **Abajo:** el proceso de compilación fase por fase, la lista de errores, la
  tabla de tokens, el árbol sintáctico y la tabla de símbolos. Al hacer clic en
  un error, el editor salta a esa línea.

Python se ejecuta dentro de la propia aplicación. Para ejecutar JavaScript se
necesita [Node.js](https://nodejs.org) instalado.

## Lenguaje

```
Inicio
    Escribir "Ingrese su nota final:"
    Leer nota
    Si (nota >= 6) Y (nota <= 10) Entonces
        Escribir "Aprobado con ", nota
    Sino
        Escribir "Reprobado"
    FinSi
Fin
```

Sigue la gramática EBNF de la Fase 1 (`pseudocompiler/parser.py`). Además se
admiten comentarios `//` y el menos unario (`x = -5`).

## Errores que detecta

- **Léxicos:** caracteres no reconocidos, cadenas sin cerrar, números mal
  formados (`3.4.5`), identificadores con tildes o que empiezan con dígito.
- **Sintácticos:** falta de `Inicio`/`Fin`/`Entonces`/`FinSi`, comparaciones sin
  paréntesis, `=` en lugar de `==`, paréntesis sin cerrar, `Sino`/`FinSi` sin
  `Si`, palabras reservadas mal escritas (`escribir` → ¿`Escribir`?).
- **Semánticos:** variables no definidas o usadas antes de `Leer`/asignarse,
  variables que solo se asignan en una rama del `Si`, división entre cero
  (con propagación de constantes), y avisos de condiciones siempre
  verdaderas/falsas, variables sin uso y nombres reservados en Python/JS.

Cada error indica la fase, la línea y la columna.

## Desarrollo

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python main.py           # abrir la interfaz
.venv/bin/python -m pytest tests   # pruebas (incluye los casos del PDF)
.venv/bin/python build.py          # generar el ejecutable en dist/
```

En Windows use `.venv\Scripts\python` en lugar de `.venv/bin/python`.
PyInstaller no compila de forma cruzada: el `.exe` de Windows debe generarse
en Windows con `python build.py`.

## Estructura

```
pseudocompiler/   núcleo del compilador
  lexer.py        fase 1: análisis léxico (tokens)
  parser.py       fase 2: análisis sintáctico (AST) con recuperación de errores
  semantic.py     fase 3: análisis semántico + tabla de símbolos
  codegen.py      fase 4: generación de Python y JavaScript
  compiler.py     orquesta las fases
gui/              interfaz PySide6 (tema retro, editor, ejecución)
examples/         Programa A, Programa B y ejemplos con errores
tests/            pruebas automáticas
```

Fuentes VT323 y Press Start 2P bajo SIL Open Font License (`assets/fonts`).
