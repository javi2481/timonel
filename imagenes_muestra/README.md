# imagenes_muestra/ — media + fixtures de eval

Mount local usado por adapter/bridge (`./imagenes_muestra:/media/images`).
Los JPG pesados están en `.gitignore`; este README es el único archivo tracked.

## Layout (tras descargar eval)

```text
imagenes_muestra/
  fo_objects_0001.jpg      # raíz plana — el media scan del adapter las ve
  fo_vehicles_0001.jpg
  fo_ocr_plates_0001.jpg
  packs/<suite>/*.jpg      # copias anidadas (no las necesita el scan de la UI)
  gt/<suite>.json          # ground truth por suite
  gt/manifest.json         # sha256 + seed=51
  failures/<suite>/*.json  # misses Tier A/B del eval
```

## Harness de accuracy (gate local — no CI)

Deps solo en el host:

```bash
python -m pip install -r scripts/requirements-eval.txt
```

Descargar fixtures (seed=51, ~15–20 muestras/suite):

```bash
# Gate local Core (default)
PYTHONPATH=. python scripts/download_paddlex_eval.py --packs core --out imagenes_muestra

# Core + Extended + Experimental
PYTHONPATH=. python scripts/download_paddlex_eval.py --packs all --out imagenes_muestra
```

Evaluar contra PaddleX en localhost (stack ya levantado):

```bash
PYTHONPATH=. python scripts/eval_paddlex_fixtures.py --packs core --out imagenes_muestra
PYTHONPATH=. python scripts/eval_paddlex_fixtures.py --packs all --out imagenes_muestra
# Subconjunto: --only / --pipelines signs,faces,anomaly
```

Smoke de integración Core (bridge → `/events` → preview; sin harness):

```bash
python scripts/smoke_core_stack.py
# OCR on en el stack: EXPECT_PLATE_OCR=true python scripts/smoke_core_stack.py
```

Foto default de vehicles: `fo_vehicles_0002.jpg` (la 0001 suele dar 0 boxes en local).

| Capa | Suites | Notas |
|------|--------|-------|
| Core | `objects` :8082, `vehicles` :8080, `ocr_plates` :8081 | Gate local de accuracy |
| Extended | `signs` :8088, `faces` :8083, `pose` :8086, `pedestrians` :8084 (Tier B), `scene` :8085 (Tier B), `ocr_text` :8081 | Opcional |
| Experimental | `face_id` :8087, `scene_cls` :8089, `instances` :8090, `small_objects` :8091, `anomaly` :8092 (Tier C smoke), `open_vocab` :8093 | Opcional; Core nunca las exige |

- `ocr_plates` / `ocr_text` / `faces` / `anomaly` / `face_id` / `scene_cls` son **sintéticos** (Pillow); FO COCO para suites de detección
- `face_id` también escribe `gt/face_id_gallery.json` (manifest de enrollment)
- Tier B honesto donde no hay GT de píxel/clase (`scene`, `open_vocab`, `scene_cls`, `face_id`)
- El baseline `scripts/eval_baseline.json` es **manual** — nunca se sobreescribe solo
- Exit ≠ 0 si hay breach de umbral o regresión vs baseline (barras Core siempre; Extended/Exp solo si corrés esas suites)

### Checklist E2E manual

1. `docker compose up --build` (profile default: vehicles/objects/ocr; profiles para puertos Extended/Exp)
2. Pausá el media-watch o aceptá thrash mientras descargás
3. `download_paddlex_eval.py --packs core` (o `--packs all`)
4. `eval_paddlex_fixtures.py --packs core` (o `--packs all` / `--pipelines …`)
5. Revisá `scripts/eval_report.json` + `failures/<suite>/`
6. Si un upgrade de modelo mejoró métricas a propósito, copiá a mano a `eval_baseline.json`

## Thrash del media-watch

Escribir muchos JPG planos de golpe puede saturar el watch del adapter. Si la UI se agita:

1. Pausá / parás bridge+adapter un momento, o sacá los JPG de eval de la raíz
2. Preferí caps de pack (~20/suite; Core por default)
3. Limpiá `fo_*` de la raíz entre experimentos; conservá `packs/`/`gt/` si vas a re-aplanar

## Licencias

- Muestras COCO: términos de [COCO dataset](https://cocodataset.org/#termsofuse) al bajar vía FiftyOne
- Patentes OCR sintéticas: generadas en local; sin fotos de terceros

## Qué no es

No es un gate de CI. No cambia el mount de Compose. FiftyOne nunca se instala dentro de las imágenes Docker.
