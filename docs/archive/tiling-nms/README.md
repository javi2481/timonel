# Archive: tiling / NMS (PR1–PR3)

**Estado:** cerrado. PR1–PR3 completados y mergeados.

## Decisión vigente (producto)

| Var | Valor |
|-----|-------|
| `BRIDGE_MAX_WIDTH` | `1920` |
| `INFER_SLICE_WH` | `640` |
| `ENABLE_INFER_TILING` | `false` |

**Motivo:** medición hires (pad@1920) mostró ganancia de match marginal (~0.20→0.24) con ~11× latencia. Sin pack hires nativo no se activa tiling por default.

## Índice

| Doc | Rol |
|-----|-----|
| [particion-tiling-nms.md](particion-tiling-nms.md) | Plan maestro 3 PRs + veredicto final |
| [infer-slice-wh-pr1.md](infer-slice-wh-pr1.md) | PR1: medición → `INFER_SLICE_WH=640` |
| [pr2-tiling-smoke-vehicles.md](pr2-tiling-smoke-vehicles.md) | PR2 smoke vehicles (tiled = bridge) |
| [pr3-zones-smoke.md](pr3-zones-smoke.md) | PR3 smoke zonas + rules-sink |
| [hires-tiling-measure.md](hires-tiling-measure.md) | Post-PR3: pad hires → flag queda `false` |

Runbook Core vigente (no archivado): [`docs/plans/e2e-core-acierto.md`](../../plans/e2e-core-acierto.md).
