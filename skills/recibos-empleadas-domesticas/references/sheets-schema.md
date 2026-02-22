# Sheets schema

## Mariza

- Sheet ID: `1nsz2T2qn1LLpFDKfAXWZwbn8Obvch4-o0-77NAjGLSE`
- Tabs:
  - `Referencia Matrix`:
    - `Período`, `Horas diarias`, `Días por semana`, `Semanas al mes`, `Horas totales`, `Básico hora`, `Salario básico`, `Antiguedad`, `Viáticos por día`, `Viáticos totales`, `Ausencia`, `% vs periodo anterior`, `Descripción`
  - `Eventos`:
    - `Fecha`, `Tipo de evento`, `Monto adicional/descuento`, `Descripción`
  - `Pagos`:
    - `Fecha`, `Mes`, `Año`, `Básico`, `Antiguedad`, `Viáticos`, `Eventos`, `Subtotal`, `Otros`, `Total`, `Notas`, `Recibo`

## Irma

- Sheet ID: `1rLfGzbbRH9WnYIMmK1Vcf34ecCOzHVX_I6uvSh35erk`
- Tabs:
  - `Referencia Matrix`:
    - `Período`, `Días hábiles`, `Horas/día`, `Básico/hora`, `Viáticos/día`, `Antiguedad`, `% vs periodo anterior`
  - `Eventos`:
    - `Fecha`, `Tipo de evento`, `Monto adicional/descuento`, `Descripción`
  - `Pagos`:
    - `Fecha`, `Mes`, `Año`, `Días hábiles`, `Ausencias`, `Total días trabajados`, `Horas trabajadas`, `Básico`, `Antiguedad`, `Viáticos`, `Subtotal`, `Otros`, `Total`, `Notas`, `Recibo`

## Regla clave

- `Referencia Matrix` define solo base/periódicos.
- `Eventos` define variables del mes (ausencias, extras, préstamos, vacaciones, ajustes).
- No descontar ausencias automáticamente desde `Referencia Matrix`.
