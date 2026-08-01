# adapter/

## Para qué sirve

API FastAPI de Timonel: media (upload/select/clear), ingest de detecciones,
consolidación a `PerceptionEvent`, preview MJPEG y la UI en el mismo origen.

## Cómo funciona

1. Watcher / upload selecciona foto → bridge la consume.
2. `POST /ingest` acumula por `track_id` (TTL); con foto activa finaliza al instante.
3. `timonel.PerceptionEvent.consolidate_and_emit` → buffer `/events`.
4. UI: Vite/React build en imagen; `http://localhost:8000/` redirige a `/app/`.
5. Opcional: forward a JetLinks / rules-sink.

Al arranque el media-watch **no** auto-selecciona fotos ya presentes (idle hasta
upload o pick). Archivos **nuevos** en `imagenes_muestra/` sí se auto-seleccionan.

## Entrada / salida

- **Entrada:** detecciones JSON del bridge; multipart upload de fotos.
- **Salida:** `PerceptionEvent` en `/events`; preview JPEG/MJPEG.

## Servicio / deps

| Item | Valor |
|------|--------|
| Compose | `adapter` (`tm-adapter`) |
| Puerto | `8000` |
| Env | `STATIC_DIR=/app/adapter/ui`, `SPA_DIR`, `MEDIA_DIR`, `TRACK_TTL_*`, `JETLINKS_*`, `TIMONEL_ENV` |

## Archivos clave

- `app.py` — endpoints.
- `timonel.py` — contrato portable.
- `ui/spa-src/` — fuente de la UI; `ui/spa/` — build (imagen Docker).
- `ui/placeholder_preview.jpg` — preview vacío tras clear.

## Qué no es

No corre PaddleX. No decide reglas de alerta (ver `rules/`).
