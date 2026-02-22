---
name: facturacion-monotributo-amigos
description: Orquestar el cierre mensual de facturación a contactos recurrentes (Santi Favelukes y Santi Olivieri) con cálculo de cotización USD desde dolarhoy, registro de deuda ARS/USD en Google Sheets, preparación y registro de facturas, actualización de tracking accounts en YNAB y salida de mensajes para WhatsApp. Usar cuando se ejecute el proceso de fin de mes con compuerta de últimos 3 días hábiles y control de cambios de monto.
---

# Facturacion Monotributo Amigos

Ejecutar este skill para cerrar mensualmente el circuito de facturación y deuda en dólares.

## Flujo obligatorio

1. Ejecutar `scripts/run_monthly_close.py --mode monthly-close`.
2. Respetar gate de fecha: correr automáticamente solo en los últimos 3 días hábiles del mes (zona configurada).
3. Usar `--dry-run` para simulación previa.
4. Frenar si se detecta cambio de monto vs histórico y no se pasa `--confirm-amount-change`.
5. Mantener ARCA y envío por WhatsApp como pasos manuales guiados.

## Comando principal

```bash
python3 scripts/run_monthly_close.py --mode monthly-close --dry-run
```

## Comando con carpeta de facturas

```bash
python3 scripts/run_monthly_close.py --mode monthly-close --invoice-dir ~/Downloads/facturas-mes
```

## Scripts disponibles

- `scripts/run_monthly_close.py`: orquestador end-to-end.
- `scripts/fetch_fx.py`: cálculo de cotización USD pactada.
- `scripts/google_sync.py`: helpers para Sheets/Drive (API real si hay dependencias o payloads si no).
- `scripts/ynab_sync.py`: alta de movimientos en tracking accounts de YNAB.
- `scripts/close_lib.py`: utilidades compartidas (gates, redondeo, helpers de período).

## Configuración

Editar `config.yaml` en la raíz del skill:

- `timezone`: `America/Argentina/Buenos_Aires`
- `business_day_window`: `3`
- `people[]`: datos por contacto, sheet y cuenta YNAB
- `google.*`, `sheets.*`, `drive.*`, `ynab.*`

## Referencias

- Proceso operativo: `references/process.md`
- Plantillas de mensaje: `assets/message_templates.md`

## Variables de entorno opcionales

- `DOLARHOY_HTML_PATH`: ruta local para parsear cotización sin red.
- `SHEETS_WRITE_WEBHOOK_URL`: endpoint alternativo para escritura en Sheets.
- `DRIVE_UPLOAD_WEBHOOK_URL`: endpoint alternativo para subida a Drive.

Si faltan credenciales o dependencias externas, el skill degrada a modo guiado y entrega payloads/listas de acción.
