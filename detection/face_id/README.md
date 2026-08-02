# detection/face_id/

## Para qué sirve

Identidad facial vía PaddleX `face_recognition` (match / label).
El bbox de rostro “anónimo” sigue en `faces/`.

## Cómo funciona

1. `ENABLE_FACE_ID=true` + `paddlex-face-id` + **`FACE_ID_INDEX_KEY`** (galería).
2. Sin key: el adapter marca `available=false` (Identidad no sale en el panel) y
   el client del bridge no llama al serving (evita 500 `assert indexer`).
3. Con key: emite `entity_type:"face_id"` con `identity` + score.

## Gate / aviso

1. Rebuild imagen paddlex (parche `infra/patches/paddlex_faisser.py`) o montaje
   hot-patch en compose — sin eso `index-build` rompe con features `(N,1,D)`.
2. Cargar galería una vez (helper):

```bash
python scripts/face_id_index_build.py --dir path/a/galeria
# galeria/<label>/*.jpg  →  imageLabelPairs
```

   O `POST /face-recognition-index-build` con `imageLabelPairs` → `indexKey`.
3. Pegá ese key en `.env` como `FACE_ID_INDEX_KEY=...` y recreá **adapter +
   bridge** (`docker compose up -d --force-recreate adapter bridge`).

Sin índice, el infer del serving responde 500. Evaluar aspectos legales/privacidad.

## Servicio / deps

| Item | Valor |
|------|--------|
| Compose | `paddlex-face-id` `:8087` (stack default) |
| Env | `ENABLE_FACE_ID`, `FACE_ID_INDEX_KEY` (adapter + bridge), `PADDLEX_FACE_ID_URL`, `PADDLEX_FACE_ID_PREDICT_PATH` (default `/face-recognition-infer`) |

## Qué no es

No sustituye `detection/faces/` (solo detección).
