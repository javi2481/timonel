# adapter/ui/

## Para qué sirve

UI de Timonel (Vite/React) servida por el adapter + placeholder de preview.
Abrís `http://localhost:8000/`; el adapter redirige `/` → `/app/`.

Empty-state: elegí `demo_*.jpg` o subí una foto. Con el stack default
(`full_up` / `docker compose up`) las capas ya están activas; click en una
capa verde con hits muestra/oculta cajas en el canvas.

## Cómo funciona

1. Fuente en `spa-src/` → `npm run build` (o stage Node del Dockerfile) → `spa/`.
2. FastAPI monta `SPA_DIR` en `/app` (`StaticFiles`, `html=True`).
3. La UI habla con `/media/*`, `/preview.mjpg` / `/media/original`, `/events`, `/capabilities`.
4. Tras clear, el adapter muestra `placeholder_preview.jpg` en el preview MJPEG.

## Entrada / salida

Estáticos servidos por FastAPI. Sin lógica de negocio en estos archivos.
**Sin CDN en runtime** — el panel funciona offline / en edge.

## Archivos clave

- `spa-src/` — fuente (Vite + React + TS).
- `spa/` — build (gitignored; `.gitkeep` mantiene el dir; se regenera en la imagen).
- `placeholder_preview.jpg` — preview vacío.

## Build e integración

- `adapter/Dockerfile` multi-stage: `node:20-slim` corre `npx tsc -b && npx vite build`;
  el stage Python copia `adapter/ui/spa/` — **no necesita Node en el host**.
- Vite `base: "/app/"` (ruta técnica de montaje; la URL de producto es `:8000/`).
- Tipos: `contracts/timonel.gen.ts` → `spa-src/src/types/timonel.gen.ts`.
- Colores: `scripts/gen_entity_colors.py` desde `detection/common/preview.py`
  → `spa-src/src/colors/entityColors.gen.ts`.
- Completitud del análisis: `generation === last_ingest_generation` en `GET /events`.

## Qué no es

No contiene detección. No es un dashboard de terceros: solo la UI de Timonel.
