# detection/face_id/

## Para qué sirve

Identidad facial vía PaddleX `face_recognition` (match / label).
El bbox de rostro “anónimo” sigue en `faces/`.

## Cómo funciona

1. `ENABLE_FACE_ID=true` + `paddlex-face-id` + `FACE_ID_INDEX_KEY` (galería).
2. Emite `entity_type:"face_id"` con `identity` + score.

## Gate / aviso

1. Rebuild imagen paddlex (parche `infra/patches/paddlex_faisser.py`) o montaje
   hot-patch en compose — sin eso `index-build` rompe con features `(N,1,D)`.
2. Cargar galería una vez:
   `POST /face-recognition-index-build` con `imageLabelPairs` → `indexKey`.
3. Poner ese key en `.env` como `FACE_ID_INDEX_KEY=...` y reiniciar bridge.
   Sin key el client no llama (evita 500 `assert indexer`).

Sin índice, el infer del serving responde 500. Evaluar aspectos legales/privacidad.

## Servicio / deps

| Item | Valor |
|------|--------|
| Compose | `paddlex-face-id` `:8087` |
| Env | `ENABLE_FACE_ID`, `FACE_ID_INDEX_KEY`, `PADDLEX_FACE_ID_URL`, `PADDLEX_FACE_ID_PREDICT_PATH` (default `/face-recognition-infer`) |

## Qué no es

No sustituye `detection/faces/` (solo detección).
