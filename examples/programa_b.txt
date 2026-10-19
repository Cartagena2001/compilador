Inicio
    Escribir "Ingrese su nota final:"
    Leer nota
    Escribir "Ingrese su porcentaje de asistencia:"
    Leer asistencia
    Si (nota >= 6) Y (asistencia >= 75) Entonces
        Escribir "Aprobado"
    Sino
        Si (nota >= 6) Y (asistencia < 75) Entonces
            Escribir "Reprobado por asistencia"
        Sino
            Escribir "Reprobado por nota"
        FinSi
    FinSi
Fin
