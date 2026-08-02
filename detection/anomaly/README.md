# detection/anomaly/

## Para qué sirve

Anomaly detection (más industrial que vial).

## Nota de dominio

En el stack default el servicio está up y `ENABLE_ANOMALY=true` vía Compose.
En fotos de calle típicas puede aportar poco; el dominio natural es inspección
industrial.

## Servicio

`paddlex-anomaly` `:8092` — Env: `ENABLE_ANOMALY`, `PADDLEX_ANOMALY_URL`.
