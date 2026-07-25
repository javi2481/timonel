# detection/signs/

## Para qué sirve

Señales de tránsito vía `object_detection` (COCO filtrado o fine-tune propio).

## Cómo funciona

1. `ENABLE_SIGNS=true` + `paddlex-signs` (profile `extended`).
2. Filtra labels en `SIGNS_LABELS` (env CSV o default COCO señales).
3. Emite `entity_type:"sign"` con track `s-*`.

## Threshold

El detector COCO genérico casi no dispara señales al threshold default (0.5):
traffic light/stop sign quedan por debajo. `SIGNS_THRESHOLD=0.1` (default del
producto) las recupera; el ruido extra lo descarta el filtro `SIGN_LABELS`. Con
pesos fine-tuneados de señales conviene subirlo. Nota: el detector genérico
igual no ve todas las señales (limitación de modelo, no de umbral).

## Fine-tune

Apuntar `VI_PIPELINE` / pesos del servicio a un object_detection entrenado
con clases propias (speed_limit, yield, …) y actualizar `SIGNS_LABELS`.

## Servicio / deps

| Item | Valor |
|------|--------|
| Compose | `paddlex-signs` `:8088` |
| Env | `ENABLE_SIGNS`, `PADDLEX_SIGNS_URL`, `SIGNS_LABELS`, `SIGNS_THRESHOLD` |

## Qué no es

No reemplaza `objects/` COCO general (puede solaparse con traffic light/stop sign).
