# Vision Intelligence — Producto B (Sprint 1)

Orquestar, no inventar. Pipeline Docker-first **foto-only**:
**Foto → detection/* → adapter/epp_core → SPA (/app/)**.

## Mapa carpeta ↔ capacidad ↔ servicio

| Carpeta | Capacidad | Servicio Compose |
|---------|-----------|------------------|
| [detection/vehicles/](detection/vehicles/) | Tipo/color de vehículo | `paddlex` `:8080` |
| [detection/objects/](detection/objects/) | COCO (incluye **person**) | `paddlex-objects` `:8082` |
| [detection/plates/](detection/plates/) | OCR patente (opcional) | `paddlex-ocr` `:8081` |
| [detection/faces/](detection/faces/) | Rostros (opcional) | `paddlex-faces` `:8083` |
| [detection/pedestrians/](detection/pedestrians/) | Attrs persona (opcional) | `paddlex-pedestrians` `:8084` |
| [detection/scene/](detection/scene/) | Escena (opcional) | `paddlex-scene` `:8085` |
| [detection/pose/](detection/pose/) | Keypoints (opcional) | `paddlex-pose` `:8086` |
| [detection/text/](detection/text/) | OCR carteles (opcional) | reusa `paddlex-ocr` `:8081` |
| [detection/open_vocab/](detection/open_vocab/) | Cola larga (prompt) | `paddlex-open-vocab` `:8093` |
| [detection/signs/](detection/signs/) | Señales (vía OV) | mismo `:8093` (`SIGNS_BACKEND=ov`) |
| [detection/face_id/](detection/face_id/) … [anomaly/](detection/anomaly/) | Opt-in | profile `experimental` `:8087`–`:8092` |
| [detection/signs/](detection/signs/) legacy COCO | Rollback | `paddlex-signs` `:8088` (`legacy-signs`) |
| [detection/common/](detection/common/) | Tracker, geometry, preview | — |
| [bridge/](bridge/) | Orquestador foto → ingest/preview | `bridge` |
| [adapter/](adapter/) | Media, consolidación, API | `adapter` `:8000` |
| [adapter/ui/](adapter/ui/) | Panel SPA (`/app/`) | (build Vite del adapter) |
| [rules/](rules/) | Alertas headless | `rules-sink` (profile `rules`) |
| [infra/](infra/) | Imagen PaddleX compartida | build de `paddlex*` |
| [tests/](tests/) | Unit tests | — |

Cada carpeta tiene su propio `README.md` (para qué / cómo / I-O / deps).

> **Personas:** el bbox `person` es clase COCO en [detection/objects/](detection/objects/).
> Los atributos van en [detection/pedestrians/](detection/pedestrians/) (no hay `persons/`).

## Arquitectura

```text
[Upload / imagenes_muestra] --> [adapter] <--poll-- [bridge]
                                                      |
         +--------+--------+--------+--------+--------+--------+
         v        v        v        v        v        v        v
     vehicles  objects   ocr?    faces   scene   pose?   open-vocab
      :8080     :8082   :8081    :8083   :8085   :8086     :8093
         |        |        |        |      |       |         |
         +--------+--- merge + NMS (vehicle>object>ov) +------+
                                          |
                                   POST /ingest + /preview/frame
                                          v
                              PerceptionEvent → SPA (/events, /app/)
```

## Arranque rápido

```bash
cp .env.example .env
docker compose up --build
```

### RAM del host

Host de referencia: **PC-Javier** — 32 GB RAM, Ryzen 5 8500G (6c/12t), sin GPU
NVIDIA. `docker compose up` levanta la **base hot** (~8 paddlex: vehicles, ocr,
objects, faces, pedestrians, scene, pose, open-vocab) + adapter + bridge, con
techo `mem_limit ~2g` por contenedor. Experimentales solo con
`--profile experimental`. El cuello esperado es CPU, no RAM.

| Recurso | URL |
|---------|-----|
| Dashboard (SPA) | http://localhost:8000/app/ |
| Events | http://localhost:8000/events |
| Health | http://localhost:8000/health |
| PaddleX vehicles | http://localhost:8080 |
| PaddleX OCR | http://localhost:8081 |
| PaddleX objects | http://localhost:8082 |
| PaddleX faces | http://localhost:8083 |
| PaddleX pedestrians | http://localhost:8084 |
| PaddleX scene | http://localhost:8085 |
| PaddleX pose | http://localhost:8086 |
| PaddleX open-vocab / signs (ov) | http://localhost:8093 |

## Flujo foto

1. Subí JPG desde el panel o copiá a `imagenes_muestra/`.
2. Adapter auto-selecciona; bridge polea `/media/current` y detecta en background.
3. SPA: capacidades disponibles; toggles solo muestran/ocultan boxes (opt-in; verde=hit, rojo=miss).
4. **Limpiar foto** → bridge idle.

## Perfiles Compose

| Comando | Efecto |
|---------|--------|
| `docker compose up --build` | base hot (~8 paddlex) + adapter + bridge |
| `docker compose --profile experimental up --build` | + face-id, scene-cls, instances, small-objects, anomaly |
| `docker compose --profile legacy-signs up` | + paddlex-signs `:8088` (rollback COCO) |
| `docker compose --profile demo up --build` | bridge sintético |
| `docker compose --profile rules up --build` | + JetLinks + rules-sink |
| `docker compose --profile gpu up --build` | PaddleX GPU (requiere NVIDIA; no aplica en PC-Javier) |

## Variables útiles

Ver [`.env.example`](.env.example). Destacadas: `ENABLE_PLATE_OCR`,
`ENABLE_FACE_DETECTION`, `ENABLE_PEDESTRIAN_ATTRS`, `ENABLE_SCENE_SEG`,
`ENABLE_POSE`, `ENABLE_SCENE_OCR`, `ENABLE_OPEN_VOCAB`, `ENABLE_SIGNS`,
`OPEN_VOCAB_PROMPT`, flags experimentales (`ENABLE_FACE_ID` …), `VI_USE_HPIP`,
`MEDIA_DIR`, `PADDLEX_*`, `BRIDGE_MAX_WIDTH`, `VI_ENV`.

## Tests

```bash
PYTHONPATH=. python3 tests/test_bridge_helpers.py
PYTHONPATH=. python3 tests/test_epp_core.py
PYTHONPATH=. python3 tests/test_adapter_media.py
PYTHONPATH=. python3 tests/test_eval_match.py
```

Detalle en [tests/README.md](tests/README.md).

## Accuracy harness (local gate ≠ CI)

Host-side golden fixtures → HTTP predict → scored report + `failures/` + baseline diff.
**Not a PR/CI blocker** — run on a developer machine with the stack already up.

```bash
python -m pip install -r scripts/requirements-eval.txt
PYTHONPATH=. python scripts/download_paddlex_eval.py --packs core   # or --packs all
PYTHONPATH=. python scripts/eval_paddlex_fixtures.py --packs core   # --pipelines suite1,suite2
```

`--packs core` is the local accuracy gate. Extended + Experimental are opt-in via
`--packs all` (see [imagenes_muestra/README.md](imagenes_muestra/README.md)).
Latency/HPIP remains [`scripts/benchmark_paddlex.py`](scripts/benchmark_paddlex.py)
(accuracy ≠ latency).

## Contrato epp-core

Portable en [adapter/epp_core.py](adapter/epp_core.py): entra dict de detección,
sale `PerceptionEvent` (votación patente/color/`class_name`/scene). Sin reglas de negocio.

## Troubleshooting

```bash
docker compose logs -f bridge
docker compose logs -f adapter
curl http://localhost:8000/media/current
```

Sin foto activa el bridge queda idle (esperado).
