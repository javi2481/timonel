# ADR: consolidar pipelines PaddleX en menos procesos

- **Estado:** propuesta (spike, sin implementación en Sprint 2)
- **Fecha:** 2026-07-21
- **Contexto:** el stack levanta 13 contenedores PaddleX (una capacidad c/u); cada uno carga runtime + pesos. En el host de referencia (PC-Javier, 32 GB) entran todos; la huella de runtime duplicado por proceso sigue siendo el costo a evaluar.

## Pregunta

¿Se pueden agrupar modelos livianos en menos procesos `paddlex --serve` para reducir huella, sin romper el diseño pedagógico **1 carpeta = 1 capacidad = 1 servicio**?

## Hechos

- El serving de PaddleX 3.x es históricamente **un pipeline por proceso** (`VI_PIPELINE` + puerto).
- Compose ya parametriza la misma imagen (`infra/Dockerfile.paddlex`) por env; el costo es N procesos, no N imágenes distintas.
- El valor de 1:1 carpeta/servicio: aislamiento de fallos, perfiles Compose, onboarding por capacidad, flags `ENABLE_*` independientes.

## Opciones

1. **Mantener 1:1** (recomendado corto plazo): techos `mem_limit` + profiles; no fusionar.
2. **Agrupar experimental** (signos livianos / scene_cls / small) en 1–2 procesos multi-pipeline *si* PaddleX lo permite de forma estable — requiere spike de serving.
3. **Sidecar único con router HTTP interno** — más ingeniería, choca con “orquestar no inventar”.
4. **(a) FastAPI custom multi-pipeline vía `create_pipeline`** — en vez de N procesos
   `paddlex --serve`, un único proceso FastAPI que instancia varios pipelines con la
   API Python de PaddleX (`paddlex.create_pipeline(...)`) y expone rutas propias por
   capacidad. Reduce huella de runtime duplicado (1 proceso Python en vez de N), pero
   pierde el aislamiento de fallos por servicio (un crash de un pipeline puede tumbar
   el proceso completo) y requiere mantener el router/serialización a mano en vez de
   delegar en `paddlex --serve`. Mayor superficie propia de código — tensiona con
   “orquestar no inventar” más que la opción 2, pero menos que un sidecar completo.
5. **(b) Triton Inference Server** — exportar los modelos PaddleX a un backend servible
   por Triton (ONNX/Paddle backend) y correr un solo servidor Triton multi-modelo.
   Beneficio: gestión de memoria/batching madura y un solo proceso para muchos modelos.
   Costo: introduce una pieza de infraestructura nueva y pesada (no es "orquestar",
   es agregar una dependencia mayor), exportación de modelos no trivial para todos los
   pipelines PaddleX usados acá, y curva de aprendizaje/operación adicional para un
   proyecto pedagógico. Candidato solo si el spike de la opción 2/4 no alcanza y el
   costo de RAM sigue siendo bloqueante en un host real de producción.

### RAM medida (PC-Javier, 2026-07-25)

Medición real con las **13 capacidades arriba a la vez** (`docker stats`, idle y
bajo carga e2e). Método: `scripts/benchmark_paddlex.py` (latencia por servicio) +
muestreo de `docker stats` durante fotos e2e.

| Escenario | RSS por proceso (medido) | RSS total | Notas |
|---|---|---|---|
| 13 caps idle | 0.3–1.6 GiB (open_vocab el mayor) | ~9.4 GiB | Todas healthy |
| 13 caps bajo carga e2e | pico open_vocab 1.49 GiB, small_objects 1.15 GiB | **~9.1 GiB pico** | Suma de picos |
| Opción 4 (FastAPI multi-pipeline, N modelos en 1 proceso) | TBD | TBD | Requiere spike de serving separado |
| Opción 5 (Triton) | TBD | TBD | Requiere exportación de modelos, spike separado |

**Hallazgo clave — WSL2 cap de RAM.** Aunque el host tiene 32 GB, el daemon Docker
(WSL2) solo ve **~15.18 GiB** (`docker info` → `MemTotal`). Las 13 caps entran
holgadas (pico ~9.1 GiB, 60% del budget WSL2), así que RAM **no** es el límite; el
cuello es CPU (~10–15 s de wall e2e por foto en el Ryzen 8500G). Para usar más de
los 32 GB físicos hay que subir el límite en `~/.wslconfig` (`[wsl2] memory=24GB`)
y reiniciar WSL — no es necesario hoy dado el margen.

