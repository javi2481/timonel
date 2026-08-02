# detection/small_objects/

## Para qué sirve

Detección de objetos muy chicos (`small_object_detection`, PP-YOLOE_plus_SOD).
Emite `entity_type:"small_object"`.

## Aviso de dominio

El modelo SOD está entrenado en imágenes **aéreas/drone** (VisDrone-style). En
fotos genéricas a nivel de suelo (las de `imagenes_muestra`) no dispara: da 0
detecciones aunque la respuesta sea 200. No es un bug de parsing — el client ya
lee `detectedObjects`. Para que aporte hits hay que alimentar imágenes aéreas o
apuntar el servicio a pesos propios.

## Servicio / deps

| Item | Valor |
|------|--------|
| Compose | `paddlex-small-objects` `:8091` (stack default; ENABLE true vía Compose) |
| Env | `ENABLE_SMALL_OBJECTS`, `PADDLEX_SMALL_OBJECTS_URL` |
