# E2E Core acierto / etiquetado — runbook + veredicto

**Estado:** harness cuantitativo Core corrido (2026-07-25); veredicto abajo.  
**Scope:** profile compose **default** (vehicles + objects + OCR serving + adapter + bridge). Sin packs extended/experimental, CLAHE, deskew ni UI de polígonos.

## Objetivo

Separar causas de “no etiqueta bien”:

1. Under-detection del modelo (baseline Core conocido).
2. Config producto (`ENABLE_PLATE_OCR`, caps).
3. Preprocess bridge (`BRIDGE_MAX_WIDTH` / tiling).
4. Path integración (merge / schema `/events` / preview) — **no** lo cubre el harness PaddleX.

## Preflight

```bash
docker compose up --build -d
# health: paddlex :8080/:8081/:8082 docs + adapter :8000/health
```

Defaults esperados (ver `.env.example`): `BRIDGE_MAX_WIDTH=1920`, `ENABLE_INFER_TILING=false`, `ENABLE_PLATE_OCR=false`.

Anti-thrash media-watch: dejar en la raíz de `imagenes_muestra/` solo las fotos de smoke (`fo_vehicles_0002.jpg`, `fo_objects_0001.jpg`); el resto en subcarpeta temporal. Restaurar al final.

## Paso 1 — Harness cuantitativo (PaddleX)

```bash
# A) Directo
PYTHONPATH=. python scripts/eval_paddlex_fixtures.py --packs core --out imagenes_muestra --report scripts/eval_report_e2e_direct.json

# B) Resize bridge
PYTHONPATH=. python scripts/eval_paddlex_fixtures.py --packs core --out imagenes_muestra --via-bridge-preprocess --report scripts/eval_report_e2e_bridge.json

# B2) Objects aislado vía bridge (evitar sesgo solo-vehicles al decidir tiling)
PYTHONPATH=. python scripts/eval_paddlex_fixtures.py --packs core --only objects --out imagenes_muestra --via-bridge-preprocess --report scripts/eval_report_e2e_objects_bridge.json
```

Comparar vs `scripts/eval_baseline.json` y `scripts/eval_thresholds.yaml`.

| Síntoma | Conclusión |
|---------|------------|
| Direct ≈ baseline | Modelo Core estable |
| Bridge ≪ direct (vehicles u objects) | Probar `--via-tiled-sync` o revisar `BRIDGE_MAX_WIDTH` |
| Direct ≪ baseline | Regresión serving / pipeline |

Tiling condicional:

```bash
PYTHONPATH=. python scripts/eval_paddlex_fixtures.py --packs core --only vehicles,objects --out imagenes_muestra --via-tiled-sync --report scripts/eval_report_e2e_tiled.json
```

Si tiled ≈ bridge y no gana vs direct → dejar `ENABLE_INFER_TILING=false`.

## Paso 2 — Smoke stack integración (bridge → adapter → events)

Cierra el gap que el harness no ve (`merge_coco`, epp_core, preview).

```bash
# OCR off (default de producto). Por defecto pinnea caps a vehicle+object
# y usa fo_vehicles_0002 (0001 suele dar 0 boxes en serving local).
python scripts/smoke_core_stack.py
# o: ./scripts/smoke_core_stack.sh

# Spot OCR on (tras recreate bridge con ENABLE_PLATE_OCR=true)
# EXPECT_PLATE_OCR=true python scripts/smoke_core_stack.py
# luego restaurar ENABLE_PLATE_OCR=false
```

Asserts del script:

- PUT `/capabilities` Core-only (salvo `SMOKE_PIN_CORE_CAPS=false`)
- `fo_vehicles_0002` (override `SMOKE_VEHICLES_PHOTO`) → ≥1 `vehicle`, schema `1.0`, bbox, `vehicle_type`
- Anti-doble: no `object` car/truck/bus/… con IoU>0.5 vs un vehicle
- `plate_text` ausente si `EXPECT_PLATE_OCR=false`; presente si `true`
- `fo_objects_0001` → ≥1 `object` + `class_name`
- `/preview.jpg` no es el placeholder (~9.6 KB)

