# bridge/

## Para qué sirve

Orquestador foto-only: elige la foto activa, llama a `detection/*`, empuja
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

Con `ENABLE_EVIDENCE_CASCADE=true` (default en compose) las dependencias
seguras (`pedestrians`, `face_id`, `open_vocab`) solo se invocan si hay
evidencia. `faces` / `pose` / `signs` / scene / experimental siguen en
oleada 1 mientras se mide recall. `false` = gather único (rollback).

Esto reduce **invocaciones/CPU**, no RAM ni cantidad de procesos PaddleX
(lifecycle Docker = fase posterior).

`DEMO_MODE=1` emite detecciones sintéticas sin PaddleX.

## Entrada / salida

- **Entrada:** foto en `MEDIA_DIR/images` (vía adapter).
- **Salida:** POST JSON a `/ingest`, JPEG anotado a `/preview/frame`.

## Servicio / deps

| Item | Valor |
|------|--------|
| Compose | `bridge` (y `bridge-demo`) |
| Depende de | `adapter`, `paddlex*`, paquetes `detection/` |
| Env | `ADAPTER_*`, `PADDLEX_*`, `ENABLE_*`, `ENABLE_EVIDENCE_CASCADE`, `CASCADE_OBJECT_LOW_SCORE`, `MEDIA_*` |

## Archivos clave

- `main.py` — `run_loop`, `run_detections` (flujo completo).
- `cascade.py` — política pura de evidencia (testeable sin HTTP).
- `media.py` — resolución de ruta / idle.

## Qué no es

No abre RTSP ni video. No consolida tracks (eso es `adapter/`). No sirve UI.
No hace `docker pause`/`stop` de pipelines (fuera de alcance de esta fase).
