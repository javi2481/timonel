# Smoke PR3: zonas runtime (`TIMONEL_ZONES_JSON` → contrato → rules)

**Date:** 2026-07-25  
**Master tip:** `d569a76` (PR1 #19 + PR2 #20 + PR3 #21).  
**SCHEMA_VERSION:** `"1.0"` (campo `zones` aditivo).

## Prerrequisitos

1. Rebuild bridge (PR2+ deps `supervision==0.28.0`) y rules-sink (`CMD` = `rules.app:app`, no el legacy `rules_sink:app`).
2. Compose pasa `TIMONEL_ZONES_JSON` al bridge (ver `docker-compose.yml`).
3. Perfil rules + webhook:

```bash
# .env (ejemplo smoke — polígono full-frame)
TIMONEL_ZONES_JSON=[{"id":"no_parking","polygon":[[0.0,0.0],[1.0,0.0],[1.0,1.0],[0.0,1.0]]}]
JETLINKS_WEBHOOK_URL=http://rules-sink:8850/webhook/events
JETLINKS_API_KEY=demo
RULES_SINK_API_KEY=demo
BRIDGE_MAX_WIDTH=1920
ENABLE_INFER_TILING=false

docker compose --profile rules up -d --build bridge adapter rules-sink
```

Denorm runtime: `pts * [w, h]` → `PolygonZone` (nunca `denormalize_boxes`).

## Smoke ejecutado

```text
POST /media/select {"name":"fo_vehicles_0001.jpg"}
GET  /events?limit=50
GET  http://127.0.0.1:8850/alerts  (x-api-key: demo)
```

### Resultado

| Check | Resultado |
|-------|-----------|
| Tag `zones` en PerceptionEvent | **OK** — 7/7 eventos con `zones: ["no_parking"]`, `schema_version: "1.0"` |
| Alerta rules-sink | **OK** — `reason: "zone:no_parking"` (prioridad sobre `confidence`) |
| Bridge load zones | `load_zone_configs()` → 1 zona `no_parking` |

## Nota ops

Imágenes Docker **anteriores a PR3** podían arrancar `uvicorn rules_sink:app` (módulo root sin campo `zones`). Tras rebuild, `CMD` debe ser `uvicorn rules.app:app ...`. Verificar:

```bash
docker inspect tm-rules-sink --format "{{.Config.Cmd}}"
# → [uvicorn rules.app:app --host 0.0.0.0 --port 8850 --reload]
```