## Paso 3 — Smoke UI cualitativo

Abrir `http://localhost:8000` (o `/app/`), contrastar overlay/tabla con el JSON de `/events` del paso 2.

Checklist → knobs: ver plan e2e original (OCR off ≠ fallo detector; recall objects ~0.31 = under-detection conocido).

## Resultados de esta corrida

| Campo | Valor |
|-------|-------|
| Fecha | 2026-07-25 |
| Commit | `f15d3b2` |
| Flags | tiling=false (`ENABLE_INFER_TILING=false`), `BRIDGE_MAX_WIDTH=1920`, `ENABLE_PLATE_OCR=true` (bridge); harness PaddleX no usa ese flag |
| Reports | `scripts/eval_report_e2e_direct.json`, `eval_report_e2e_bridge.json`, `eval_report_e2e_objects_bridge.json` |
| Nota ops | Antes de la corrida válida: host→`:8081`/`:8082` daba `RemoteDisconnected` (vehicles `:8080` OK). `docker restart vi-paddlex-ocr vi-paddlex-objects` restauró docs/predict; la 1ª corrida direct con objects/OCR a 0.0 se descarta |

| Capa | Resultado |
|------|-----------|
| Core direct vs baseline | **PASS** (exit 0). objects recall **0.3861** / prec **0.78** (baseline 0.3152 / 0.7733); vehicles bbox **0.4691** / schema **1.0** (= baseline); ocr_plates **1.0** (= baseline). Sin breaches ni regresiones. |
| Core via-bridge vs baseline | **FAIL gate** (exit 1) solo por vehicles: bbox **0.358** < min 0.45 y < baseline 0.4691−0.05. objects recall **0.3861** / prec **0.7959** (sin regresión); ocr **0.95** (sobre min 0.90; en el borde de tolerancia baseline). Mismo drop vehicles que smoke PR1/PR2 documentado. |
| Objects via-bridge | **PASS** (exit 0). recall **0.3861** / prec **0.7959** — igual recall que direct, prec ligeramente mejor. No hay sesgo objects que empuje tiling. |
| Tiled (si corrió) | N/A (fuera de scope de esta corrida) |
| `smoke_core_stack` vehicles/objects | PASS (sesión previa, stack live; no re-corrido aquí) |
| Anti-doble merge | PASS (sesión previa / asserts del smoke) |
| plate_text OCR off / on | OCR on en bridge (`ENABLE_PLATE_OCR=true`); smoke spot OCR documentado en runbook; harness OCR serving direct=1.0 |
| Preview ≠ placeholder | PASS (sesión previa) |

**Veredicto:** `no tocar pipelines` — Core direct estable vs baseline (sin regresión serving); objects vía bridge no degrada; el único hueco cuantitativo es vehicles vía resize (0.358), ya conocido y sin evidencia tiled en esta corrida. No activar OCR como “fix” de under-detection (OCR serving ya en 1.0; `ENABLE_PLATE_OCR` es toggle de producto). Tiling queda como experimento opcional posterior (`--via-tiled-sync`), no como acción ahora.

**Addendum 2026-07-25 — objects sí cambió de modelo.** El veredicto de arriba vale para vehicles/OCR, pero objects quedó superado por el A/B posterior: PicoDet-S (recall 0.386) → **PP-YOLOE_plus-S** (0.604 direct / 0.574 vía bridge, precisión 0.81) vía `detection/objects/pipeline.yaml`. PP-YOLOE_plus-L da 0.693 pero ~3.5x wall y ~2x RAM, así que queda como escalada opt-in (`docker-compose.objects-yoloe-exp.yml`, con `mem_limit` subido a 1600m). `eval_baseline.json` refrescado sólo en las claves de objects.

## Referencias

- Plan ops: `.cursor/plans/e2e_acierto_etiquetado_*.plan.md`
- Ampliación gaps: `.cursor/plans/e2e_gaps_ampliación_*.plan.md`
- Baseline / umbrales: `scripts/eval_baseline.json`, `scripts/eval_thresholds.yaml`
- CI: `tests/test_eval_match.py` incluido en `.github/workflows/ci.yml`
