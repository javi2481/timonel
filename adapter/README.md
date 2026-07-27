# adapter/

## Para qué sirve

API FastAPI: media (upload/select/clear), ingest de detecciones, consolidación
a `PerceptionEvent`, preview MJPEG y la SPA en `/app/`.

## Cómo funciona

1. Watcher / upload selecciona foto → bridge la consume.
2. `POST /ingest` acumula por `track_id` (TTL); con foto activa finaliza al instante.
3. `epp_core.PerceptionEvent.consolidate_and_emit` → buffer `/events`.
4. UI: SPA Vite en `/app/` (build en imagen); `/` redirige a `/app/`.
5. Opcional: forward a JetLinks / rules-sink.

## Entrada / salida

- **Entrada:** detecciones JSON del bridge; multipart upload de fotos.
- **Salida:** `PerceptionEvent` en `/events`; preview JPEG/MJPEG.

## Servicio / deps

| Item | Valor |
|------|--------|
| Compose | `adapter` |
| Puerto | `8000` |
| Env | `STATIC_DIR=/app/adapter/ui`, `SPA_DIR`, `MEDIA_DIR`, `TRACK_TTL_*`, `JETLINKS_*` |

## Archivos clave

- `app.py` — endpoints.
- `epp_core.py` — contrato portable.
- `ui/spa-src/` — fuente de la SPA; `ui/spa/` — build (imagen Docker).
- `ui/placeholder_preview.jpg` — preview vacío tras clear.

## Qué no es

No corre PaddleX. No decide reglas de alerta (ver `rules/`).
