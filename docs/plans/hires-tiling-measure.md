# Hires multi-tile measure vs PR2 baseline

**Date:** 2026-07-25  
**Harness:** `scripts/measure_hires_tiling.py`  
**Report (local, gitignored):** `scripts/eval_report_hires_tiling.json`

## Why pad (not native 1920 photos)

Core pack fixtures are ≤640 px wide → InferenceSlicer is effectively **single-tile** (PR2 smoke). To exercise multi-tile without inventing a new dataset, the harness **pads** each fixture onto a width=1920 canvas (native pixels top-left, black fill). GT bboxes stay in the same pixel coords.

## PR2 baseline (native pack, 19 fixtures vehicles)

| Path | bbox_match_rate |
|------|-----------------|
| Direct JPEG | 0.4691 |
| `--via-bridge-preprocess` | **0.358** |
| `--via-tiled-sync` | **0.358** |

See [`pr2-tiling-smoke-vehicles.md`](pr2-tiling-smoke-vehicles.md).

## Hires pad sample (2026-07-25, 5 fixtures, `INFER_SLICE_WH=640`)

| Path | bbox_match_rate | tp/gt | mean latency |
|------|-----------------|-------|--------------|
| Bridge preprocess @1920 pad | 0.20 | 5/25 | **4.6 s** |
| Tiled sync (8–20 tiles/frame) | 0.24 | 6/25 | **51.8 s** |

Tiles/frame observed: 8–20 (all multi-tile).

## Decision

**`ENABLE_INFER_TILING` remains `false` (default).**

- Match rate: +0.04 absoluto en n=5 (ruido; no supera baseline nativo 0.358).
- Costo: ~11× latencia media (tile POSTs seriales, `thread_workers=1`).
- No hay fotos hires nativas en el pack Core para atribuir una ganancia real de resolución.

Re-medir cuando exista un pack hires real; hasta entonces el flag no pasa a `true`.

## Command

```bash
PADDLEX_URL=http://127.0.0.1:8080 BRIDGE_MAX_WIDTH=1920 \
  PYTHONPATH=. PYTHONUNBUFFERED=1 \
  python scripts/measure_hires_tiling.py
# optional: HIRES_MAX_FIXTURES=5
```
