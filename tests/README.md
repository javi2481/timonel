# tests/

## Para qué sirve

Tests stdlib (`unittest`) de helpers de detection, bridge, contrato Timonel y
media del adapter. En local son opcionales; GitHub Actions corre la misma suite
en `.github/workflows/ci.yml`.

## Cómo funciona

Desde la raíz del repo, con deps instaladas (`opencv`, `numpy`, `pydantic`,
`fastapi`, …):

```bash
PYTHONPATH=. python3 tests/test_timonel.py
PYTHONPATH=. python3 tests/test_bridge_helpers.py
PYTHONPATH=. python3 tests/test_bridge_cascade.py
PYTHONPATH=. python3 tests/test_bridge_lifecycle.py
PYTHONPATH=. python3 tests/test_adapter_media.py
PYTHONPATH=. python3 tests/test_capabilities.py
PYTHONPATH=. python3 tests/test_tiled_infer.py
PYTHONPATH=. python3 tests/test_nms_zones_pr3.py
PYTHONPATH=. python3 tests/test_parse_plate_stats.py
PYTHONPATH=. python3 tests/test_eval_match.py
```

Con vendor local (si existe `.vendor/`):

```bash
PYTHONPATH=".vendor:." python3 tests/test_adapter_media.py
```

## Fixtures

| Archivo | Descripción |
|---------|-------------|
| `fixtures/sample.jpg` | JPEG mínimo válido (1×1) para pruebas de media/preview sin depender de PIL |

Generado como bytes JFIF embebidos (no requiere Pillow). Se puede regenerar con
cualquier encoder que escriba un `.jpg` pequeño en esa ruta.

## Entrada / salida

Sin servicios Docker: solo funciones puras / helpers.

## Servicio / deps

Ninguno. Requiere packages de `bridge/requirements.txt` + `adapter/requirements.txt`.

## Archivos clave

| Test | Cubre |
|------|--------|
| `test_timonel.py` | consolidación / entity_type / contrato |
| `test_bridge_helpers.py` | geometry, preview, vehicles, objects, media |
| `test_bridge_cascade.py` | cascada por evidencia (política + gather) |
| `test_bridge_lifecycle.py` | pause/unpause idle + wake oleada 2 |
| `test_adapter_media.py` | media watch / select |
| `test_capabilities.py` | plano de control GET/PUT |
| `test_tiled_infer.py` | tiling / round-trip detecciones |
| `test_nms_zones_pr3.py` | NMS cross-cap + zonas |
| `test_parse_plate_stats.py` | parseo stats de patentes |
| `test_eval_match.py` | IoU matcher, OCR normalize, thresholds/baseline, pack registry |

CI también regenera `contracts/timonel.gen.ts` vía `scripts/gen_timonel_types.py`
y falla si el archivo commiteado está desfasado.

## Qué no es

No sustituye smoke E2E con `docker compose up`.
No descarga FiftyOne ni llama a PaddleX en CI (`test_eval_match.py` es puro).
