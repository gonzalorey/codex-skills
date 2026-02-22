# Proceso mensual

## Objetivo

Registrar de forma trazable el circuito mensual de facturación y deuda en USD con dos contactos.

## Pasos del orquestador

1. Validar fecha hábil en ventana de cierre (`últimos 3 días hábiles`).
2. Obtener cotización pactada de USD (`promedio de 4 puntas`).
3. Proponer montos por persona copiando último monto registrado.
4. Bloquear si hay cambio de monto sin confirmación explícita.
5. Escribir fila de deuda en Sheets por persona.
6. Detectar PDFs en carpeta local, subir a Drive y registrar en tab `Facturas`.
7. Crear movimiento en tracking account de YNAB por persona.
8. Emitir mensajes WhatsApp listos para copiar.
9. Emitir checklist final de pasos manuales.

## Pasos manuales (siempre)

- Emisión de factura en ARCA.
- Envío de factura por WhatsApp.
- Ajuste de categorías de budget en YNAB.

## Estrategia de degradación

Si falta credencial, dependencia o acceso de red, mantener ejecución en modo guiado:

- Entregar payloads para carga manual.
- No romper el flujo ni perder el resumen mensual.
- Registrar en artifact qué pasos quedaron bloqueados.
