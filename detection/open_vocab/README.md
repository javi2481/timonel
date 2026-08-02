# detection/open_vocab/

## Para qué sirve

Cola larga fuera del piso COCO de `objects/`: prompt de texto → boxes.
Pieza central de “qué hay en la foto” para clases que YOLO-World pueda
buscar y COCO ignore (casco, extintor, grapadora, etc.).

## Cómo funciona

1. `ENABLE_OPEN_VOCAB=true` + servicio `paddlex-open-vocab` `:8093`.
2. Prompt vía `OPEN_VOCAB_PROMPT` (default cola larga en `client.py` — **sin**
   `"traffic sign"`; ownership de "señal" es de `detection/signs`).
   Override por foto: Form `open_vocab_prompt` en upload → `GET /media/current`
   → bridge pasa `prompt=` a `infer_open_vocab`.
3. Emite `entity_type:"open_vocab"` / tracks `ov-*`. Body vía `build_open_vocab_body`.
4. Con cascada on, OV corre en **oleada 1** (en paralelo con objects). El NMS
   del bridge dedupea solapes con `vehicle`/`object`
   (preferencia vehicle > object > open_vocab).

## Modelo (CPU)

Pipeline montado: `pipeline.yaml` → **YOLO-Worldv2-L**.

El default upstream (`GroundingDINO-T`) en paddle 3.0.0 CPU responde 500
(`RuntimeError: could not reshape a memory descriptor`). No se arregla con
`FLAGS_use_mkldnn=0`. YOLO-Worldv2-L sí corre en este host.

## Gate / aviso

Más lento/pesado que objects. Es **prompt-driven**, no class-agnostic: sin
términos en el prompt no hay hit. Override por env; prompt por upload en la UI
queda fuera de esta entrega. Caída aislada en el client (`None` ante 5xx).

## Servicio / deps

| Item | Valor |
|------|--------|
| Compose | `paddlex-open-vocab` `:8093` (stack default; imagen con `PADDLEX_EXTRAS=…,multimodal`) |
| Env | `ENABLE_OPEN_VOCAB`, `PADDLEX_OPEN_VOCAB_URL`, `OPEN_VOCAB_PROMPT`, `OPEN_VOCAB_THRESHOLD` |
| Pipeline | `/opt/paddlex/pipelines/open_vocab_yoloworld.yaml` |
