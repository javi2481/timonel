# detection/open_vocab/

## Para qué sirve

Detección open-vocabulary (prompt de texto → boxes). Útil para clases fuera
del vocabulario fijo de `objects`/`signs` (p. ej. EPP).

## Cómo funciona

1. `ENABLE_OPEN_VOCAB=true` + servicio `paddlex-open-vocab` `:8093`.
2. Prompt vía `OPEN_VOCAB_PROMPT` (default `person,car,traffic sign`).
3. Emite `entity_type:"open_vocab"`.

## Modelo (CPU)

Pipeline montado: `pipeline.yaml` → **YOLO-Worldv2-L**.

El default upstream (`GroundingDINO-T`) en paddle 3.0.0 CPU responde 500
(`RuntimeError: could not reshape a memory descriptor`). No se arregla con
`FLAGS_use_mkldnn=0`. YOLO-Worldv2-L sí corre en este host.

## Gate / aviso

Flexible pero más lento/pesado que objects. Caída aislada en el client
(`None` ante 5xx). Candidato EPP: `OPEN_VOCAB_PROMPT=helmet,safety vest,forklift`
una vez verificado el prompt en fotos reales.

## Servicio / deps

| Item | Valor |
|------|--------|
| Compose | `paddlex-open-vocab` `:8093` (imagen con `PADDLEX_EXTRAS=…,multimodal`) |
| Env | `ENABLE_OPEN_VOCAB`, `PADDLEX_OPEN_VOCAB_URL`, `OPEN_VOCAB_PROMPT`, `OPEN_VOCAB_THRESHOLD` |
| Pipeline | `/opt/paddlex/pipelines/open_vocab_yoloworld.yaml` |
