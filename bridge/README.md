# bridge/

## Para qué sirve

Orquestador solo-foto: elige la foto activa, llama a `detection/*`, empuja
preview e ingest al adapter.

## Cómo funciona

```text
idle ←→ poll /media/current
         ↓ foto
      imread → oleada 1 (vehicles∥objects∥faces?∥scene?∥…)
            → evidencia (person / face / objects state)
            → oleada 2 (pedestrians?∥face_id?∥open_vocab?)
            → merge → plates? → overlay → /ingest + /preview/frame
         ↓ clear
       idle
```

Con `ENABLE_EVIDENCE_CASCADE=true` (default en compose):
- `pedestrians` / `face_id` solo tras evidencia (person / face) en oleada 2.
- `open_vocab` corre en **oleada 1** (cola larga, en paralelo con objects).
  NMS posterior dedupea vehicle/object/open_vocab (preferencia
  vehicle > object > ov).
- `faces` / `pose` / `signs` / scene siguen en oleada 1.
`false` = gather único.

Esto reduce **invocaciones/CPU** en ped/face_id. Con
`ENABLE_CONTAINER_LIFECYCLE=true` (solo vía override avanzado
`compose.ondemand.yml`) el bridge hace `docker start`/`stop` de capas
extended idle; **no** es el default del producto (`full_up` deja todo up).
Las capas objects/faces/pose/ocr/vehicles no se stoppean por lifecycle.
`open_vocab` y `signs` comparten contenedor. Requiere montar el Docker sock
en el servicio bridge.

`DEMO_MODE=1` emite detecciones sintéticas sin PaddleX.

## Entrada / salida

- **Entrada:** foto en `MEDIA_DIR/images` (vía adapter).
- **Salida:** POST JSON a `/ingest`, JPEG anotado a `/preview/frame`.

## Servicio / deps

| Item | Valor |
|------|--------|
| Compose | `bridge` (y `bridge-demo`) |
| Depende de | `adapter`, `paddlex*`, paquetes `detection/` |
| Env | `ADAPTER_*`, `PADDLEX_*`, `ENABLE_*`, `ENABLE_EVIDENCE_CASCADE`, `CASCADE_OBJECT_LOW_SCORE`, `ENABLE_CONTAINER_LIFECYCLE`, `CONTAINER_IDLE_PAUSE_S`, `MEDIA_*` |

## Archivos clave

- `main.py` — `run_loop`, `run_detections` (flujo completo).
- `cascade.py` — política pura de evidencia (testeable sin HTTP).
- `lifecycle.py` — start/stop Docker de capas extended (opt-in ondemand).
- `media.py` — resolución de ruta / idle.

## Qué no es

No abre RTSP ni video. No consolida tracks (eso es `adapter/`). No sirve UI.
Lifecycle stop/start es override avanzado (`compose.ondemand.yml`), no el
camino `full_up`.
