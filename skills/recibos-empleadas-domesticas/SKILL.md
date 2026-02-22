---
name: recibos-empleadas-domesticas
description: Liquidar sueldos mensuales de personal de casas particulares en Argentina (Irma y Mariza) usando Google Sheets (Referencia Matrix, Eventos, Pagos), preparar el flujo ARCA, validar resultados con gate de aprobación final, registrar pagos y preparar entrega por WhatsApp sin envío automático. Usar cuando se necesite cálculo mensual, chequeo normativo ARCA/CNTCP, simulación o ejecución controlada con aprobación previa.
---

# Recibos Empleadas Domésticas

Ejecutar este skill para orquestar el proceso mensual de liquidación con aprobación final.

## Flujo obligatorio

1. Ejecutar `scripts/run_monthly_payroll.py`.
2. Respetar gate de fecha: solo liquidar automáticamente cuando el día del mes sea `1`.
3. Usar `--mode dry-run` para pruebas o validación previa.
4. Mostrar primero validación corta (`OK/Revisar`) y luego detalle.
5. No enviar WhatsApp ni disparar transferencias sin aprobación explícita.

## Comandos principales

```bash
python3 scripts/run_monthly_payroll.py --mode dry-run --period 2026-02 --simulate-arca true --simulate-whatsapp true --ignore-day-gate
python3 scripts/run_monthly_payroll.py --mode real --period 2026-03 --simulate-arca false --simulate-whatsapp false
```

## Scripts disponibles

- `scripts/run_monthly_payroll.py`: orquestador end-to-end.
- `scripts/calc_payroll.py`: cálculo por persona a partir de datos normalizados.
- `scripts/check_rules_updates.py`: chequeo normativo ARCA/CNTCP con resumen textual.
- `scripts/validate_before_send.py`: checklist corto + detalle y estado global.
- `scripts/update_pagos_sheet.py`: payload para insertar fila en `Pagos`.
- `scripts/upload_receipts_drive.py`: payload de subida de PDFs por carpeta destino.
- `scripts/prepare_whatsapp_payload.py`: genera paquete de entrega WhatsApp (sin enviar).

## Referencias

- Esquema de columnas y mapeos: `references/sheets-schema.md`.
- Fuentes de control normativo: `references/legal-check-sources.md`.
- Plantilla de aprobación final: `references/approval-template.md`.

## Variables de entorno opcionales

- `SHEETS_WRITE_WEBHOOK_URL`: endpoint para aplicar escritura real en Google Sheets.
- `DRIVE_UPLOAD_WEBHOOK_URL`: endpoint para subida real de PDFs a Drive.
- `WHATSAPP_PREP_WEBHOOK_URL`: endpoint para preparar entregas en WhatsApp.

Sin estas variables, el skill opera en modo seguro: genera payloads y bloquea acciones externas.
