# Timonel

Timonel orquesta detectores PaddleX sobre **una foto**: objetos, caras, pose,
vehículos y texto. Vos prendés cada capa y mirás qué aporta.

> Orquestar, no inventar.

## Probarlo

```bash
cp .env.example .env
docker compose up --build
```

Abrí [http://localhost:8000/](http://localhost:8000/). La UI arranca vacía:
subí un JPG o elegí uno de `imagenes_muestra/`.

| | |
|--|--|
| UI | http://localhost:8000/ |
| Health | http://localhost:8000/health |
| Eventos | http://localhost:8000/events |

Sin foto activa el bridge queda en idle (esperado).

## Qué hace

1. El [adapter](adapter/) recibe la foto y sirve la UI.
2. El [bridge](bridge/) llama a las capacidades en [detection/](detection/).
3. Fusiona resultados (NMS entre capas) y publica eventos tipados.
4. La UI dibuja overlays, leyenda y analítica sobre lo detectado.

El contrato portable vive en [`adapter/timonel.py`](adapter/timonel.py): entra
una detección, sale un `PerceptionEvent`. Sin reglas de negocio ahí.

```text
foto → adapter → bridge → PaddleX (varias capas)
                      ↓
              PerceptionEvent → UI
```

## Qué viene prendido

Con `docker compose up` (CPU, sin GPU):

- vehículos, objetos (COCO, incl. persona), caras, pose
- OCR de patentes y de texto en escena (mismo servicio OCR)
- adapter + bridge

El resto del código en `detection/` está intacto y se activa con profiles
Compose + flags en [`.env.example`](.env.example):

| Profile | Ejemplos |
|---------|----------|
| `extended` | peatones (atributos), escena, open-vocab, señales |
| `experimental` | face-id, clasificación de escena, instancias, anomalías |
| `demo` | bridge sintético sin modelos |
| `rules` | sink de alertas |
| `gpu` | PaddleX con NVIDIA |

Detalle por capacidad: [detection/README.md](detection/README.md).

## Recursos

El stack default levanta ~5 contenedores PaddleX + adapter + bridge, con techo
~2 GB RAM por contenedor. Si hay OOM, subí el `mem_limit` del servicio o bajá
`BRIDGE_MAX_WIDTH`.

## Desarrollo

```bash
# tests unitarios (también en CI)
PYTHONPATH=. python3 tests/test_timonel.py
PYTHONPATH=. python3 tests/test_bridge_helpers.py

# accuracy local (no bloquea CI) — ver imagenes_muestra/README.md
PYTHONPATH=. python scripts/download_paddlex_eval.py --packs core
PYTHONPATH=. python scripts/eval_paddlex_fixtures.py --packs core
```

Más: [tests/](tests/), [infra/](infra/), [adapter/ui/](adapter/ui/).

## Si algo falla

```bash
docker compose logs -f bridge
docker compose logs -f adapter
curl http://localhost:8000/media/current
```
