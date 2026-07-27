# adapter/ui/

## Para qué sirve

UI del producto: SPA Vite/React en `/app/` + placeholder de preview.
`/` en el adapter redirige a `/app/`.

## Cómo funciona

1. Fuente en `spa-src/` → `npm run build` (o stage Node del Dockerfile) → `spa/`.
2. FastAPI monta `SPA_DIR` en `/app` (`StaticFiles`, `html=True`).
3. La SPA habla con `/media/*`, `/preview.mjpg` / `/media/original`, `/events`, `/capabilities`.
4. Tras clear, el adapter muestra `placeholder_preview.jpg` en el preview MJPEG.

## Entrada / salida

Estáticos de la SPA servidos por FastAPI. Sin lógica de negocio en estos
archivos. **Sin CDN en runtime** — el panel funciona offline / en edge.

## Archivos clave

- `spa-src/` — fuente (Vite + React + TS).
- `spa/` — build (gitignored; `.gitkeep` mantiene el dir; se regenera en la imagen).
- `placeholder_preview.jpg` — preview vacío.

## SPA (`/app/`)

- `adapter/Dockerfile` multi-stage: `node:20-slim` corre `npx tsc -b && npx vite build`;
  el stage Python copia `adapter/ui/spa/` — **no necesita Node en el host**.
- Vite `base: "/app/"`.
- Tipos: `contracts/epp.gen.ts` → `spa-src/src/types/epp.gen.ts`.
- Colores: `scripts/gen_entity_colors.py` desde `detection/common/preview.py`
  → `spa-src/src/colors/entityColors.gen.ts`.
- Completitud del análisis: `generation === last_ingest_generation` en `GET /events`.

## Qué no es

No contiene detección. AMIS fue retirado (ya no hay `dashboard.html` ni `vendor/`).
