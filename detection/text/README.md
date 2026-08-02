# detection/text/

## Para qué sirve

OCR de carteles / texto en escena (no filtrado a patentes). Reusa
`paddlex-ocr` (:8081).

## Cómo funciona

1. `ENABLE_SCENE_OCR=true`.
2. POST del JPEG completo a `/ocr` (capa `text`).
3. Tras el merge, si hay dets `sign` y `SCENE_OCR_FROM_SIGNS=true`:
   recorta top-K carteles en hires → OCR → líneas `text` con bbox
   desplazado al frame completo (mismo patrón que plates sobre vehículos).
4. Emite dets `entity_type:"text"` con `text` + score (top-K global por score).

## Entrada / salida

- **Entrada:** `jpeg: bytes` (full-frame) + enrich opcional sobre `frame_hires` + signs.
- **Salida:** `[{track_id:t-*, label:"text", text, score, bbox, entity_type:"text"}]`.
  Líneas de crop llevan `source:"sign_crop"` y opcional `sign_track_id`.

## Servicio / deps

| Item | Valor |
|------|--------|
| Compose | reusa `paddlex-ocr` |
| Env | `ENABLE_SCENE_OCR`, `SCENE_OCR_MIN_SCORE` (default **0.3**), `SCENE_OCR_MAX_LINES`, `SCENE_OCR_FROM_SIGNS`, `SCENE_OCR_SIGN_TOPK`, `SCENE_OCR_SIGN_MIN_SCORE`, `PADDLEX_OCR_URL` |
| Dep | capacidad `signs` activa para el path de crops |

## Archivos clave

- `client.py`

## Qué no es

No reemplaza `plates/` (regex de patente sobre crops de vehículos).
