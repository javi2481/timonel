# detection/scene_cls/

## Para qué sirve

Clasificación global de imagen (`image_classification` / multilabel): night, rain, etc.

## Nota de dominio

Capa liviana de señal global; el valor de producto depende del caso (noche/lluvia/…).
En el stack default el servicio está up y `ENABLE_SCENE_CLS=true` vía Compose.

## Servicio

`paddlex-scene-cls` `:8089` — Env: `ENABLE_SCENE_CLS`, `PADDLEX_SCENE_CLS_URL`.
