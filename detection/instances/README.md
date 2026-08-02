# detection/instances/

## Para qué sirve

Instance segmentation (`entity_type:"instance"`, tracks `i-*`).
Servicio `paddlex-instances` `:8090` en el **stack default**; Compose fuerza
`ENABLE_INSTANCE_SEG=true`.

## Cómo funciona

1. Bridge POST JPEG a `/instance-segmentation` si la capa está activa.
2. `normalize_instances_result` → bbox + label + score (máscara RLE del serving
   no se propaga hoy al contrato SPA).
3. Fallo HTTP → `None` (aislado).

## Servicio / deps

| Item | Valor |
|------|--------|
| Compose | `paddlex-instances` `:8090` |
| Env | `ENABLE_INSTANCE_SEG`, `PADDLEX_INSTANCES_URL` |

## Qué no es

No reemplaza `objects/` (COCO det). No es conteo denso fine-tuneado.
