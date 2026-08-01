# detection/signs/

## Para qué sirve

Señales de tránsito → bbox con `entity_type:"sign"` y tracks `s-*`.
No hace falta tipo fino de señal (rombo/stop/semáforo): el contrato de producto
es **hay una señal aquí**.

## Backend de producto (YOLO-World)

1. `ENABLE_SIGNS=true` + servicio `paddlex-open-vocab` `:8093`.
2. `SIGNS_BACKEND=ov` (default) → POST `/open-vocabulary-detection` con
   `build_open_vocab_body` (`SIGNS_OV_PROMPT` + `SIGNS_OV_THRESHOLD`).
3. Label **colapsado a `"sign"`**. `categoryName` del prompt + score van como
   `hint` (pista, no veredicto) — alineado con el contrato Timonel.
4. Ownership: **"señal" es exclusiva de esta capacidad**. `OPEN_VOCAB_PROMPT`
   no debe incluir `"traffic sign"` (si no, el mismo cartel sale como
   `sign/s-*` y `open_vocab/ov-*`; NMS-B no los fusiona).

Defaults propuestos (medición `scripts/measure_signs_ov_ab.py`, fo_signs n=2
seed=51; **AR pendiente** — sin fotos locales):

| Knob | Valor propuesto | Nota |
|------|-----------------|------|
| `SIGNS_OV_PROMPT` | `traffic sign,stop sign,traffic light` | OV-B; OV-A solo (`traffic sign`) dio 0 hits |
| `SIGNS_OV_THRESHOLD` | `0.05` | P≈0.67 R≈0.50 @960; thr≥0.1 → 0 hits en este pack |

Confirmar con gate humano. Report JSON: `scripts/measure_signs_ov_ab_report.json`.

## Threshold

`SIGNS_OV_THRESHOLD` es **perilla propia**. Los scores YOLO-World no están
calibrados como COCO: no reusar `SIGNS_THRESHOLD` (queda solo para legacy).

## Legacy COCO (rollback)

`paddlex-signs` `:8088` está en Compose profile `legacy-signs` (no arranca
con `docker compose up`).

Rollback nombrado:

```bash
docker compose --profile legacy-signs up -d paddlex-signs
# en .env / bridge:
SIGNS_BACKEND=coco
PADDLEX_SIGNS_URL=http://paddlex-signs:8088
# SIGNS_THRESHOLD=0.1  (filtro SIGN_LABELS)
```

## Servicio / deps

| Item | Valor |
|------|--------|
| Compose (producto) | `paddlex-open-vocab` `:8093` |
| Compose (legacy) | `paddlex-signs` `:8088` (`profiles: [legacy-signs]`) |
| Env producto | `ENABLE_SIGNS`, `SIGNS_BACKEND`, `PADDLEX_SIGNS_OV_URL`, `SIGNS_OV_PROMPT`, `SIGNS_OV_THRESHOLD` |
| Env legacy | `PADDLEX_SIGNS_URL`, `SIGNS_LABELS`, `SIGNS_THRESHOLD` |

## Qué no es

- No ensucia el timonel `open_vocab` (sigue emitiendo `open_vocab`/`ov-*`).
- No es fine-tune / PULC / Roboflow / TT100K.
- No reemplaza `objects/` COCO general.
