# detection/

## Para qué sirve

Código cliente de las capacidades de IA (HTTP + normalize). Bridge orquesta.
El código de todas las carpetas **se conserva**; Compose + `ENABLE_*` deciden
qué corre. En el **stack default** (`full_up` / `docker compose up`) todas las
capas SPA de abajo están ENABLE y con servicio up.

## Cómo funciona

```text
bridge → gather de capas activas (SPA / ENABLE_*)
       → merge → plates? → ingest
```

## Capacidades (stack default)

| Carpeta | Capacidad | Flag / servicio |
|---------|-----------|-----------------|
| [vehicles/](vehicles/) | Tipo/color vehículo | `ENABLE_VEHICLES` → `:8080` |
| [objects/](objects/) | COCO (incl. person) | siempre → `:8082` |
| [plates/](plates/) | OCR patente | `ENABLE_PLATE_OCR` → `:8081` |
| [faces/](faces/) | Rostros | `ENABLE_FACE_DETECTION` → `:8083` |
| [pose/](pose/) | Keypoints | `ENABLE_POSE` → `:8086` |
| [text/](text/) | OCR carteles | `ENABLE_SCENE_OCR` (reusa `:8081`) |
| [pedestrians/](pedestrians/) | Attrs persona | `ENABLE_PEDESTRIAN_ATTRS` → `:8084` |
| [scene/](scene/) | Escena / lanes / crosswalk | `ENABLE_SCENE_SEG` → `:8085` |
| [open_vocab/](open_vocab/) | Open-vocab (prompt) | `ENABLE_OPEN_VOCAB` → `:8093` |
| [signs/](signs/) | Señales (vía OV) | `ENABLE_SIGNS` → mismo `:8093` |
| [face_id/](face_id/) | Identidad facial | `ENABLE_FACE_ID` → `:8087` |
| [scene_cls/](scene_cls/) | Clasif. escena | `ENABLE_SCENE_CLS` → `:8089` |
| [instances/](instances/) | Instance seg | `ENABLE_INSTANCE_SEG` → `:8090` |
| [small_objects/](small_objects/) | Small objects | `ENABLE_SMALL_OBJECTS` → `:8091` |
| [anomaly/](anomaly/) | Anomaly | `ENABLE_ANOMALY` → `:8092` |

Compose fuerza `ENABLE_*=true` en adapter/bridge. Lifecycle on-demand
(`compose.ondemand.yml`) es override avanzado, no el default.

### Compartido

| Carpeta | Rol |
|---------|-----|
| [common/](common/) | Tracker, geometry, preview, NMS |

## Qué no es

No levanta modelos ni Docker: solo clientes HTTP + normalización.
