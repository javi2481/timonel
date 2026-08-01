# imagenes_muestra/ — media + fixtures de eval

Mount local usado por adapter/bridge (`./imagenes_muestra:/media/images`).

## Demo onboarding (versionado)

Fotos `demo_*.jpg` **commiteadas** para probar sin FiftyOne ni buscar imágenes.

| | |
|--|--|
| Manifiesto | [`manifest_demo.json`](manifest_demo.json) (`requires`: `core` \| `full`) |
| Atribución | [`LICENSE.md`](LICENSE.md) |
| Regenerar | `python scripts/fetch_demo_images.py` |

### Andan en core (`requires: core`)

Calle / personas / escena — útiles con objects + faces del default Compose.
Ejemplo: `demo_01_street.jpg`.

### Piden full (`requires: full`)

Texto / fachada — necesitan OCR (`--profile full` + flags de `.env.full.example`).
Sin full parecen “vacías”; no es un bug del core.

## Layout (eval, gitignored)

```text
imagenes_muestra/
  demo_XX_*.jpg            # versionadas (onboarding)
  fo_objects_0001.jpg      # eval — gitignored
  packs/ gt/ failures/     # eval
```

Los JPG de eval (`fo_*`) siguen en `.gitignore`. No mezclar nombres `demo_*` / `fo_*`.

## Harness de accuracy (gate local — no CI)

```bash
python -m pip install -r scripts/requirements-eval.txt
PYTHONPATH=. python scripts/download_paddlex_eval.py --packs core --out imagenes_muestra
PYTHONPATH=. python scripts/eval_paddlex_fixtures.py --packs core --out imagenes_muestra
python scripts/smoke_core_stack.py   # integración fo_* (no onboarding)
python scripts/smoke_onboarding.py   # demo_* versionadas
```

## Thrash del media-watch

Muchos JPG en la raíz saturan el watch. Las ~21 demos están OK (< warning ~40).
Si corrés eval, preferí pausar adapter/bridge o sacar `fo_*` de la raíz.

## Licencias

- Demos `demo_*`: CC0/PDM vía Openverse — ver `LICENSE.md`
- Muestras COCO eval: términos COCO al bajar vía FiftyOne (no se versionan)