### Nota RAM — host de referencia 32 GB

Las 13 capacidades corren juntas bajo el techo único `x-limits-paddlex`
(`mem_limit: 2000m` por contenedor) en PC-Javier (32 GB). Conviven con `adapter`,
`bridge` y la SPA en `/app/` sin presión de RAM; el cuello observado es CPU
(Ryzen 8500G, 6c/12t repartidos entre 13 procesos), no memoria. El smoke completo
(`scripts/smoke_extended.sh`) sí corre en este host (ver `infra/README.md`).

## Decisión (Sprint 2)

**No merge de servicios.** Entregable de este ADR: documentar el trade-off y dejar el spike como follow-up solo si, tras medir con `scripts/benchmark_paddlex.py` + `docker stats`, la RAM de extended sigue siendo bloqueante en el desktop 32 GB *después* de los `mem_limit`.

## Criterio para reabrir

- Un host target real < 16 GB necesita más de 3 capacidades a la vez, **o**
- PaddleX documenta/soporta multi-pipeline serve estable en un proceso.

## Consecuencias

- Sigue el mapa carpeta ↔ capacidad ↔ servicio del README.
- La reducción de huella inmediata es operativa (`mem_limit` por contenedor, apagar capacidades vía `ENABLE_*`), no arquitectónica.

## Enmienda (2026-07-25) — cascada por evidencia (invocaciones, no procesos)

**Ortogonal al merge de servicios:** con `ENABLE_EVIDENCE_CASCADE` el bridge
ejecuta dos oleadas (core + independientes → dependientes por evidencia).
Reduce llamadas HTTP/CPU cuando no hay persona/rostro/objects inciertos;
**no** reduce RAM idle ni cantidad de contenedores. `docker pause`/`stop`
queda como follow-up tras medir.

| Capacidad | Oleada | Trigger MVP |
|-----------|--------|-------------|
| vehicles, objects | 1 | siempre / SPA-active |
| faces, pose, signs, scene, text, scene_cls, instances, small_objects, anomaly | 1 | SPA + ENABLE (sin trigger de evidencia aún) |
| pedestrians | 2 | `objects` con `label=person` |
| face_id | 2 | `faces` con ≥1 hit |
| open_vocab | 2 | objects failed/empty/`max(score)<CASCADE_OBJECT_LOW_SCORE` |
| plates | enrich | sin cambio (`OCR_MIN_SCORE` sobre vehicles) |

Rollback: `ENABLE_EVIDENCE_CASCADE=false` (gather único legacy).

## Enmienda (2026-07-25) — signs + open_vocab sobre `:8093`

**Desviación consciente del invariante 1 carpeta = 1 capacidad = 1 servicio:**
dos clients (`detection/signs`, `detection/open_vocab`) pegan al mismo proceso
`paddlex-open-vocab` `:8093` (YOLO-Worldv2-L) con prompts distintos. Consolida
y apaga `paddlex-signs` `:8088` (Compose `profiles: ["legacy-signs"]`).

| Tema | Decisión |
|------|----------|
| Ownership de "señal" | Exclusiva de `signs` (`entity_type:"sign"` / `s-*`). `OPEN_VOCAB_PROMPT` **sin** `"traffic sign"`. |
| Label | Colapsado a `"sign"`; `categoryName`+score como `hint`. |
| Perillas | `SIGNS_OV_PROMPT` + `SIGNS_OV_THRESHOLD` (no heredar `SIGNS_THRESHOLD`). |
| SPOF | Si `:8093` cae, **signs + open_vocab** fallan en el POST. `available` sigue saliendo de `ENABLE_*` sin probe HTTP (preexistente) — ahora arrastra dos caps. Trade-off aceptado frente a liberar ~2 GiB del servicio COCO. |
| Rollback | `docker compose --profile legacy-signs up -d paddlex-signs` + `SIGNS_BACKEND=coco` + `PADDLEX_SIGNS_URL=http://paddlex-signs:8088`. |
| Gate eval | El número `signs` en `scripts/eval_baseline.json` es **baseline COCO legacy decorativo**, no el path de producto OV. |
