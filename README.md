# Timonel

## English summary

Timonel orchestrates PaddleX detectors over **one photo** — objects, faces, pose, vehicles, text, and the rest of the SPA layers. Stack: Docker Compose + FastAPI adapter/bridge + SPA. Try it with `.\scripts\full_up.ps1` (or `docker compose up --build --wait`), then open http://localhost:8000/.

---

Timonel orquesta detectores PaddleX sobre **una foto**: objetos, caras, pose,
vehículos, texto y el resto de capas del panel. Al levantar el proyecto
arranacan **todas** las capacidades del stack default.

> Orquestar, no inventar.

![Panel de Timonel](assets/panel.png)

<p align="center"><sub>Varias capacidades PaddleX orquestadas sobre una sola foto: objetos, caras y pose unificados en un flujo de eventos.</sub></p>

## Prerrequisitos

- Docker Desktop / Engine + Compose v2
- ~16+ GB RAM libres recomendados (varios contenedores PaddleX ~2 GB c/u)
- Red la primera vez (descarga de imágenes/modelos; puede tardar varios minutos)

No hace falta Node ni Python en el host para la UI. El `.env` es **opcional**
(Compose ya fuerza `ENABLE_*=true` en adapter/bridge).

## Probarlo (recomendado: todas las capacidades)

```powershell
.\scripts\full_up.ps1
```

```bash
chmod +x scripts/full_up.sh && ./scripts/full_up.sh
```

Equivale a `docker compose up -d --build --wait`: todos los `tm-paddlex-*`
del stack default + adapter + bridge. En la UI las capas arrancan **activas**
(verdes cuando healthy). Click en una capa verde con hits → mostrar/ocultar
cajas en el canvas.

On-demand (start/stop idle) queda como override avanzado:
`compose.ondemand.yml` + `ENABLE_CONTAINER_LIFECYCLE`.
`scripts/ondemand_up.*` redirige a `full_up`.

Abrí [http://localhost:8000/](http://localhost:8000/) (redirige a `/app/`).

1. En el selector elegí una `demo_*.jpg` o subí una foto.
2. Esperá overlays / eventos (cold start de modelos puede tardar minutos).
3. Tocá capas verdes para ocultar/mostrar detecciones en el canvas.

| | |
|--|--|
| UI | http://localhost:8000/ |
| Health | http://localhost:8000/health |
| Eventos | http://localhost:8000/events |

Smoke opcional (Python en el host):

```bash
python scripts/smoke_onboarding.py
# solo UI: python scripts/smoke_onboarding.py --ui-only
```

Progreso: `docker compose ps` · `docker compose logs -f bridge`

## Demos versionadas

En [`imagenes_muestra/`](imagenes_muestra/) hay `demo_*.jpg` con licencia
redistribuible (ver `LICENSE.md`). El manifiesto indica `requires: core|full`
(histórico); con el stack default todas las capas están arriba.

## Qué hace

1. El [adapter](adapter/) recibe la foto y sirve la UI.
2. El [bridge](bridge/) llama a las capacidades en [detection/](detection/).
3. Fusiona resultados y publica eventos tipados.
4. La UI dibuja overlays, leyenda y analítica.

```text
foto → adapter → bridge → PaddleX
                      ↓
              PerceptionEvent → UI
```

## Stack default

Con `docker compose up` / `full_up`:

- `adapter` + `bridge`
- objects, faces, pose, ocr, vehicles
- pedestrians, scene, face-id, scene-cls, instances, small-objects, anomaly, open-vocab

Profiles que siguen aparte: `legacy-signs`, `demo`, `rules`.

- **Face ID:** `FACE_ID_INDEX_KEY` vacío por default — ver `detection/face_id/`.
- **open-vocab / signs:** comparten `:8093`.
- Apagado: `docker compose down` (añadí `-v` solo si querés borrar caches de modelos).

GPU (sustituye vehicles CPU):

```bash
docker compose -f docker-compose.yml -f compose.gpu.yml up --build
```

No levantes `--profile demo` junto al bridge real (dos bridges en `/events`).
Usá `docker compose up adapter bridge-demo` solo si querés el sintético.

| Síntoma | Qué mirar |
|---------|-----------|
| `unhealthy` | `docker compose ps` + `logs`; `start_period` 300s en PaddleX |
| `OOMKilled` | Subir `mem_limit` o bajar `BRIDGE_MAX_WIDTH` |
| Objeto pequeño 0 hits | Modelo SOD aéreo; ver `detection/small_objects/README.md` |

## Recursos

Cada contenedor PaddleX tiene techo ~2 GB RAM. Si hay OOM, subí `mem_limit`
o bajá `BRIDGE_MAX_WIDTH`.

## Desarrollo

```bash
PYTHONPATH=. python3 tests/test_timonel.py
PYTHONPATH=. python3 tests/test_bridge_helpers.py
PYTHONPATH=. python3 tests/test_compose_onboarding.py
```

Más: [tests/](tests/), [infra/](infra/), [adapter/ui/](adapter/ui/).

## Si algo falla

```bash
docker compose logs -f bridge
docker compose logs -f adapter
curl http://localhost:8000/media/current
```
