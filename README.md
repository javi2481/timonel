# Timonel

Orquestar, no inventar. Pipeline Docker-first **foto-only**:
**Foto → detection/* → adapter/timonel → SPA (/app/)**.

## Activo por default (`docker compose up`)

| Capacidad | Qué detecta | Servicio |
|-----------|-------------|----------|
| [vehicles](detection/vehicles/) | Tipo/color de vehículo + bbox | `paddlex` `:8080` |
| [objects](detection/objects/) | COCO (~80 clases, incl. **person**) | `paddlex-objects` `:8082` |
| [faces](detection/faces/) | Rostros (bbox + score, sin identidad) | `paddlex-faces` `:8083` |
| [pose](detection/pose/) | Keypoints / esqueleto humano | `paddlex-pose` `:8086` |
| [plates](detection/plates/) | Patente (OCR en crops de vehículos) | `paddlex-ocr` `:8081` |
| [text](detection/text/) | Texto en escena / carteles (OCR frame completo) | reusa `paddlex-ocr` `:8081` |

Siempre: [adapter](adapter/) `:8000` (API + SPA) y [bridge](bridge/) (orquestador).

> **Personas:** el bbox `person` sale de [objects](detection/objects/) (COCO).
> Atributos de persona están en [pedestrians](detection/pedestrians/) (opt-in, profile `extended`).

## Desactivado (código intacto — se puede activar)

Código en `detection/` se conserva. Hay que levantar el profile Compose y poner el flag en `true` (ver [`.env.example`](.env.example)).

### Profile `extended`

| Capacidad | Qué detecta al activar | Cómo |
|-----------|------------------------|------|
| [pedestrians](detection/pedestrians/) | Atributos de persona (género, edad, ropa…) sobre `person` | `--profile extended` + `ENABLE_PEDESTRIAN_ATTRS=true` |
| [scene](detection/scene/) | Seg. semántica (calle, vereda, carriles, cruce) | `--profile extended` + `ENABLE_SCENE_SEG=true` |
| [open_vocab](detection/open_vocab/) | Clases por prompt fuera de COCO (casco, chaleco, cono…) | `--profile extended` + `ENABLE_OPEN_VOCAB=true` |
| [signs](detection/signs/) | Señales de tránsito (bbox “hay señal”) | `--profile extended` + `ENABLE_SIGNS=true` (usa `:8093`) |

### Profile `experimental`

| Capacidad | Qué detecta al activar | Cómo |
|-----------|------------------------|------|
| [face_id](detection/face_id/) | Identidad facial (match a galería; identity hasheada) | `--profile experimental` + `ENABLE_FACE_ID=true` + `FACE_ID_INDEX_KEY` |
| [scene_cls](detection/scene_cls/) | Clasificación global de la foto (noche, lluvia…) | `--profile experimental` + `ENABLE_SCENE_CLS=true` |
| [instances](detection/instances/) | Instance segmentation (máscaras por objeto) | `--profile experimental` + `ENABLE_INSTANCE_SEG=true` |
| [small_objects](detection/small_objects/) | Objetos muy chicos (modelo tipo drone) | `--profile experimental` + `ENABLE_SMALL_OBJECTS=true` |
| [anomaly](detection/anomaly/) | Anomalías / defectos | `--profile experimental` + `ENABLE_ANOMALY=true` |

Otros: [signs](detection/signs/) legacy COCO → `--profile legacy-signs` (`:8088`). Alertas → `--profile rules`.

Infra compartida: [detection/common/](detection/common/), [infra/](infra/), [rules/](rules/), [tests/](tests/). Cada carpeta de capacidad tiene su `README.md`.

## Arquitectura (hot path)

```text
[Upload / imagenes_muestra] --> [adapter] <--poll-- [bridge]
                                                      |
         +--------+--------+--------+--------+--------+
         v        v        v        v        v
     vehicles  objects   ocr     faces    pose
      :8080     :8082   :8081    :8083    :8086
         |        |    plates+text |        |
         +--------+--------+--------+--------+
                          |
                   merge + NMS (vehicle>object)
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
NVIDIA. `docker compose up` levanta **~5 paddlex** (vehicles, ocr, objects, faces,
pose) + adapter + bridge, con techo `mem_limit ~2g` por contenedor. Extended /
experimental solo con su profile. El cuello esperado es CPU, no RAM.

| Recurso | URL |
|---------|-----|
| Dashboard (SPA) | http://localhost:8000/app/ |
| Events | http://localhost:8000/events |
| Health | http://localhost:8000/health |
| PaddleX vehicles | http://localhost:8080 |
| PaddleX OCR (plates + text) | http://localhost:8081 |
| PaddleX objects | http://localhost:8082 |
| PaddleX faces | http://localhost:8083 |
| PaddleX pose | http://localhost:8086 |

## Flujo foto

1. Subí JPG desde el panel o copiá a `imagenes_muestra/`.
2. Adapter auto-selecciona; bridge polea `/media/current` y detecta en background.
3. SPA: capacidades disponibles; toggles solo muestran/ocultan boxes (opt-in; verde=hit, rojo=miss).
4. **Limpiar foto** → bridge idle.

## Perfiles Compose

| Comando | Efecto |
|---------|--------|
| `docker compose up --build` | hot (~5 paddlex) + adapter + bridge |
| `docker compose --profile extended up --build` | + pedestrians, scene, open-vocab |
| `docker compose --profile experimental up --build` | + face-id, scene-cls, instances, small-objects, anomaly |
| `docker compose --profile legacy-signs up` | + paddlex-signs `:8088` (rollback COCO) |
| `docker compose --profile demo up --build` | bridge sintético |
| `docker compose --profile rules up --build` | + JetLinks + rules-sink |
| `docker compose --profile gpu up --build` | PaddleX GPU (requiere NVIDIA; no aplica en PC-Javier) |

## Variables útiles

Ver [`.env.example`](.env.example). Hot: `ENABLE_PLATE_OCR`, `ENABLE_SCENE_OCR`,
`ENABLE_FACE_DETECTION`, `ENABLE_POSE`. Opt-in: `ENABLE_PEDESTRIAN_ATTRS`,
`ENABLE_SCENE_SEG`, `ENABLE_OPEN_VOCAB`, `ENABLE_SIGNS`, flags experimentales
(`ENABLE_FACE_ID` …), `OPEN_VOCAB_PROMPT`, `TIMONEL_USE_HPIP`, `MEDIA_DIR`,
`PADDLEX_*`, `BRIDGE_MAX_WIDTH`, `TIMONEL_ENV`.

## Tests

```bash
PYTHONPATH=. python3 tests/test_bridge_helpers.py
PYTHONPATH=. python3 tests/test_timonel.py
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

## Contrato timonel

Portable en [adapter/timonel.py](adapter/timonel.py): entra dict de detección,
sale `PerceptionEvent` (votación patente/color/`class_name`/scene). Sin reglas de negocio.

## Troubleshooting

```bash
docker compose logs -f bridge
docker compose logs -f adapter
curl http://localhost:8000/media/current
```

Sin foto activa el bridge queda idle (esperado).
