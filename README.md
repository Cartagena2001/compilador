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
    Funcion clasificacion = Clasificar(nota)
        Si nota >= 6 Entonces
            clasificacion = "Aprobado"
        Sino
            clasificacion = "Reprobado"
        FinSi
        Retornar clasificacion
    FinFuncion

    Leer n
    Dimension notas[n]
    Para i = 1 Hasta n Hacer
        Leer notas[i]
        Escribir "Nota ", i, ": ", Clasificar(notas[i])
    FinPara
Fin
```

Además se admiten comentarios `//` y el menos unario (`x = -5`).

### Gramática (EBNF)

Sustituye a la de la Fase 1. También está en `pseudocompiler/parser.py`.

```
programa      = "Inicio", { funcion | instruccion }, "Fin" ;
funcion       = "Funcion", ID, "=", ID, "(", [ ID, { ",", ID } ], ")",
                { instruccion }, "Retornar", ID, "FinFuncion" ;
instruccion   = leer | escribir | asignacion | si | para | mientras | dimension ;
leer          = "Leer", destino ;
escribir      = "Escribir", expresion, { ",", expresion } ;
dimension     = "Dimension", ID, "[", expresion, "]" ;
asignacion    = destino, "=", expresion ;
destino       = ID | ID, "[", expresion, "]" ;
si            = "Si", condicion, "Entonces", { instruccion },
                [ "Sino", { instruccion } ], "FinSi" ;
para          = "Para", ID, "=", expresion, "Hasta", expresion, "Hacer",
                { instruccion }, "FinPara" ;
mientras      = "Mientras", condicion, "Hacer", { instruccion }, "FinMientras" ;
condicion     = conj, { "O", conj } ;
conj          = neg, { "Y", neg } ;
neg           = [ "NO" ], comparacion ;
comparacion   = expresion, OP_REL, expresion | "(", condicion, ")" ;
expresion     = termino, { ("+" | "-"), termino } ;
termino       = factor, { ("*" | "/"), factor } ;
factor        = NUMERO | CADENA | llamada | ID | ID, "[", expresion, "]"
              | "(", expresion, ")" | "-", factor ;
llamada       = ID, "(", [ expresion, { ",", expresion } ], ")" ;
```

Precedencia (de mayor a menor): paréntesis, `-` unario, `* /`, `+ -`,
relacionales, `NO`, `Y`, `O`. Un `(` al inicio de una comparación puede abrir una
expresión o una condición; el parser prueba lo primero y, si no resulta, retrocede.

### Decisiones de diseño

- **Arreglos base 1:** `Dimension v[n]` reserva `n + 1` elementos y no usa el
  índice 0, así `v[i]` se traduce a `v[i]` sin restar 1.
- **Números reales:** `Leer` produce reales, por lo que tamaños, índices y límites
  de `Para` se truncan a entero (`int()` / `Math.trunc()`).
- **Para:** el límite se evalúa una vez, y la variable de control solo tiene valor
  dentro del ciclo; usarla después sin reasignarla es un error semántico.
- **Ámbitos:** cada función tiene su propio ámbito con sus parámetros, su variable
  de retorno y sus variables locales. No ve las variables globales.
- **Tipos:** `Número`, `Texto` y `Arreglo`. Una variable conserva su tipo, y texto y
  número no se mezclan en aritmética ni en comparaciones.
- **División entre cero:** si el divisor es constante, es un error semántico. Si
  depende de datos leídos, es un error de ejecución en ambos lenguajes
  (`ZeroDivisionError` en Python y `Error: división entre cero` en JavaScript).

### Limitaciones conocidas

- `Retornar` solo puede ser la última instrucción de una función, y los arreglos
  no pueden pasarse como argumento.
- El rango de un índice solo se verifica cuando es constante. Con índices
  calculados, un acceso fuera de rango da `IndexError` en Python y `undefined` en
  JavaScript; un índice negativo en Python cuenta desde el final del arreglo.
- Un tamaño negativo leído en ejecución da un arreglo vacío en Python y `RangeError`
  en JavaScript.
- Los enteros grandes tienen precisión exacta en Python y de 64 bits en
  JavaScript: por ejemplo, el factorial de 22 ya se muestra distinto.

## Errores que detecta

- **Léxicos:** caracteres no reconocidos, cadenas sin cerrar, números mal
  formados (`3.4.5`), identificadores con tildes o que empiezan con dígito.
- **Sintácticos:** falta de `Inicio`/`Fin`/`Entonces`/`Hasta`/`Hacer`, bloques sin
  cerrar o cierres sobrantes (`FinSi`, `FinPara`, `FinMientras`, `FinFuncion`),
  `=` en lugar de `==`, paréntesis o corchetes sin cerrar, `Retornar` fuera de una
  función o antes del final, funciones anidadas, palabras reservadas mal escritas
  (`escribir` → ¿`Escribir`?).
- **Semánticos:** variables no definidas o usadas antes de `Leer`/asignarse,
  variables asignadas solo en un bloque que podría no ejecutarse, arreglos sin
  `Dimension`, sin índice o con índice constante fuera de rango, índice aplicado a algo que no es
  arreglo, funciones no declaradas o con número incorrecto de argumentos, retorno
  de otra variable, mezcla de texto y número, división entre cero (con propagación
  de constantes). También avisa de condiciones siempre verdaderas o falsas, símbolos sin
  uso, reasignación de la variable de control y nombres reservados en Python/JS.

Cada error indica la fase, la línea y la columna.

## Línea de comandos

```bash
python -m pseudocompiler examples/programa_c.txt -o salida
```

Escribe en la carpeta indicada (por defecto, la del archivo de entrada)
`programa_c_errores.txt` y, si no hay errores, `programa_c_python.txt` y
`programa_c_javascript.txt`. Termina con código 0 si compiló, 1 si hay errores
en el programa y 2 si no pudo leer la entrada.

## Desarrollo

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python main.py           # abrir la interfaz
.venv/bin/python -m pytest tests   # pruebas (incluye los 15 casos de los programas A-E)
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
  errors.py       gestor de errores de todas las fases
  __main__.py     compilación por línea de comandos
gui/              interfaz PySide6 (tema retro, editor, ejecución)
examples/         Programas A a E y ejemplos con errores
tests/            pruebas automáticas
```

Fuentes VT323 y Press Start 2P bajo SIL Open Font License (`assets/fonts`).
