# tests/

## Para qué sirve

Tests stdlib (`unittest`) de helpers de detection, bridge, contrato Timonel,
media del adapter y config Compose de onboarding. GitHub Actions corre la
misma suite en `.github/workflows/ci.yml`.

## Capas de verificación

| Capa | Qué | CI |
|------|-----|----|
| Unitarios | `tests/test_*.py` sin modelos PaddleX | sí |
| Compose onboarding | `test_compose_onboarding.py` + `compose config` | sí |
| SPA build | `npm ci && npm run build` en `adapter/ui/spa-src` | sí |
| Smoke onboarding | `scripts/smoke_onboarding.py` (stack core) | manual |
| Smoke core fo_* | `scripts/smoke_core_stack.py` | manual |
| Eval PaddleX | `scripts/eval_paddlex_fixtures.py` | no |

## Cómo funciona

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
PYTHONPATH=. python3 tests/test_compose_onboarding.py
```

## Qué no es

No sustituye smoke E2E con PaddleX real en cada PR.
