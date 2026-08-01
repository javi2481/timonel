# detection/

## Para qué sirve

Código cliente de las capacidades de IA (HTTP + normalize). Bridge orquesta.
El código de todas las carpetas **se conserva**; Compose + flags deciden qué
corre en caliente.

## Cómo funciona

```text
bridge → vehicles + objects + faces + pose + text (+ plates OCR)
       → [extended/experimental si ENABLE_* y profile]
       → merge → ingest
```

## Capacidades

### Hot (default compose)

| Carpeta | Capacidad | Flag / servicio |
|---------|-----------|-----------------|
| [vehicles/](vehicles/) | Tipo/color vehículo | default `:8080` |
| [objects/](objects/) | COCO (incl. person) | default `:8082` |
| [plates/](plates/) | OCR patente | `ENABLE_PLATE_OCR` → `:8081` |
| [faces/](faces/) | Rostros | `ENABLE_FACE_DETECTION` → `:8083` |
| [pose/](pose/) | Keypoints | `ENABLE_POSE` → `:8086` |
| [text/](text/) | OCR carteles | `ENABLE_SCENE_OCR` (reusa `:8081`) |

### Extended (`--profile extended` + flag)

| Carpeta | Capacidad | Flag |
|---------|-----------|------|
| [pedestrians/](pedestrians/) | Attrs persona | `ENABLE_PEDESTRIAN_ATTRS` → `:8084` |
| [scene/](scene/) | Escena / lanes / crosswalk | `ENABLE_SCENE_SEG` → `:8085` |
| [open_vocab/](open_vocab/) | Open-vocab (prompt) | `ENABLE_OPEN_VOCAB` → `:8093` |
| [signs/](signs/) | Señales (vía OV) | `ENABLE_SIGNS` → mismo `:8093` |

### Experimental (`--profile experimental` + flag)

| Carpeta | Capacidad | Flag |
|---------|-----------|------|
| [face_id/](face_id/) | Identidad facial | `ENABLE_FACE_ID` → `:8087` |
| [scene_cls/](scene_cls/) | Clasif. escena | `ENABLE_SCENE_CLS` → `:8089` |
| [instances/](instances/) | Instance seg | `ENABLE_INSTANCE_SEG` → `:8090` |
| [small_objects/](small_objects/) | Small objects | `ENABLE_SMALL_OBJECTS` → `:8091` |
| [anomaly/](anomaly/) | Anomaly | `ENABLE_ANOMALY` → `:8092` |

### Compartido

| Carpeta | Rol |
|---------|-----|
| [common/](common/) | Tracker, geometry, preview, NMS |

## Qué no es

No levanta modelos ni Docker: solo clientes HTTP + normalización.
